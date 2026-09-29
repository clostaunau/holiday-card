"""Registry of named export targets for ``holiday-card create``.

A target is a (name, layout, [geometry]) triple plus a panel-fit mode.
The two layouts:

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

__all__ = [
    "ExportTarget",
    "PanelFit",
    "REGISTRY",
    "get_target",
    "ExportTargetNotFoundError",
]

# How a per-panel target maps a panel onto its fixed trim (D8). ``native``
# keeps the panel's own size; ``fill`` scales by ``max`` and crops the
# overflow; ``letterbox`` scales by ``min`` and leaves paper bands.
PanelFit = Literal["native", "fill", "letterbox"]


class ExportTargetNotFoundError(KeyError):
    """Raised when an unknown ``--export-for`` value is requested."""


@dataclass(frozen=True)
class ExportTarget:
    """A named output destination.

    For ``imposition`` targets, ``geometry`` is the sheet layout the
    compiler emits (one page, all panels). ``geometry`` is required.

    For ``per-panel`` targets:

    * ``geometry=None, panel_fit="native"`` — each output file uses
      the panel's native dimensions; only ``bleed_in`` and
      ``safe_margin_in`` from this target apply.
    * ``geometry=<PageGeometry>, panel_fit="fill"`` — each output file
      lands at ``geometry``'s trim. The compiler wraps the panel in one
      uniform scale group (``max`` of the two axis ratios), so the art
      covers the whole trim + bleed and the off-axis overflow is cropped
      (D8). ``"letterbox"`` (opt-in via ``--panel-fit``) uses ``min``
      instead and leaves paper bands on the off-axis.
    """

    name: str
    description: str
    layout: Literal["imposition", "per-panel"]
    bleed_in: float = DEFAULT_BLEED
    safe_margin_in: float = SAFE_MARGIN
    geometry: PageGeometry | None = None
    panel_fit: PanelFit = "native"
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
    # operators (k/K), converted at render time by
    # ``color_management.CMYKConverter`` (ICC, GRACoL2013, rel. col. +
    # BPC, 300% ink cap). Those numbers are what prints: the PDF/X
    # OutputIntent only names the intended condition.
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
            "US Letter (8.5\"x11\") imposition for home printers; one "
            "PDF/SVG/PNG with all panels on a single sheet, no bleed "
            "(MediaBox = 8.5x11) (default)."
        ),
        layout="imposition",
        geometry=PageGeometry.us_letter(),
    ),
    "per-panel-pdf": ExportTarget(
        name="per-panel-pdf",
        description=(
            "Each panel as a separate file at its native trim + "
            "0.125\" bleed. Use when you've designed templates for "
            "a specific finished-card size."
        ),
        layout="per-panel",
        panel_fit="native",
        fold_marks_default=False,
    ),
    "moo-a6": ExportTarget(
        name="moo-a6",
        description=(
            "MOO A6 folded card: each panel as a separate PDF/SVG/PNG "
            "at 4.13\"x5.83\" trim + 0.125\" bleed. Panel art is "
            "scaled to fill the trim and the overflow is cropped (text "
            "that crosses the safe zone is warned about; --panel-fit "
            "letterbox opts out). PDF output is CMYK + PDF/X-1a:2003 "
            "compliant for direct MOO submission."
        ),
        layout="per-panel",
        geometry=PageGeometry.moo_a6(),
        panel_fit="fill",
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
