"""Image source resolution and content validation (D5).

Templates are data: a template's ``image_elements[].source_path`` resolves
relative to the template file and may not leave its directory. Every image
the compiler puts on the IR is probed here first, so its format comes from
the bytes rather than the file extension. Otherwise the SVG backend would
base64-embed any readable file (e.g. ``secret.env``) into shareable output.

It also checks the effective print resolution of placed images (#66):
PPI is read from the final IR, so a compiler scale group is counted.

Pillow only; no renderer imports.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Final, Literal

from PIL import Image

from holiday_card.core.render_ir import BeginGroup, DrawImage, EndGroup, ImageRef, RenderCommand
from holiday_card.utils.measurements import MIN_DPI, POINTS_PER_INCH

RECOMMENDED_PRINT_PPI: Final = 300
"""Print services (MOO, Prodigi) expect this at final size; below it warns."""

MIN_PRINT_PPI: Final = MIN_DPI
"""Below this a print target refuses the image (D4); 150."""

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


@dataclass(frozen=True)
class ResolutionFinding:
    """A placed image below a print-resolution threshold."""

    source: str  # ImageRef.source
    ppi: float  # effective, at final placed size
    level: Literal["warn", "fail"]
    needed_width_px: int  # pixels needed at RECOMMENDED_PRINT_PPI
    needed_height_px: int


class LowResolutionWarning(UserWarning):
    """A placed image prints below ``RECOMMENDED_PRINT_PPI`` (or below the
    minimum, when ``--allow-low-res`` downgraded the failure)."""


class LowResolutionImageError(ValueError):
    """An image would print below ``MIN_PRINT_PPI`` at its placed size."""

    def __init__(self, findings: Sequence[ResolutionFinding]) -> None:
        self.findings = list(findings)
        lines = [f"  {describe_finding(f)}" for f in self.findings]
        super().__init__(
            f"image resolution is below the {MIN_PRINT_PPI} PPI print minimum "
            f"(--allow-low-res renders anyway, for proofs only):\n" + "\n".join(lines)
        )


def effective_ppi(ref: ImageRef, group_scale: float = 1.0) -> float:
    """Pixels per inch of ``ref`` at its displayed size.

    ``preserve_aspect`` ("meet") fits the image uniformly, so the axis that
    touches the rect sets the PPI (``max``); a stretched image is as soft as
    its most stretched axis (``min``). Rotation does not change PPI.
    """
    w_in = ref.rect.width / POINTS_PER_INCH * group_scale
    h_in = ref.rect.height / POINTS_PER_INCH * group_scale
    per_axis = (ref.width_px / w_in, ref.height_px / h_in)
    return max(per_axis) if ref.preserve_aspect else min(per_axis)


def check_print_resolution(
    commands: Sequence[RenderCommand],
    *,
    warn_below: float = RECOMMENDED_PRINT_PPI,
    fail_below: float = MIN_PRINT_PPI,
) -> list[ResolutionFinding]:
    """Return one finding per ``DrawImage`` below ``warn_below`` (fail beats warn).

    Each enclosing group scales the placed size by ``|scale_x·scale_y|^½``.
    """
    scales: list[float] = [1.0]
    findings: list[ResolutionFinding] = []
    for cmd in commands:
        if isinstance(cmd, BeginGroup):
            t = cmd.transform
            scales.append(scales[-1] * math.sqrt(abs(t.scale_x * t.scale_y)))
        elif isinstance(cmd, EndGroup):
            scales.pop()
        elif isinstance(cmd, DrawImage):
            ref, scale = cmd.image, scales[-1]
            ppi = effective_ppi(ref, scale)
            if ppi >= warn_below:
                continue
            findings.append(ResolutionFinding(
                source=ref.source,
                ppi=ppi,
                level="fail" if ppi < fail_below else "warn",
                needed_width_px=_pixels_at(ref.rect.width * scale, RECOMMENDED_PRINT_PPI),
                needed_height_px=_pixels_at(ref.rect.height * scale, RECOMMENDED_PRINT_PPI),
            ))
    return findings


def describe_finding(finding: ResolutionFinding) -> str:
    """``me.jpg is 212 PPI at its placed size (300 recommended; need ≥ 885×885 px)``."""
    return (
        f"{Path(finding.source).name} is {finding.ppi:.0f} PPI at its placed size "
        f"({RECOMMENDED_PRINT_PPI} recommended; need ≥ "
        f"{finding.needed_width_px}×{finding.needed_height_px} px)"
    )


def _pixels_at(length_pt: float, ppi: float) -> int:
    # round() first so 2.95" at 300 PPI is 885, not 886 from float noise.
    return math.ceil(round(length_pt / POINTS_PER_INCH * ppi, 6))
