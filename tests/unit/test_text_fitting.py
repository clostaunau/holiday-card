"""Tests for the extracted text-fitting strategies.

These cover the public surface of ``core/text_fitting.py`` — the functions
the future Wave 2 compiler will call. Behavior parity with the renderer's
old private methods is implicitly verified by the integration suite (every
existing PDF-rendering test still passes); these unit tests lock in the
free-function contract so the compiler PR can build against it safely.
"""

import pytest

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
from holiday_card.core.text_measure import TextMeasurer
from holiday_card.core.text_utils import measure_text, wrap_text
from holiday_card.renderers.reportlab_measurer import ReportLabTextMeasurer
from holiday_card.utils.measurements import inches_to_points


@pytest.fixture
def measurer() -> TextMeasurer:
    """The production ReportLab measurer, so widths are the real ones."""
    return ReportLabTextMeasurer()


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
    def test_returns_content_unchanged_when_it_already_fits(self, measurer: TextMeasurer) -> None:
        out = truncate_to_fit(measurer, "hi", "Helvetica", 12, max_width=500.0)
        assert out == "hi"

    def test_appends_ellipsis_when_overflowing(self, measurer: TextMeasurer) -> None:
        out = truncate_to_fit(measurer, "this is far too long for a tiny box",
                              "Helvetica", 14, max_width=20.0)
        assert out.endswith("...")
        assert len(out) < len("this is far too long for a tiny box")


# ---------------------------------------------------------------------------
# apply_shrink_strategy
# ---------------------------------------------------------------------------


class TestApplyShrinkStrategy:
    def test_returns_unchanged_when_no_width_constraint(self, measurer: TextMeasurer) -> None:
        text = _make_text("Hello", width=None)
        size, content = apply_shrink_strategy(measurer, text, "Helvetica")
        assert size == text.font_size
        assert content == "Hello"

    def test_returns_smaller_size_for_overflowing_text(self, measurer: TextMeasurer) -> None:
        # Force overflow: 60-char string in a 1-inch box at 24pt is too wide.
        text = _make_text("a" * 60, width=1.0, font_size=24, min_font_size=8)
        size, content = apply_shrink_strategy(measurer, text, "Helvetica")
        assert size <= 24


# ---------------------------------------------------------------------------
# apply_wrap_strategy
# ---------------------------------------------------------------------------


class TestApplyWrapStrategy:
    def test_short_text_returns_single_line(self, measurer: TextMeasurer, panel: Panel) -> None:
        text = _make_text("Brief.")
        size, lines = apply_wrap_strategy(measurer, text, panel, "Helvetica")
        assert lines == ["Brief."]
        assert size == text.font_size

    def test_long_text_wraps_to_multiple_lines(self, measurer: TextMeasurer, panel: Panel) -> None:
        long = " ".join(["lorem ipsum dolor sit amet"] * 8)
        text = _make_text(long, width=2.0, font_size=14)
        _, lines = apply_wrap_strategy(measurer, text, panel, "Helvetica")
        assert len(lines) > 1


class HalfEmMeasurer:
    """Every glyph is half an em wide, so fits are exact and monotone in size."""

    def string_width(self, text: str, font_id: str, size_pt: float) -> float:  # noqa: ARG002
        return len(text) * size_pt * 0.5

    def ascent_descent(self, font_id: str, size_pt: float) -> tuple[float, float]:  # noqa: ARG002
        return (0.8 * size_pt, -0.2 * size_pt)

    def known_font_ids(self) -> frozenset[str]:
        return frozenset({"Helvetica"})


def _fits_wrapped(m: TextMeasurer, text: TextElement, panel: Panel, size: int) -> bool:
    """Re-measure ``text`` wrapped at ``size`` against its width and the panel height."""
    width = inches_to_points(text.width or 0.0)
    lines = wrap_text(m, text.content, "Helvetica", size, width, text.max_lines)
    return measure_text(
        m, text.content, "Helvetica", size, width, inches_to_points(panel.height), lines
    ).fits_within_bounds


