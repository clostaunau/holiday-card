"""``ReportLabTextMeasurer`` is numerically identical to ``Canvas.stringWidth`` (#75)."""

from __future__ import annotations

import io

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import getAscentDescent
from reportlab.pdfgen import canvas

from holiday_card.renderers.font_registry import (
    CURATED_FONTS,
    FONT_MAP,
    ensure_default_fonts_registered,
    known_font_ids,
)
from holiday_card.renderers.reportlab_measurer import ReportLabTextMeasurer

FONT_IDS = sorted(set(FONT_MAP) | set(CURATED_FONTS))
SIZES = (7.5, 12, 36)
SAMPLE = "Merry Christmas — and a joyful, peaceful New Year! 0123 éñü"


@pytest.fixture(scope="module")
def reference() -> canvas.Canvas:
    ensure_default_fonts_registered()
    return canvas.Canvas(io.BytesIO(), pagesize=letter)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("font_id", FONT_IDS)
def test_string_width_matches_canvas(reference: canvas.Canvas, font_id: str, size: float) -> None:
    measured = ReportLabTextMeasurer().string_width(SAMPLE, font_id, size)
    assert measured == reference.stringWidth(SAMPLE, font_id, size)


@pytest.mark.parametrize("font_id", FONT_IDS)
def test_ascent_descent_matches_pdfmetrics(font_id: str) -> None:
    ensure_default_fonts_registered()
    assert ReportLabTextMeasurer().ascent_descent(font_id, 18) == getAscentDescent(font_id, 18)


def test_known_font_ids_is_the_registry_catalog() -> None:
    assert ReportLabTextMeasurer().known_font_ids() == known_font_ids()


def test_a_fresh_measurer_registers_the_fonts_itself() -> None:
    # Curated TTFs are unknown to ReportLab until registered: the measurer
    # must not rely on some earlier caller having done it.
    assert ReportLabTextMeasurer().string_width("Hi", "Caveat", 10) > 0
