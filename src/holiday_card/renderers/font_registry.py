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
    "FONT_MAP",
    "ensure_default_fonts_registered",
    "resolve_font_id",
    "ttf_path_for",
]

logger = logging.getLogger(__name__)

# Repo-relative fonts directory. Resolved at import time.
# src/holiday_card/renderers/font_registry.py → ../../../fonts/
FONT_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent / "fonts"

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

_registered: bool = False


def ensure_default_fonts_registered() -> None:
    """Register the default font chain with ReportLab. Idempotent.

    Safe to call from every backend's ``render()`` and from every
    constructor — the second and subsequent calls are no-ops.
    """
    global _registered
    if _registered:
        return
    for font_id, (filename, reg_name) in FONT_MAP.items():
        path = FONT_DIR / filename
        if not path.exists():
            logger.warning(
                "Default font %s not found at %s; backend will fall back to %r.",
                filename, path, font_id,
            )
            continue
        try:
            pdfmetrics.registerFont(TTFont(reg_name, str(path)))
        except Exception as e:  # noqa: BLE001 — registration is best-effort
            logger.warning("Failed to register font %s: %s", reg_name, e)
    _registered = True


def resolve_font_id(font_id: str) -> str:
    """Map an IR ``font_id`` to the registered ReportLab font name.

    Returns the original ``font_id`` unchanged if it is not in the
    default map (so custom fonts registered via ``font_file`` still
    work). Returns the Liberation equivalent otherwise.
    """
    entry = FONT_MAP.get(font_id)
    return entry[1] if entry else font_id


def ttf_path_for(font_id: str) -> Path | None:
    """Return the on-disk TTF path for a default font_id, or None if
    not in the default map. Used by the PNG backend to give Pillow a
    direct file path instead of relying on system font lookup.
    """
    entry = FONT_MAP.get(font_id)
    if entry is None:
        return None
    path = FONT_DIR / entry[0]
    return path if path.exists() else None
