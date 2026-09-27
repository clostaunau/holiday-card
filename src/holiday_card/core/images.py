"""Image source resolution and content validation (D5).

Templates are data: a template's ``image_elements[].source_path`` resolves
relative to the template file and may not leave its directory. Every image
the compiler puts on the IR is probed here first, so its format comes from
the bytes rather than the file extension. Otherwise the SVG backend would
base64-embed any readable file (e.g. ``secret.env``) into shareable output.

Pillow only; no renderer imports.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Literal

from PIL import Image

MAX_IMAGE_PIXELS = 50_000_000
"""Largest image accepted (50 MP); larger files are refused, not downscaled."""

# MPO is what Pillow calls a JPEG with a CIPA MPF marker (dual-camera phone
# photos); its first frame is an ordinary JPEG, which is what every backend reads.
_FORMATS: dict[str, Literal["png", "jpeg"]] = {"PNG": "png", "JPEG": "jpeg", "MPO": "jpeg"}


class ImageSourceError(ValueError):
    """An image source path or its content is not acceptable."""


@dataclass(frozen=True)
class ProbedImage:
    """An image whose bytes have been checked to be a whole PNG or JPEG."""

    path: Path
    format: Literal["png", "jpeg"]
    width_px: int
    height_px: int


def resolve_template_image_path(source_path: str, template_dir: Path) -> Path:
    """Resolve a template's image ``source_path`` against its template directory.

    Raises:
        ImageSourceError: If the path is empty or absolute, has a ``..``
            component, or resolves (e.g. via a symlink) outside ``template_dir``.
    """
    if not source_path:
        raise ImageSourceError("image source_path is empty")
    pure = PurePath(source_path)
    if pure.is_absolute():
        raise ImageSourceError(
            f"image source_path {source_path!r} is absolute; template images "
            f"must be relative to the template file"
        )
    if ".." in pure.parts:
        raise ImageSourceError(
            f"image source_path {source_path!r} contains '..'; template images "
            f"must live in the template's directory or below it"
        )
    base = template_dir.resolve()
    resolved = (base / pure).resolve()
    if not resolved.is_relative_to(base):
        raise ImageSourceError(
            f"image source_path {source_path!r} resolves to {resolved}, "
            f"outside the template directory {base}"
        )
    return resolved


def probe_image(path: Path) -> ProbedImage:
    """Check that ``path`` holds a complete PNG or JPEG and return its size.

    The format is read from the file's bytes; the extension is ignored.

    Raises:
        ImageSourceError: If the file is missing, unreadable, not a PNG or
            JPEG, truncated/corrupt, or larger than ``MAX_IMAGE_PIXELS``.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise ImageSourceError(f"image file not found: {path}")
    try:
        with warnings.catch_warnings():
            # Pillow warns (not raises) between its own limit and 2x it.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(resolved) as img:
                pil_format = img.format or "unknown"
                width, height = img.size
                if pil_format not in _FORMATS:
                    raise ImageSourceError(
                        f"image {resolved} is {pil_format}; only PNG and JPEG "
                        f"are supported"
                    )
                if width * height > MAX_IMAGE_PIXELS:
                    raise ImageSourceError(
                        f"image {resolved} is {width}x{height} "
                        f"({width * height / 1e6:.1f} megapixels); the limit is "
                        f"{MAX_IMAGE_PIXELS / 1e6:.0f} megapixels"
                    )
                img.verify()
            # verify() leaves the image unusable and skips pixel data for
            # JPEG, so decode once more to catch truncation.
            with Image.open(resolved) as img:
                img.load()
    except ImageSourceError:
        raise
    except (
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as e:
        raise ImageSourceError(f"image {resolved} is not a readable image: {e}") from e
    return ProbedImage(
        path=resolved, format=_FORMATS[pil_format], width_px=width, height_px=height
    )
