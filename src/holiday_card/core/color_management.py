"""Colour-managed sRGB → CMYK conversion + ICC profile resolution.

This module owns the colour management the press export targets
(``--export-for moo-a6`` today) need:

1. **sRGB → CMYK via ICC.** :class:`CMYKConverter` converts through
   LittleCMS (Pillow ``ImageCms``) from sRGB into the bundled
   GRACoL2013_CRPC6 profile with relative colorimetric intent and
   black-point compensation (D9), then caps total ink at 300%. Pure black
   gets press-conventional handling: text and strokes print K-only, large
   fills print a rich black. The numbers it returns are what gets
   printed: a RIP does **not** re-interpret DeviceCMYK through the
   PDF/X OutputIntent, which only names the condition the numbers were
   made for. There is no fallback to a naive formula; an unreadable or
   non-CMYK profile raises (D4, D17).

2. **ICC profile path resolution.** Locating the bundled
   ``GRACoL2013_CRPC6.icc`` so the post-processor and other callers
   don't have to know the asset layout. The profile ships as package
   data under ``holiday_card/data/icc/`` and is located via
   :func:`holiday_card.core.data_paths.data_path`, so editable and
   wheel (pipx) installs resolve it the same way.
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from typing import Literal

from PIL import Image, ImageCms

from holiday_card.core.data_paths import data_path

__all__ = [
    "DEFAULT_CMYK_PROFILE_FILENAME",
    "CMYKConverter",
    "ColorRole",
    "ICCProfileNotFoundError",
    "default_cmyk_icc_path",
]


DEFAULT_CMYK_PROFILE_FILENAME = "GRACoL2013_CRPC6.icc"

ColorRole = Literal["text", "stroke", "fill"]

_CMYK = tuple[float, float, float, float]
_K_ONLY: _CMYK = (0.0, 0.0, 0.0, 1.0)


class ICCProfileNotFoundError(FileNotFoundError):
    """Raised when the requested ICC profile can't be located on disk."""


