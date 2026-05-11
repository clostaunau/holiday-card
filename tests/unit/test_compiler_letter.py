"""Compiler-level tests for ``_compile_letter_content``.

Asserts the DrawText emission shape and ordering — the layout choice
itself (top-to-bottom, conventional gaps, P.S. at 85%) is exercised
by checking the size_pt and y-ordinates on the emitted commands.
"""

from __future__ import annotations

from holiday_card.core.compiler import compile_card
from holiday_card.core.letter import LetterContent
from holiday_card.core.models import (
    Card,
    FoldType,
    OccasionType,
    Panel,
    PanelPosition,
    TextElement,
)
from holiday_card.core.render_ir import DrawText


def _make_card(text: TextElement) -> Card:
    """One-panel minimal card carrying the text element under test."""
    panel = Panel(
        position=PanelPosition.INSIDE_LEFT,
        width=4.0,
        height=6.0,
        x=0.0,
        y=0.0,
        text_elements=[text],
    )
    return Card(
        name="test",
        template_id="t",
        occasion=OccasionType.GENERIC,
        fold_type=FoldType.HALF_FOLD,
        panels=[panel],
    )


def _draw_texts(commands: list) -> list[DrawText]:
    return [c for c in commands if isinstance(c, DrawText)]


class TestCompileLetterContent:
    def test_all_five_parts_emit_in_order(self) -> None:
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            width=3.0,
            font_family="Helvetica",
            font_size=12,
            letter_content=LetterContent(
                salutation="Dear M,",
                body="Hello",
                signoff="Love,",
                signature="C",
                postscript="PS hi",
            ),
        )
        commands = compile_card(_make_card(text))
        draws = _draw_texts(commands)
        # Exactly five parts → five DrawTexts (each part is a single
        # line that fits within width=3.0").
        texts = [d.run.text for d in draws]
        assert texts == ["Dear M,", "Hello", "Love,", "C", "PS hi"]

    def test_empty_letter_emits_nothing(self) -> None:
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            letter_content=LetterContent(),  # all empty
        )
        commands = compile_card(_make_card(text))
        assert _draw_texts(commands) == []

    def test_omitted_parts_collapse_naturally(self) -> None:
        # Only salutation + body — the layout should produce two
        # DrawTexts, with no leftover blank-line space awkwardness.
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            width=3.0,
            font_size=12,
            letter_content=LetterContent(salutation="Hey,", body="Brief note."),
        )
        draws = _draw_texts(compile_card(_make_card(text)))
        assert [d.run.text for d in draws] == ["Hey,", "Brief note."]

    def test_postscript_size_is_85_percent_of_body(self) -> None:
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            font_size=20,  # 20 * 0.85 = 17
            letter_content=LetterContent(body="hi", postscript="PS"),
        )
        draws = _draw_texts(compile_card(_make_card(text)))
        body_draw, ps_draw = draws
        assert body_draw.run.size_pt == 20.0
        assert ps_draw.run.size_pt == 17.0

    def test_postscript_size_floor_is_6pt(self) -> None:
        # Per the model: even with a tiny body font, P.S. won't go
        # below the readable floor of 6pt.
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            font_size=6,  # 6 * 0.85 = 5.1 → floor to 6
            letter_content=LetterContent(body="hi", postscript="PS"),
        )
        draws = _draw_texts(compile_card(_make_card(text)))
        body_draw, ps_draw = draws
        assert body_draw.run.size_pt == 6.0
        assert ps_draw.run.size_pt == 6.0

    def test_signature_uses_override_font(self) -> None:
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            font_family="Lato",
            font_size=12,
            letter_content=LetterContent(
                signature="C",
                signature_font_family="Caveat",
            ),
        )
        draws = _draw_texts(compile_card(_make_card(text)))
        assert len(draws) == 1
        assert draws[0].run.font_id == "Caveat"

    def test_signature_defaults_to_body_font(self) -> None:
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            font_family="Lato",
            font_size=12,
            letter_content=LetterContent(signature="C"),
        )
        draws = _draw_texts(compile_card(_make_card(text)))
        assert draws[0].run.font_id == "Lato"

    def test_parts_stack_top_to_bottom_with_gaps(self) -> None:
        # Y coordinates should strictly decrease (PDF y goes up;
        # stacked text moves down the page).
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            width=3.0,
            font_size=12,
            letter_content=LetterContent(
                salutation="A",
                body="B",
                signoff="C",
                signature="D",
                postscript="E",
            ),
        )
        draws = _draw_texts(compile_card(_make_card(text)))
        ys = [d.run.origin.y for d in draws]
        assert ys == sorted(ys, reverse=True), (
            f"Letter parts should stack top-to-bottom (y strictly decreasing); "
            f"got {ys}"
        )

    def test_body_with_newlines_splits_into_multiple_drawtexts(self) -> None:
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            width=3.0,
            font_size=12,
            letter_content=LetterContent(body="line one\nline two"),
        )
        draws = _draw_texts(compile_card(_make_card(text)))
        assert [d.run.text for d in draws] == ["line one", "line two"]

    def test_body_with_paragraph_break_splits(self) -> None:
        # Blank line in body → wrap_text treats as paragraph boundary
        # by virtue of the hard-newline split inside emit_block.
        text = TextElement(
            content="",
            x=0.5,
            y=5.0,
            width=3.0,
            font_size=12,
            letter_content=LetterContent(body="para one\n\npara two"),
        )
        draws = _draw_texts(compile_card(_make_card(text)))
        assert [d.run.text for d in draws] == ["para one", "para two"]
