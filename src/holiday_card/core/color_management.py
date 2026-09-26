"""Color-space conversion + ICC profile resolution.

This module hosts the pieces of color management that the rest of the
codebase needs in order to emit CMYK PDFs for press-quality export
targets (``--export-for moo-a6`` today; more POD targets later).

Two responsibilities:

1. **sRGB → DeviceCMYK conversion.** A deterministic per-pixel formula
   used by ``IRReportLabRenderer`` when the renderer is constructed in
   CMYK mode. The conversion is intentionally *naive* — it does not
   apply the destination ICC profile in software. Perceptual accuracy
   is the responsibility of the printer's RIP, which interprets the
   emitted DeviceCMYK values through the OutputIntent ICC profile
   embedded in the PDF/X-1a by ``pdfx_postprocess``. This matches the
   PDF/X-1a workflow used by most professional toolchains: emit
   DeviceCMYK + attach the destination profile; let the RIP do
   colorimetric work.

2. **ICC profile path resolution.** Locating the bundled
   ``GRACoL2013_CRPC6.icc`` so the post-processor and other callers
   don't have to know the asset layout. The profile ships as package
   data under ``holiday_card/data/icc/`` and is located via
   :func:`holiday_card.core.data_paths.data_path`, so editable and
   wheel (pipx) installs resolve it the same way.
"""

from __future__ import annotations

from pathlib import Path

from holiday_card.core.data_paths import data_path

__all__ = [
    "DEFAULT_CMYK_PROFILE_FILENAME",
    "ICCProfileNotFoundError",
    "default_cmyk_icc_path",
    "rgb_to_cmyk",
]


DEFAULT_CMYK_PROFILE_FILENAME = "GRACoL2013_CRPC6.icc"


class ICCProfileNotFoundError(FileNotFoundError):
    """Raised when the requested ICC profile can't be located on disk."""


def rgb_to_cmyk(r: float, g: float, b: float) -> tuple[float, float, float, float]:
    """Convert an sRGB triplet in [0, 1] to a DeviceCMYK quadruplet in [0, 1].

    Uses the standard "black removal" formula:

    * K = 1 - max(R, G, B)
    * If K == 1 (input is pure black), return pure K — C/M/Y can be
      anything mathematically, but 0 is the convention.
    * Else C = (1 - R - K) / (1 - K), and similarly for M and Y.

    The output is *device* CMYK: it has no colorimetric meaning until
    a destination ICC profile is applied. The PDF/X-1a OutputIntent is
    where the colorimetric meaning gets attached.

    Out-of-range inputs are clamped silently — callers shouldn't
    produce them, but the IR's ``RGBA`` model only validates at
    construction so a downstream bug shouldn't crash the renderer.
    """
    r = _clamp01(r)
    g = _clamp01(g)
    b = _clamp01(b)
    k = 1.0 - max(r, g, b)
    if k >= 1.0 - 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    denom = 1.0 - k
    c = (1.0 - r - k) / denom
    m = (1.0 - g - k) / denom
    y = (1.0 - b - k) / denom
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


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v
