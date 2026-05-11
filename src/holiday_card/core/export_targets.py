"""Registry of named export targets for ``holiday-card create``.

A target is a (name, layout, [geometry]) triple plus an optional
content-scaling flag. The two layouts:

* ``imposition`` — the today-default: every panel is laid out on a
  single sheet (US Letter, half-fold imposition). One file out.
* ``per-panel`` — the POD-friendly mode: each panel becomes its own
  page in its own file. Used by MOO, Catprint, Vistaprint, Printful.

Targets are exposed via the CLI's ``--export-for`` flag. Adding a new
target (e.g. ``vistaprint-5x7``) is a one-line registry entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from holiday_card.utils.measurements import (
    DEFAULT_BLEED,
    SAFE_MARGIN,
    PageGeometry,
)

__all__ = ["ExportTarget", "REGISTRY", "get_target", "ExportTargetNotFoundError"]


class ExportTargetNotFoundError(KeyError):
    """Raised when an unknown ``--export-for`` value is requested."""


@dataclass(frozen=True)
class ExportTarget:
    """A named output destination.

    For ``imposition`` targets, ``geometry`` is the sheet layout the
    compiler emits (one page, all panels). ``geometry`` is required.

    For ``per-panel`` targets:

    * ``geometry=None, scale_panels_to_fit=False`` — each output file
      uses the panel's native dimensions; only ``bleed_in`` and
      ``safe_margin_in`` from this target apply.
    * ``geometry=<PageGeometry>, scale_panels_to_fit=True`` — each
      output file lands at ``geometry``'s trim, with panel content
      uniformly scaled to fit (letterboxed on the off-axis if the
      aspect ratios disagree).
    """

    name: str
    description: str
    layout: Literal["imposition", "per-panel"]
    bleed_in: float = DEFAULT_BLEED
    safe_margin_in: float = SAFE_MARGIN
    geometry: PageGeometry | None = None
    scale_panels_to_fit: bool = False
    # Default fold-mark behavior for this target. Imposition targets
    # (single sheet for home printer) default ON — the user folds the
    # printed sheet by hand and the dashed grey guide helps align the
    # crease. Per-panel targets default OFF — each output file is a
    # finished card, never folded; the fold guide would print on the
    # finished product. Overridable via the CLI's --with-fold-marks /
    # --no-fold-marks flag.
    fold_marks_default: bool = True
    # Color space for the emitted PDF stream. ``srgb`` is today's
    # default and what home-printer / browser previews expect.
    # ``cmyk`` switches the PDF backend to emit DeviceCMYK color
    # operators (k/K) using a deterministic sRGB→CMYK conversion at
    # render time; perceptual interpretation is deferred to the
    # OutputIntent ICC profile attached by the PDF/X post-processor.
    # Non-PDF backends (SVG/PNG) ignore this field today.
    color_space: Literal["srgb", "cmyk"] = "srgb"
    # PDF/X conformance level to apply via post-processing. ``None``
    # means no PDF/X structuring (today's behavior). ``"PDF/X-1a:2003"``
    # triggers the pikepdf post-pass that embeds the OutputIntent ICC
    # profile, writes the XMP metadata stream, sets the /Trapped key,
    # and forces PDF 1.4. Currently only ``"PDF/X-1a:2003"`` is
    # recognized; other levels raise at post-process time.
    pdfx: str | None = None


REGISTRY: dict[str, ExportTarget] = {
    "letter": ExportTarget(
        name="letter",
        description=(
            "US Letter (8.5\"x11\") imposition; one PDF/SVG/PNG with "
            "all panels on a single sheet (default)."
        ),
        layout="imposition",
        geometry=PageGeometry.us_letter(bleed_in=DEFAULT_BLEED),
    ),
    "per-panel-pdf": ExportTarget(
        name="per-panel-pdf",
        description=(
            "Each panel as a separate file at its native trim + "
            "0.125\" bleed. Use when you've designed templates for "
            "a specific finished-card size."
        ),
        layout="per-panel",
        scale_panels_to_fit=False,
        fold_marks_default=False,
    ),
    "moo-a6": ExportTarget(
        name="moo-a6",
        description=(
            "MOO A6 folded card: each panel as a separate PDF/SVG/PNG "
            "at 4.13\"x5.83\" trim + 0.125\" bleed. Panel content is "
            "uniformly scaled to fit; aspect-ratio mismatch produces "
            "letterbox bands. PDF output is CMYK + PDF/X-1a:2003 "
            "compliant for direct MOO submission."
        ),
        layout="per-panel",
        geometry=PageGeometry.moo_a6(),
        scale_panels_to_fit=True,
        fold_marks_default=False,
        color_space="cmyk",
        pdfx="PDF/X-1a:2003",
    ),
}


def get_target(name: str) -> ExportTarget:
    """Look up an export target by name.

    Raises ``ExportTargetNotFoundError`` (a KeyError subclass) if the
    name is not registered. The error message lists the available
    targets for quick recovery.
    """
    target = REGISTRY.get(name)
    if target is None:
        available = ", ".join(sorted(REGISTRY))
        raise ExportTargetNotFoundError(
            f"unknown export target {name!r}. Available: {available}"
        )
    return target
