"""Tests for the extracted text-fitting strategies.

These cover the public surface of ``core/text_fitting.py`` — the functions
the future Wave 2 compiler will call. Behavior parity with the renderer's
old private methods is implicitly verified by the integration suite (every
existing PDF-rendering test still passes); these unit tests lock in the
free-function contract so the compiler PR can build against it safely.
"""

import io

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as _canvas

from holiday_card.core.models import (
    Color,
    OverflowStrategy,
    Panel,
    PanelPosition,
    TextElement,
)
from holiday_card.core.text_fitting import (
    apply_shrink_strategy,
    apply_truncate_strategy,
    apply_wrap_strategy,
    fit_text_element,
    select_auto_strategy,
    truncate_to_fit,
)


@pytest.fixture
def pdf_canvas() -> _canvas.Canvas:
    """A throwaway in-memory canvas; we only call stringWidth-style methods."""
    return _canvas.Canvas(io.BytesIO(), pagesize=letter)


@pytest.fixture
def panel() -> Panel:
    return Panel(
        position=PanelPosition.FRONT,
        x=0.0,
        y=0.0,
        width=5.5,
        height=8.5,
    )


def _make_text(content: str, *, width: float | None = 3.0, font_size: int = 14, **kw: object) -> TextElement:
    """Build a TextElement with sensible defaults for these tests."""
    return TextElement(
        content=content,
        x=0.5,
        y=1.0,
        width=width,
        font_size=font_size,
        color=Color(r=0, g=0, b=0),
        **kw,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# select_auto_strategy
# ---------------------------------------------------------------------------


class TestSelectAutoStrategy:
    def test_short_text_chooses_shrink(self) -> None:
        text = _make_text("Hi!")
        assert select_auto_strategy(text) == OverflowStrategy.SHRINK

    def test_long_text_with_width_chooses_wrap(self) -> None:
        long = "a" * 80
        text = _make_text(long, width=2.0)
        assert select_auto_strategy(text) == OverflowStrategy.WRAP

    def test_long_text_without_width_falls_back_to_shrink(self) -> None:
        long = "a" * 80
        text = _make_text(long, width=None)
        assert select_auto_strategy(text) == OverflowStrategy.SHRINK


# ---------------------------------------------------------------------------
# truncate_to_fit
# ---------------------------------------------------------------------------


class TestTruncateToFit:
    def test_returns_content_unchanged_when_it_already_fits(self, pdf_canvas: _canvas.Canvas) -> None:
        out = truncate_to_fit(pdf_canvas, "hi", "Helvetica", 12, max_width=500.0)
        assert out == "hi"

    def test_appends_ellipsis_when_overflowing(self, pdf_canvas: _canvas.Canvas) -> None:
        out = truncate_to_fit(pdf_canvas, "this is far too long for a tiny box",
                              "Helvetica", 14, max_width=20.0)
        assert out.endswith("...")
        assert len(out) < len("this is far too long for a tiny box")


# ---------------------------------------------------------------------------
# apply_shrink_strategy
# ---------------------------------------------------------------------------


class TestApplyShrinkStrategy:
    def test_returns_unchanged_when_no_width_constraint(self, pdf_canvas: _canvas.Canvas) -> None:
        text = _make_text("Hello", width=None)
        size, content = apply_shrink_strategy(pdf_canvas, text, "Helvetica")
        assert size == text.font_size
        assert content == "Hello"

    def test_returns_smaller_size_for_overflowing_text(self, pdf_canvas: _canvas.Canvas) -> None:
        # Force overflow: 60-char string in a 1-inch box at 24pt is too wide.
        text = _make_text("a" * 60, width=1.0, font_size=24, min_font_size=8)
        size, content = apply_shrink_strategy(pdf_canvas, text, "Helvetica")
        assert size <= 24


# ---------------------------------------------------------------------------
# apply_wrap_strategy
# ---------------------------------------------------------------------------


class TestApplyWrapStrategy:
    def test_short_text_returns_single_line(self, pdf_canvas: _canvas.Canvas, panel: Panel) -> None:
        text = _make_text("Brief.")
        size, lines = apply_wrap_strategy(pdf_canvas, text, panel, "Helvetica")
        assert lines == ["Brief."]
        assert size == text.font_size

    def test_long_text_wraps_to_multiple_lines(self, pdf_canvas: _canvas.Canvas, panel: Panel) -> None:
        long = " ".join(["lorem ipsum dolor sit amet"] * 8)
        text = _make_text(long, width=2.0, font_size=14)
        _, lines = apply_wrap_strategy(pdf_canvas, text, panel, "Helvetica")
        assert len(lines) > 1


# ---------------------------------------------------------------------------
# apply_truncate_strategy
# ---------------------------------------------------------------------------


class TestApplyTruncateStrategy:
    def test_short_text_returned_unchanged(self, pdf_canvas: _canvas.Canvas) -> None:
        text = _make_text("ok", font_size=12)
        size, content = apply_truncate_strategy(pdf_canvas, text, "Helvetica")
        assert size == 12
        assert content == "ok"

    def test_long_text_truncated_with_ellipsis(self, pdf_canvas: _canvas.Canvas) -> None:
        text = _make_text("this content is far too wide to fit", width=0.5, font_size=14)
        _, content = apply_truncate_strategy(pdf_canvas, text, "Helvetica")
        assert content.endswith("...")


# ---------------------------------------------------------------------------
# fit_text_element — the integration entry point used by both the renderer
# and (soon) the compiler.
# ---------------------------------------------------------------------------


class TestFitTextElement:
    def test_returns_unchanged_for_text_that_already_fits(
        self, pdf_canvas: _canvas.Canvas, panel: Panel
    ) -> None:
        text = _make_text("Hi", font_size=12, overflow_strategy=OverflowStrategy.SHRINK)
        size, lines, result = fit_text_element(pdf_canvas, text, panel, "Helvetica")
        assert size == 12
        assert lines == ["Hi"]
        assert result.was_adjusted is False
        assert result.strategy_applied == OverflowStrategy.SHRINK

    def test_auto_strategy_resolves_to_concrete_choice(
        self, pdf_canvas: _canvas.Canvas, panel: Panel
    ) -> None:
        text = _make_text("Hi", overflow_strategy=OverflowStrategy.AUTO)
        _, _, result = fit_text_element(pdf_canvas, text, panel, "Helvetica")
        # AUTO must always resolve to a concrete strategy in the report.
        assert result.strategy_applied != OverflowStrategy.AUTO
        assert result.strategy_applied in (
            OverflowStrategy.SHRINK,
            OverflowStrategy.WRAP,
            OverflowStrategy.TRUNCATE,
        )

    def test_wrap_strategy_reports_multiple_lines(
        self, pdf_canvas: _canvas.Canvas, panel: Panel
    ) -> None:
        long = " ".join(["lorem ipsum dolor sit amet consectetur"] * 5)
        text = _make_text(long, width=2.0, overflow_strategy=OverflowStrategy.WRAP)
        _, lines, result = fit_text_element(pdf_canvas, text, panel, "Helvetica")
        assert len(lines) >= 2
        assert result.lines_used == len(lines)
        assert result.was_adjusted is True
