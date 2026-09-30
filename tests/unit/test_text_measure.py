"""The injectable ``TextMeasurer`` seam (spec §4, issue #75).

A deterministic fake measurer, passed through ``CompileContext``, drives
every width decision the compiler makes; nothing reaches ReportLab.
"""

from __future__ import annotations

import warnings
from dataclasses import replace

import pytest

from holiday_card.core import text_measure
from holiday_card.core.compiler import (
    CompileContext,
    SafeZoneWarning,
    UnknownFontError,
    compile_card,
)
from holiday_card.core.export_targets import get_target
from holiday_card.core.flatten import flatten_transparency
from holiday_card.core.models import (
    Card,
    Color,
    FoldType,
    OverflowStrategy,
    Panel,
    PanelPosition,
    TextElement,
)
from holiday_card.core.per_panel import build_per_panel_context
from holiday_card.core.render_ir import RGBA, DrawText, Point, TextRun
from holiday_card.core.text_fitting import fit_text_element, truncate_to_fit
from holiday_card.core.text_measure import (
    TextMeasurer,
    default_text_measurer,
    set_default_text_measurer,
)
from holiday_card.core.text_utils import measure_text, shrink_to_fit, wrap_text


class FixedWidthMeasurer:
    """Every glyph is half an em wide; ascent 0.8 em, descent -0.2 em."""

    def __init__(self, fonts: frozenset[str] = frozenset({"Helvetica", "Mono"})) -> None:
        self.fonts = fonts
        self.calls: list[tuple[str, str, float]] = []

    def string_width(self, text: str, font_id: str, size_pt: float) -> float:
        self.calls.append((text, font_id, size_pt))
        return len(text) * size_pt * 0.5

    def ascent_descent(self, font_id: str, size_pt: float) -> tuple[float, float]:  # noqa: ARG002
        return (0.8 * size_pt, -0.2 * size_pt)

    def known_font_ids(self) -> frozenset[str]:
        return self.fonts


def _card(text: TextElement) -> Card:
    panel = Panel(
        position=PanelPosition.FRONT, width=4.25, height=5.5, text_elements=[text]
    )
    return Card(name="t", template_id="t", fold_type=FoldType.QUARTER_FOLD, panels=[panel])


def _texts(commands: list[object]) -> list[DrawText]:
    return [c for c in commands if isinstance(c, DrawText)]


def test_fake_satisfies_the_protocol() -> None:
    measurer: TextMeasurer = FixedWidthMeasurer()
    assert measurer.string_width("abcd", "Mono", 10) == 20.0


def test_compile_card_uses_the_injected_measurer_for_wrap_points() -> None:
    # 1.5" = 108 pt; at 12 pt each char is 6 pt, so 18 chars fit per line.
    text = TextElement(
        content="aaaa bbbb cccc dddd eeee ffff",
        x=0.25, y=4.0, width=1.5, font_family="Mono", font_size=12,
        min_font_size=12, overflow_strategy=OverflowStrategy.WRAP,
        color=Color(r=0, g=0, b=0),
    )
    measurer = FixedWidthMeasurer()
    commands = compile_card(
        _card(text), CompileContext(impose=False, emit_fold_lines=False, measurer=measurer)
    )
    assert [d.run.text for d in _texts(commands)] == [
        "aaaa bbbb cccc",
        "dddd eeee ffff",
    ]
    assert measurer.calls, "the compiler never consulted the injected measurer"
    assert {font for _t, font, _s in measurer.calls} == {"Mono"}


def test_compile_card_known_fonts_come_from_the_measurer() -> None:
    text = TextElement(content="hi", x=0.5, y=1.0, font_family="Lato", color=Color(r=0, g=0, b=0))
    ctx = CompileContext(impose=False, measurer=FixedWidthMeasurer())
    with pytest.raises(UnknownFontError, match="Available: Helvetica, Mono"):
        compile_card(_card(text), ctx)


def test_safe_zone_uses_the_measurer_extents() -> None:
    # Fitted panel: 40 chars × 6 pt = 240 pt, far wider than the A6 safe area.
    text = TextElement(
        content="x" * 40, x=0.1, y=4.0, font_family="Mono", font_size=12,
        min_font_size=12, overflow_strategy=OverflowStrategy.SHRINK,
        color=Color(r=0, g=0, b=0),
    )
    card = _card(text)
    ctx = build_per_panel_context(card.panels[0], get_target("moo-a6"))
    ctx = replace(ctx, measurer=FixedWidthMeasurer())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compile_card(card, ctx)
    assert any(issubclass(w.category, SafeZoneWarning) for w in caught)


def test_text_utils_and_fitting_take_a_measurer() -> None:
    m = FixedWidthMeasurer()
    assert measure_text(m, "abcd", "Mono", 10, max_width=19.0).width_pts == 20.0
    assert shrink_to_fit(m, "abcd", "Mono", 20, max_width=20.0, min_size=4) == 10
    # "ab cd" is 5 chars × 5 pt = 25 pt: the wrap point sits exactly there.
    assert wrap_text(m, "ab cd ef", "Mono", 10, max_width=24.9) == ["ab", "cd", "ef"]
    assert wrap_text(m, "ab cd ef", "Mono", 10, max_width=25.0) == ["ab cd", "ef"]
    assert truncate_to_fit(m, "abcdefgh", "Mono", 10, max_width=30.0) == "abc..."
    text = TextElement(
        content="abcdefgh", x=0, y=0, width=30 / 72, font_family="Mono", font_size=10,
        min_font_size=10, overflow_strategy=OverflowStrategy.TRUNCATE,
        color=Color(r=0, g=0, b=0),
    )
    panel = Panel(position=PanelPosition.FRONT, width=4.25, height=5.5)
    size, lines, _ = fit_text_element(m, text, panel, "Mono")
    assert (size, lines) == (10, ["abc..."])


def test_flatten_measures_text_through_the_measurer() -> None:
    measurer = FixedWidthMeasurer()
    run = TextRun(
        text="abc", font_id="Mono", size_pt=10, origin=Point(x=10, y=10),
        color=RGBA(r=0, g=0, b=0, a=0.5),
    )
    draw = DrawText(run=run)
    flatten_transparency([draw], where="t", measurer=measurer)
    assert ("abc", "Mono", 10) in measurer.calls


def test_default_measurer_without_registration_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text_measure, "_default_factory", None)
    with pytest.raises(RuntimeError, match="no TextMeasurer registered"):
        default_text_measurer()


def test_set_default_text_measurer_is_what_compile_card_uses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(text_measure, "_default_factory", None)
    fake = FixedWidthMeasurer()
    set_default_text_measurer(lambda: fake)
    assert default_text_measurer() is fake
    # "Mono" is known only to the fake, so compiling at all proves it is used.
    text = TextElement(
        content="hello", x=0.5, y=1.0, width=2.0, font_family="Mono",
        color=Color(r=0, g=0, b=0),
    )
    compile_card(_card(text), CompileContext(impose=False))
    assert fake.calls


def test_package_registers_a_default_measurer() -> None:
    import holiday_card  # noqa: F401 — the composition root registers on import

    measurer = default_text_measurer()
    assert measurer.string_width("Hello", "Helvetica", 12) > 0
    assert "Cormorant" in measurer.known_font_ids()