class CMYKConverter:
    """sRGB -> CMYK via ICC (relative colorimetric + BPC) with ink cap and black rules.

    Rules, in order:

    1. Pure black (``r == g == b == 0``): ``text`` / ``stroke`` → K-only
       ``(0, 0, 0, 1)``; a ``fill`` whose bbox ``area_pt2`` is at least
       ``rich_black_min_area_pt2`` (1 in²) → ``rich_black``; a smaller
       fill, or one with no known area, → K-only.
    2. Otherwise the colour is quantised to 8 bits and converted through
       one LittleCMS transform (sRGB → profile, relative colorimetric +
       black-point compensation), memoised per 8-bit triplet.
    3. Ink cap: if ``C+M+Y+K > total_ink_limit``, C, M and Y are scaled by
       ``(limit − K) / (C+M+Y)``; K is kept.

    Channels are fractions in ``[0, 1]``; ``total_ink_limit`` is a sum of
    fractions (3.00 = 300%).

    Raises:
        ICCProfileNotFoundError: ``profile_path`` (or the bundled profile)
            does not exist.
        ValueError: the file isn't a readable ICC profile, or its colour
            space isn't CMYK.
    """

    def __init__(
        self,
        profile_path: Path | None = None,
        *,
        total_ink_limit: float = 3.00,
        rich_black: tuple[float, float, float, float] = (0.60, 0.40, 0.40, 1.00),
        rich_black_min_area_pt2: float = 72.0 * 72.0,
    ) -> None:
        path = profile_path if profile_path is not None else default_cmyk_icc_path()
        if not path.is_file():
            raise ICCProfileNotFoundError(f"CMYK ICC profile not found at {path}")
        try:
            self._profile = ImageCms.getOpenProfile(str(path))
        except (ImageCms.PyCMSError, OSError) as e:
            raise ValueError(f"{path} is not a readable ICC profile: {e}") from e
        space = self._profile.profile.xcolor_space.strip()
        if space != "CMYK":
            raise ValueError(f"{path} is a {space!r} profile; a CMYK profile is required")
        self.total_ink_limit = total_ink_limit
        self.rich_black = rich_black
        self.rich_black_min_area_pt2 = rich_black_min_area_pt2
        self._srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
        self._transform = self._build_transform(self._srgb)
        self._convert8 = lru_cache(maxsize=4096)(self._convert8_uncached)

    def convert(
        self,
        r: float,
        g: float,
        b: float,
        *,
        role: ColorRole = "fill",
        area_pt2: float | None = None,
    ) -> tuple[float, float, float, float]:
        """Convert one sRGB colour (channels in ``[0, 1]``, clamped) to CMYK fractions."""
        rgb8 = (_to8(r), _to8(g), _to8(b))
        if rgb8 == (0, 0, 0):
            if (
                role == "fill"
                and area_pt2 is not None
                and area_pt2 >= self.rich_black_min_area_pt2
            ):
                return self.rich_black
            return _K_ONLY
        return self._convert8(rgb8)

    def convert_image(self, image: Image.Image) -> Image.Image:
        """Convert a raster image to mode ``"CMYK"`` (rules 2–3; no black rules).

        An embedded ``icc_profile`` is honoured as the source profile;
        otherwise the pixels are assumed to be sRGB.
        """
        embedded = image.info.get("icc_profile")
        rgb = image if image.mode == "RGB" else image.convert("RGB")
        if embedded:
            try:
                source = ImageCms.ImageCmsProfile(io.BytesIO(embedded))
            except (ImageCms.PyCMSError, OSError) as e:
                raise ValueError(f"image carries an unreadable ICC profile: {e}") from e
            transform = self._build_transform(source)
        else:
            transform = self._transform
        out = ImageCms.applyTransform(rgb, transform)
        assert out is not None  # applyTransform returns None only when inPlace=True
        return self._cap_image(out)

    # ------------------------------------------------------------------

    def _build_transform(self, source: ImageCms.ImageCmsProfile) -> ImageCms.ImageCmsTransform:
        return ImageCms.buildTransform(
            source,
            self._profile,
            "RGB",
            "CMYK",
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
            flags=ImageCms.Flags.BLACKPOINTCOMPENSATION,
        )

    def _convert8_uncached(self, rgb8: tuple[int, int, int]) -> _CMYK:
        px = ImageCms.applyTransform(Image.new("RGB", (1, 1), rgb8), self._transform)
        assert px is not None
        c8, m8, y8, k8 = px.getpixel((0, 0))  # type: ignore[misc]
        return self._cap((c8 / 255, m8 / 255, y8 / 255, k8 / 255))

    def _cap(self, cmyk: _CMYK) -> _CMYK:
        c, m, y, k = cmyk
        cmy = c + m + y
        if cmy + k <= self.total_ink_limit or cmy == 0.0:
            return cmyk
        scale = max(self.total_ink_limit - k, 0.0) / cmy
        return (c * scale, m * scale, y * scale, k)

    def _cap_image(self, image: Image.Image) -> Image.Image:
        limit8 = self.total_ink_limit * 255
        raw = bytearray(image.tobytes())
        for i in range(0, len(raw), 4):
            px = raw[i : i + 4]
            if sum(px) > limit8:
                raw[i : i + 4] = bytes(_floor8(self._cap(tuple(v / 255 for v in px))))  # type: ignore[arg-type]
        return Image.frombytes("CMYK", image.size, bytes(raw))


def _to8(v: float) -> int:
    return round(min(max(v, 0.0), 1.0) * 255)


def _floor8(cmyk: _CMYK) -> tuple[int, int, int, int]:
    # Flooring keeps the 8-bit sum at or under the limit.
    c, m, y, k = (int(v * 255) for v in cmyk)
    return (c, m, y, k)


def default_cmyk_icc_path() -> Path:
    """Return the absolute filesystem path to the bundled CMYK ICC profile.

    The profile ships at ``holiday_card/data/icc/GRACoL2013_CRPC6.icc``.
    It is GRACoL2013_CRPC6 (US commercial coated), the ICC's CGATS21
    reference profile that MOO and most US POD services expect. Override
    by passing an explicit path to callers that accept one.

    Raises:
        ICCProfileNotFoundError: the bundled profile file is missing.
    """
    path = data_path("icc") / DEFAULT_CMYK_PROFILE_FILENAME
    if not path.is_file():
        raise ICCProfileNotFoundError(
            f"Bundled CMYK ICC profile {DEFAULT_CMYK_PROFILE_FILENAME!r} not "
            f"found at {path}; the installation is missing bundled data."
        )
    return path
