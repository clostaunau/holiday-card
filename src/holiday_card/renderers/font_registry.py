"""Embedded-font registry for the IR backends.

Ships open-source TTF fonts (Liberation Sans / Serif / Mono — SIL OFL +
GPL with font exception) that are metric-equivalent to the PDF base-14
fonts (Helvetica, Times-Roman, Courier). When the IR emits a ``font_id``
like ``"Helvetica"``, both the PDF backend and the PNG backend resolve
it to the corresponding Liberation font and **embed/subset** it instead
of relying on the PDF reader (or Pillow's bitmap fallback) to substitute
something host-OS-specific.

This addresses defect 9 from the industry critique panel — until this
module landed, ``pdffonts`` reported ``Helvetica … emb=no, sub=no``
on every generated PDF.

Custom fonts (``font_file`` in the template) continue to be handled
through the existing per-renderer registration path — this module only
covers the default Helvetica/Times/Courier chain.
"""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

__all__ = [
    "FONT_DIR",
    "CURATED_FONT_DIR",
    "FONT_MAP",
    "CURATED_FONTS",
    "ensure_default_fonts_registered",
    "resolve_font_id",
    "ttf_path_for",
]

logger = logging.getLogger(__name__)

# Repo-relative fonts directory. Resolved at import time.
# src/holiday_card/renderers/font_registry.py → ../../../fonts/
FONT_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent / "fonts"
CURATED_FONT_DIR: Path = FONT_DIR / "curated"

# IR font_id (matches PDF base-14 conventional names) → (TTF filename, registered name).
# The registered name is what gets passed to canvas.setFont() in the PDF
# backend, and to Pillow's ImageFont.truetype() in the PNG backend.
FONT_MAP: dict[str, tuple[str, str]] = {
    # Helvetica → Liberation Sans
    "Helvetica":             ("LiberationSans-Regular.ttf",      "LiberationSans"),
    "Helvetica-Bold":        ("LiberationSans-Bold.ttf",         "LiberationSans-Bold"),
    "Helvetica-Oblique":     ("LiberationSans-Italic.ttf",       "LiberationSans-Italic"),
    "Helvetica-BoldOblique": ("LiberationSans-BoldItalic.ttf",   "LiberationSans-BoldItalic"),
    # Times-Roman → Liberation Serif
    "Times-Roman":           ("LiberationSerif-Regular.ttf",     "LiberationSerif"),
    "Times-Bold":            ("LiberationSerif-Bold.ttf",        "LiberationSerif-Bold"),
    "Times-Italic":          ("LiberationSerif-Italic.ttf",      "LiberationSerif-Italic"),
    "Times-BoldItalic":      ("LiberationSerif-BoldItalic.ttf",  "LiberationSerif-BoldItalic"),
    # Courier → Liberation Mono
    "Courier":               ("LiberationMono-Regular.ttf",      "LiberationMono"),
    "Courier-Bold":          ("LiberationMono-Bold.ttf",         "LiberationMono-Bold"),
    "Courier-Oblique":       ("LiberationMono-Italic.ttf",       "LiberationMono-Italic"),
    "Courier-BoldOblique":   ("LiberationMono-BoldItalic.ttf",   "LiberationMono-BoldItalic"),
}


# Curated fonts shipped with the project (Leapfrog 2). These are
# *intentional* typeface choices — not the metric-equivalent
# Liberation defaults — designed for greeting-card composition. The
# panel's "curated font shipment" recommendation (consensus-general.md
# Agreement 1) called for 6-8 curated open-source fonts in fonts/.
#
# IR font_id (the canonical short name templates reference) →
# (TTF filename relative to CURATED_FONT_DIR, registered name).
#
# Pairing intent (templates can mix freely):
#   * Cormorant — editorial / devotional serif (display + body)
#   * PlayfairDisplay — high-contrast display serif (covers, accents)
#   * Lato — friendly geometric sans (body, warm voice)
#   * Inter — modern variable sans (body, modern voice; the only one
#       with both opsz + wght axes)
#   * Caveat — handwritten script (signatures, irreverent voice)
#   * Comfortaa — rounded display (witty voice)
#
# Variable fonts (Cormorant, Inter, Caveat, PlayfairDisplay,
# Comfortaa) load at their default weight in both ReportLab and
# Pillow. A future PR can register specific weights as separate
# font_ids if needed.
CURATED_FONTS: dict[str, tuple[str, str]] = {
    "Cormorant":              ("CormorantGaramond-Regular.ttf", "Cormorant"),
    "Cormorant-Italic":       ("CormorantGaramond-Italic.ttf",  "Cormorant-Italic"),
    "PlayfairDisplay":        ("PlayfairDisplay-Regular.ttf",   "PlayfairDisplay"),
    "PlayfairDisplay-Italic": ("PlayfairDisplay-Italic.ttf",    "PlayfairDisplay-Italic"),
    "Lato":                   ("Lato-Regular.ttf",              "Lato"),
    "Lato-Bold":              ("Lato-Bold.ttf",                 "Lato-Bold"),
    "Inter":                  ("Inter-Regular.ttf",             "Inter"),
    "Caveat":                 ("Caveat-Regular.ttf",            "Caveat"),
    "Comfortaa":              ("Comfortaa-Regular.ttf",         "Comfortaa"),
}

_registered: bool = False


def ensure_default_fonts_registered() -> None:
    """Register the default + curated font chains with ReportLab. Idempotent.

    Safe to call from every backend's ``render()`` and from every
    constructor — the second and subsequent calls are no-ops.
    """
    global _registered
    if _registered:
        return
    for font_id, (filename, reg_name) in FONT_MAP.items():
        _try_register(reg_name, FONT_DIR / filename, font_id)
    for font_id, (filename, reg_name) in CURATED_FONTS.items():
        _try_register(reg_name, CURATED_FONT_DIR / filename, font_id)
    _registered = True


def _try_register(reg_name: str, path: Path, font_id: str) -> None:
    if not path.exists():
        logger.warning(
            "Font %s not found at %s; backend will fall back to %r.",
            path.name, path, font_id,
        )
        return
    try:
        pdfmetrics.registerFont(TTFont(reg_name, str(path)))
    except Exception as e:  # noqa: BLE001 — registration is best-effort
        logger.warning("Failed to register font %s: %s", reg_name, e)


def resolve_font_id(font_id: str) -> str:
    """Map an IR ``font_id`` to the registered ReportLab font name.

    Curated fonts win over the Liberation default chain when a name
    collides (currently no collision, but future-safe). Returns the
    original ``font_id`` unchanged when it is not in either map (so
    user-registered ``font_file`` paths still work).
    """
    curated = CURATED_FONTS.get(font_id)
    if curated:
        return curated[1]
    entry = FONT_MAP.get(font_id)
    return entry[1] if entry else font_id


def ttf_path_for(font_id: str) -> Path | None:
    """Return the on-disk TTF path for a registered font_id, or None.

    Checks the curated chain first, then the Liberation default chain.
    Used by the PNG backend to give Pillow a direct file path instead
    of relying on system font lookup.
    """
    curated = CURATED_FONTS.get(font_id)
    if curated:
        path = CURATED_FONT_DIR / curated[0]
        if path.exists():
            return path
    entry = FONT_MAP.get(font_id)
    if entry is None:
        return None
    path = FONT_DIR / entry[0]
    return path if path.exists() else None