class TestWrapShrinksToFitHeight:
    """The binary search inside ``apply_wrap_strategy`` (#84)."""

    _PARAGRAPH = " ".join(["word"] * 40)

    @pytest.mark.parametrize("panel_height", [1.5, 2.0, 3.0, 4.5])
    def test_returns_the_largest_size_that_fits(self, panel_height: float) -> None:
        m = HalfEmMeasurer()
        panel = Panel(position=PanelPosition.FRONT, width=4.25, height=panel_height)
        text = _make_text(self._PARAGRAPH, width=3.0, font_size=36, min_font_size=6)
        assert not _fits_wrapped(m, text, panel, 36)  # overflows at the requested size

        size, lines = apply_wrap_strategy(m, text, panel, "Helvetica")

        assert text.min_font_size < size < text.font_size
        assert _fits_wrapped(m, text, panel, size)
        assert not _fits_wrapped(m, text, panel, size + 1)
        assert lines == wrap_text(m, text.content, "Helvetica", size, inches_to_points(3.0))
        assert size == max(
            s for s in range(text.min_font_size, text.font_size + 1)
            if _fits_wrapped(m, text, panel, s)
        )

    def test_never_drops_below_min_font_size(self) -> None:
        m = HalfEmMeasurer()
        panel = Panel(position=PanelPosition.FRONT, width=4.25, height=0.1)
        text = _make_text(self._PARAGRAPH, width=3.0, font_size=36, min_font_size=9)
        assert not _fits_wrapped(m, text, panel, 9)  # nothing fits, not even the floor

        size, lines = apply_wrap_strategy(m, text, panel, "Helvetica")

        assert size == 9
        assert lines == wrap_text(m, text.content, "Helvetica", 36, inches_to_points(3.0))

    def test_text_that_fits_keeps_its_size(self) -> None:
        m = HalfEmMeasurer()
        panel = Panel(position=PanelPosition.FRONT, width=4.25, height=8.0)
        text = _make_text(self._PARAGRAPH, width=3.0, font_size=12, min_font_size=6)
        size, _ = apply_wrap_strategy(m, text, panel, "Helvetica")
        assert size == 12


class TestShrinkAtTheFloor:
    def test_truncates_at_min_font_size_when_still_too_wide(self) -> None:
        m = HalfEmMeasurer()
        text = _make_text("x" * 100, width=1.0, font_size=24, min_font_size=8)
        size, content = apply_shrink_strategy(m, text, "Helvetica")
        assert size == 8
        assert content.endswith("...")
        assert content != text.content
        assert m.string_width(content, "Helvetica", 8) <= inches_to_points(1.0)
        # Maximal: one more character would overflow.
        assert m.string_width("x" + content, "Helvetica", 8) > inches_to_points(1.0)

    def test_shrinks_without_truncating_when_a_larger_size_fits(self) -> None:
        m = HalfEmMeasurer()
        text = _make_text("x" * 12, width=1.0, font_size=24, min_font_size=8)
        size, content = apply_shrink_strategy(m, text, "Helvetica")
        assert size == 12  # 12 chars x 6 pt = 72 pt = 1"
        assert content == text.content

    def test_fits_exactly_at_the_floor_without_truncating(self) -> None:
        m = HalfEmMeasurer()
        text = _make_text("x" * 18, width=1.0, font_size=24, min_font_size=8)
        size, content = apply_shrink_strategy(m, text, "Helvetica")
        assert size == 8  # 18 chars x 4 pt = 72 pt
        assert content == text.content


# ---------------------------------------------------------------------------
# apply_truncate_strategy
# ---------------------------------------------------------------------------


class TestApplyTruncateStrategy:
    def test_short_text_returned_unchanged(self, measurer: TextMeasurer) -> None:
        text = _make_text("ok", font_size=12)
        size, content = apply_truncate_strategy(measurer, text, "Helvetica")
        assert size == 12
        assert content == "ok"

    def test_long_text_truncated_with_ellipsis(self, measurer: TextMeasurer) -> None:
        text = _make_text("this content is far too wide to fit", width=0.5, font_size=14)
        _, content = apply_truncate_strategy(measurer, text, "Helvetica")
        assert content.endswith("...")


# ---------------------------------------------------------------------------
# fit_text_element — the integration entry point used by both the renderer
# and (soon) the compiler.
# ---------------------------------------------------------------------------


class TestFitTextElement:
    def test_returns_unchanged_for_text_that_already_fits(
        self, measurer: TextMeasurer, panel: Panel
    ) -> None:
        text = _make_text("Hi", font_size=12, overflow_strategy=OverflowStrategy.SHRINK)
        size, lines, result = fit_text_element(measurer, text, panel, "Helvetica")
        assert size == 12
        assert lines == ["Hi"]
        assert result.was_adjusted is False
        assert result.strategy_applied == OverflowStrategy.SHRINK

    def test_auto_strategy_resolves_to_concrete_choice(
        self, measurer: TextMeasurer, panel: Panel
    ) -> None:
        text = _make_text("Hi", overflow_strategy=OverflowStrategy.AUTO)
        _, _, result = fit_text_element(measurer, text, panel, "Helvetica")
        # AUTO must always resolve to a concrete strategy in the report.
        assert result.strategy_applied != OverflowStrategy.AUTO
        assert result.strategy_applied in (
            OverflowStrategy.SHRINK,
            OverflowStrategy.WRAP,
            OverflowStrategy.TRUNCATE,
        )

    def test_wrap_strategy_reports_multiple_lines(
        self, measurer: TextMeasurer, panel: Panel
    ) -> None:
        long = " ".join(["lorem ipsum dolor sit amet consectetur"] * 5)
        text = _make_text(long, width=2.0, overflow_strategy=OverflowStrategy.WRAP)
        _, lines, result = fit_text_element(measurer, text, panel, "Helvetica")
        assert len(lines) >= 2
        assert result.lines_used == len(lines)
        assert result.was_adjusted is True
