"""The generator mutates cards only through validated assignment (#81, D4).

``validate_assignment`` sees ``panel.text_elements = [...]`` but not
``panel.text_elements.append(...)``, and a field-by-field switch of the
inside surface could pass through a state the model forbids. So the
generator reassigns lists and swaps whole, validated text elements.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from holiday_card.core import card_request, generators
from holiday_card.core.generators import CardGenerator
from holiday_card.core.letter import LetterContent
from holiday_card.core.markdown import parse_markdown
from holiday_card.core.models import Card, FoldType, Panel, PanelPosition, TextElement

_ELEMENT_LISTS = {"text_elements", "image_elements", "shape_elements", "panels"}
_MUTATORS = {"append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse"}


def _list_mutations(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _MUTATORS
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr in _ELEMENT_LISTS
        ):
            found.append(f"{path.name}:{node.lineno} .{node.func.value.attr}.{node.func.attr}()")
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr in _ELEMENT_LISTS
                ):
                    found.append(f"{path.name}:{node.lineno} .{target.value.attr}[...] =")
    return found


@pytest.mark.parametrize("module", [generators, card_request], ids=lambda m: m.__name__)
def test_no_in_place_mutation_of_model_lists(module: object) -> None:
    path = Path(module.__file__)  # type: ignore[attr-defined]
    assert _list_mutations(path) == []


def _card(*, inside_text: bool = True, front_text: bool = True) -> Card:
    def panel(position: PanelPosition, texts: list[TextElement]) -> Panel:
        return Panel(position=position, width=4.25, height=5.5, text_elements=texts)

    return Card(
        name="c",
        template_id="t",
        fold_type=FoldType.QUARTER_FOLD,
        panels=[
            panel(PanelPosition.FRONT, [TextElement(id="greeting", content="g", x=1, y=1)] if front_text else []),
            panel(PanelPosition.BACK, []),
            panel(PanelPosition.INSIDE_LEFT, []),
            panel(
                PanelPosition.INSIDE_RIGHT,
                [TextElement(id="message", content="m", x=1, y=1, font_family="Cormorant")] if inside_text else [],
            ),
        ],
    )


def _panel(card: Card, position: PanelPosition) -> Panel:
    return next(p for p in card.panels if p.position == position)


def _letter() -> LetterContent:
    return LetterContent(salutation="Dear M,", body="Hello")


class TestInsideApplySwapsTheElement:
    def test_letter_then_rich_leaves_only_rich(self) -> None:
        card = _card()
        gen = CardGenerator()
        gen.apply_inside_letter(card, _letter())
        gen.apply_inside_rich_content(card, parse_markdown("**hi**"))
        (message,) = _panel(card, PanelPosition.INSIDE_RIGHT).text_elements
        assert message.rich_content is not None
        assert message.letter_content is None
        assert message.content == ""
        assert (message.id, message.font_family) == ("message", "Cormorant")

    def test_rich_then_letter_leaves_only_letter(self) -> None:
        card = _card()
        gen = CardGenerator()
        gen.apply_inside_rich_content(card, parse_markdown("**hi**"))
        gen.apply_inside_letter(card, _letter())
        (message,) = _panel(card, PanelPosition.INSIDE_RIGHT).text_elements
        assert message.letter_content == _letter()
        assert message.rich_content is None

    def test_plain_message_clears_letter(self) -> None:
        card = _card()
        gen = CardGenerator()
        gen.apply_inside_letter(card, _letter())
        gen._apply_inside_message(card, "plain")
        (message,) = _panel(card, PanelPosition.INSIDE_RIGHT).text_elements
        assert (message.content, message.letter_content, message.rich_content) == ("plain", None, None)

    def test_the_element_is_replaced_not_edited(self) -> None:
        card = _card()
        panel = _panel(card, PanelPosition.INSIDE_RIGHT)
        before_list, (before,) = panel.text_elements, panel.text_elements
        CardGenerator().apply_inside_letter(card, _letter())
        assert panel.text_elements is not before_list
        assert panel.text_elements[0] is not before
        assert before.letter_content is None

    def test_auto_added_inside_element_goes_through_reassignment(self) -> None:
        card = _card(inside_text=False)
        panel = _panel(card, PanelPosition.INSIDE_LEFT)
        before_list = panel.text_elements
        CardGenerator()._apply_inside_message(card, "hello")
        assert panel.text_elements is not before_list
        (added,) = panel.text_elements
        assert (added.content, added.font_family) == ("hello", "Lato")


class TestFrontMessage:
    def test_auto_added_front_element_goes_through_reassignment(self) -> None:
        card = _card(front_text=False)
        panel = _panel(card, PanelPosition.FRONT)
        before_list = panel.text_elements
        CardGenerator()._apply_front_message(card, "Merry")
        assert panel.text_elements is not before_list
        (added,) = panel.text_elements
        assert added.content == "Merry"

    def test_front_message_too_long_raises(self) -> None:
        card = _card()
        with pytest.raises(ValueError, match="1000"):
            CardGenerator()._apply_front_message(card, "x" * 1001)
