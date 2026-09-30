"""ReportLab-backed ``TextMeasurer`` (issue #75).

Measures the IR ``font_id`` exactly as ``Canvas.stringWidth`` did when the
compiler owned a throwaway canvas: base-14 names use ReportLab's AFM
metrics, curated names their registered TTFs.
"""

from __future__ import annotations

from reportlab.pdfbase.pdfmetrics import getAscentDescent, stringWidth

from holiday_card.renderers.font_registry import ensure_default_fonts_registered, known_font_ids

__all__ = ["ReportLabTextMeasurer"]


class ReportLabTextMeasurer:
    """``TextMeasurer`` over ``reportlab.pdfbase.pdfmetrics``."""

    def __init__(self) -> None:
        # Curated TTFs are unknown to ReportLab until registered (KeyError).
        ensure_default_fonts_registered()

    def string_width(self, text: str, font_id: str, size_pt: float) -> float:
        """Advance width in points (same call ``Canvas.stringWidth`` makes)."""
        return float(stringWidth(text, font_id, size_pt))

    def ascent_descent(self, font_id: str, size_pt: float) -> tuple[float, float]:
        """``(ascent, descent)`` in points, from the font's metrics."""
        ascent, descent = getAscentDescent(font_id, size_pt)
        return (ascent, descent)

    def known_font_ids(self) -> frozenset[str]:
        """The bundled base-14 + curated catalog."""
        return known_font_ids()
