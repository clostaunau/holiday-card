"""Unit tests for core domain models."""

import inspect

import pytest
from pydantic import BaseModel, ValidationError

from holiday_card.core import models
from holiday_card.core.letter import LetterContent
from holiday_card.core.markdown import RichTextContent, parse_markdown
from holiday_card.core.models import (
    AdjustmentResult,
    BorderStyle,
    Card,
    Color,
    Colors,
    FoldType,
    FontStyle,
    OccasionType,
    OverflowStrategy,
    Panel,
    PanelPosition,
    Rectangle,
    Template,
    TextAlignment,
    TextElement,
    Theme,
)

# Every non-frozen domain model defined in core/models.py (#81).
_MUTABLE_MODEL_NAMES = sorted(
    name
    for name, cls in vars(models).items()
    if inspect.isclass(cls)
    and issubclass(cls, BaseModel)
    and cls.__module__ == models.__name__
    and not cls.model_config.get("frozen", False)
)


class TestColor:
    """Tests for Color model."""

    def test_valid_color(self):
        """Test creating a valid color."""
        color = Color(r=0.5, g=0.5, b=0.5)
        assert color.r == 0.5
        assert color.g == 0.5
        assert color.b == 0.5

    def test_color_from_hex(self):
        """Test creating color from hex string."""
        color = Color.from_hex("#FF0000")
        assert color.r == 1.0
        assert color.g == 0.0
        assert color.b == 0.0

    def test_color_to_hex(self):
        """Test converting color to hex string."""
        color = Color(r=1.0, g=0.0, b=0.0)
        assert color.to_hex() == "#ff0000"

    def test_color_to_tuple(self):
        """Test converting color to tuple."""
        color = Color(r=0.5, g=0.6, b=0.7)
        assert color.to_tuple() == (0.5, 0.6, 0.7)

    def test_invalid_color_range(self):
        """Test that out-of-range values raise validation error."""
        with pytest.raises(ValidationError):
            Color(r=1.5, g=0.5, b=0.5)

    def test_predefined_colors(self):
        """Test predefined color constants."""
        assert Colors.WHITE.r == 1.0
        assert Colors.BLACK.r == 0.0
        assert Colors.RED.r == 0.8


class TestEnums:
    """Tests for enumeration types."""

    def test_fold_type_values(self):
        """Test FoldType enum values."""
        assert FoldType.HALF_FOLD.value == "half_fold"
        assert FoldType.QUARTER_FOLD.value == "quarter_fold"
        assert FoldType.TRI_FOLD.value == "tri_fold"

    def test_occasion_type_values(self):
        """Test OccasionType enum values."""
        assert OccasionType.CHRISTMAS.value == "christmas"
        assert OccasionType.BIRTHDAY.value == "birthday"

    def test_sympathy_class_occasions_exist(self):
        # Panel L2 taxonomy expansion — these exist so the AI hard-rails
        # planned for L3 (consensus-ai-feature.md) have categories to
        # refuse against by default.
        assert OccasionType.SYMPATHY.value == "sympathy"
        assert OccasionType.CONDOLENCE.value == "condolence"
        assert OccasionType.MISCARRIAGE.value == "miscarriage"
        assert OccasionType.PET_LOSS.value == "pet_loss"

    def test_panel_position_values(self):
        """Test PanelPosition enum values."""
        assert PanelPosition.FRONT.value == "front"
        assert PanelPosition.BACK.value == "back"

    def test_font_style_values(self):
        """Test FontStyle enum values."""
        assert FontStyle.BOLD.value == "bold"
        assert FontStyle.ITALIC.value == "italic"

    def test_text_alignment_values(self):
        """Test TextAlignment enum values."""
        assert TextAlignment.CENTER.value == "center"

    def test_border_style_values(self):
        """Test BorderStyle enum values."""
        assert BorderStyle.SOLID.value == "solid"
        assert BorderStyle.DASHED.value == "dashed"

    def test_overflow_strategy_enum_values(self):
        """Test OverflowStrategy enum values."""
        assert OverflowStrategy.AUTO.value == "auto"
        assert OverflowStrategy.SHRINK.value == "shrink"
        assert OverflowStrategy.WRAP.value == "wrap"
        assert OverflowStrategy.TRUNCATE.value == "truncate"


class TestAdjustmentResult:
    """Tests for AdjustmentResult model."""

    def test_creation(self):
        """Test creating an AdjustmentResult."""
        result = AdjustmentResult(
            was_adjusted=True,
            strategy_applied=OverflowStrategy.SHRINK,
            original_font_size=36,
            final_font_size=24,
            lines_used=1,
            content_truncated=False,
        )
        assert result.was_adjusted is True
        assert result.strategy_applied == OverflowStrategy.SHRINK
        assert result.original_font_size == 36
        assert result.final_font_size == 24
        assert result.lines_used == 1
        assert result.content_truncated is False

    def test_default_truncated(self):
        """Test that content_truncated defaults to False."""
        result = AdjustmentResult(
            was_adjusted=False,
            strategy_applied=OverflowStrategy.AUTO,
            original_font_size=12,
            final_font_size=12,
            lines_used=1,
        )
        assert result.content_truncated is False


class TestTextElement:
    """Tests for TextElement model."""

    def test_valid_text_element(self):
        """Test creating a valid text element."""
        text = TextElement(content="Hello", x=1.0, y=2.0)
        assert text.content == "Hello"
        assert text.x == 1.0
        assert text.y == 2.0
        assert text.font_family == "Helvetica"  # default
        assert text.font_size == 12  # default

    def test_text_element_with_styling(self):
        """Test text element with full styling."""
        text = TextElement(
            content="Test",
            x=0.5,
            y=0.5,
            font_family="Times",
            font_size=24,
            font_style=FontStyle.BOLD,
            alignment=TextAlignment.CENTER,
            color=Color(r=1.0, g=0.0, b=0.0),
        )
        assert text.font_style == FontStyle.BOLD
        assert text.alignment == TextAlignment.CENTER

    def test_text_element_overflow_strategy_default(self):
        """Test that overflow_strategy defaults to AUTO."""
        text = TextElement(content="Test", x=0.0, y=0.0)
        assert text.overflow_strategy == OverflowStrategy.AUTO

    def test_text_element_overflow_strategy_validation(self):
        """Test that overflow_strategy validates correctly."""
        text = TextElement(
            content="Test",
            x=0.0,
            y=0.0,
            overflow_strategy=OverflowStrategy.SHRINK,
        )
        assert text.overflow_strategy == OverflowStrategy.SHRINK

    def test_text_element_min_font_size_default(self):
        """Test that min_font_size defaults to 8."""
        text = TextElement(content="Test", x=0.0, y=0.0)
        assert text.min_font_size == 8

    def test_text_element_max_lines_default(self):
        """Test that max_lines defaults to None."""
        text = TextElement(content="Test", x=0.0, y=0.0)
        assert text.max_lines is None

class TestPanel:
    """Tests for Panel model."""

    def test_valid_panel(self):
        """Test creating a valid panel."""
        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=4.25,
            height=5.5,
        )
        assert panel.position == PanelPosition.FRONT
        assert panel.width == 4.25
        assert panel.height == 5.5

    def test_panel_with_content(self):
        """Test panel with text and image elements."""
        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=4.25,
            height=5.5,
            text_elements=[TextElement(content="Hello", x=1.0, y=1.0)],
            background_color=Colors.WHITE,
        )
        assert len(panel.text_elements) == 1
        assert panel.background_color == Colors.WHITE

    def test_panel_bleed_default_is_inherit(self):
        """Panel.bleed defaults to None (inherit from card)."""
        panel = Panel(
            position=PanelPosition.FRONT, x=0, y=0, width=4.25, height=5.5,
        )
        assert panel.bleed is None

    def test_panel_bleed_accepts_explicit_value(self):
        panel = Panel(
            position=PanelPosition.FRONT,
            x=0, y=0, width=4.25, height=5.5,
            bleed=0.0625,
        )
        assert panel.bleed == 0.0625

    def test_panel_bleed_rejects_negative(self):
        with pytest.raises(ValidationError):
            Panel(
                position=PanelPosition.FRONT,
                x=0, y=0, width=4.25, height=5.5,
                bleed=-0.01,
            )

    def test_panel_bleed_rejects_excessive(self):
        # 0.5" cap protects against geometry mistakes (a half-inch bleed
        # would push past the sheet on most printers).
        with pytest.raises(ValidationError):
            Panel(
                position=PanelPosition.FRONT,
                x=0, y=0, width=4.25, height=5.5,
                bleed=0.6,
            )


class TestTemplate:
    """Tests for Template model."""

    def test_valid_template(self):
        """Test creating a valid template."""
        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=4.25,
            height=5.5,
        )
        template = Template(
            id="test-template",
            name="Test Template",
            occasion=OccasionType.CHRISTMAS,
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )
        assert template.id == "test-template"
        assert len(template.panels) == 1

    def test_template_requires_panels(self):
        """Test that template requires at least one panel."""
        with pytest.raises(ValidationError):
            Template(
                id="test",
                name="Test",
                occasion=OccasionType.GENERIC,
                fold_type=FoldType.HALF_FOLD,
                panels=[],
            )


class TestCard:
    """Tests for Card model."""

    def test_valid_card(self):
        """Test creating a valid card."""
        panel = Panel(
            position=PanelPosition.FRONT,
            x=0.0,
            y=0.0,
            width=4.25,
            height=5.5,
        )
        card = Card(
            name="My Card",
            template_id="test-template",
            fold_type=FoldType.HALF_FOLD,
            panels=[panel],
        )
        assert card.name == "My Card"
        assert card.template_id == "test-template"

    def test_card_bleed_defaults_to_industry_standard(self):
        panel = Panel(position=PanelPosition.FRONT, x=0, y=0, width=4.25, height=5.5)
        card = Card(
            name="X", template_id="t", fold_type=FoldType.HALF_FOLD, panels=[panel],
        )
        assert card.bleed == 0.125

    def test_card_bleed_accepts_zero(self):
        panel = Panel(position=PanelPosition.FRONT, x=0, y=0, width=4.25, height=5.5)
        card = Card(
            name="X", template_id="t", fold_type=FoldType.HALF_FOLD, bleed=0.0,
            panels=[panel],
        )
        assert card.bleed == 0.0

    def test_card_bleed_rejects_out_of_range(self):
        panel = Panel(position=PanelPosition.FRONT, x=0, y=0, width=4.25, height=5.5)
        with pytest.raises(ValidationError):
            Card(
                name="X", template_id="t", fold_type=FoldType.HALF_FOLD,
                bleed=-0.1, panels=[panel],
            )
        with pytest.raises(ValidationError):
            Card(
                name="X", template_id="t", fold_type=FoldType.HALF_FOLD,
                bleed=0.7, panels=[panel],
            )


class TestTheme:
    """Tests for Theme model."""

    def test_valid_theme(self):
        """Test creating a valid theme."""
        theme = Theme(
            id="test-theme",
            name="Test Theme",
            occasion=OccasionType.CHRISTMAS,
            primary=Colors.RED,
            secondary=Colors.GREEN,
        )
        assert theme.id == "test-theme"
        assert theme.primary == Colors.RED


# ---------------------------------------------------------------------------
# #81: invariants hold on assignment, not only at construction (D4)
# ---------------------------------------------------------------------------


def _panel(**kwargs: object) -> Panel:
    return Panel(position=PanelPosition.FRONT, width=4.25, height=5.5, **kwargs)  # type: ignore[arg-type]


def _letter() -> LetterContent:
    return LetterContent(salutation="Dear M,", body="Hello", signoff="Love,", signature="C")


def _rich() -> RichTextContent:
    return parse_markdown("Hello **there**")


class TestValidateAssignment:
    """Every mutable domain model validates on assignment (#81)."""

    def test_rich_content_on_a_letter_element_raises(self) -> None:
        text = TextElement(content="", x=0, y=0, letter_content=_letter())
        with pytest.raises(ValidationError, match="mutually exclusive"):
            text.rich_content = _rich()

    def test_font_size_above_the_limit_raises(self) -> None:
        text = TextElement(content="x", x=0, y=0)
        with pytest.raises(ValidationError):
            text.font_size = 500
        assert text.font_size == 12

    def test_panel_background_color_must_be_a_color(self) -> None:
        panel = _panel()
        with pytest.raises(ValidationError):
            panel.background_color = "red"  # type: ignore[assignment]

    def test_card_panels_cannot_be_emptied(self) -> None:
        card = Card(name="c", template_id="t", fold_type=FoldType.QUARTER_FOLD, panels=[_panel()])
        with pytest.raises(ValidationError, match="at least one panel"):
            card.panels = []

    def test_color_component_out_of_range_raises(self) -> None:
        color = Color(r=0.1, g=0.2, b=0.3)
        with pytest.raises(ValidationError):
            color.r = 2.0

    def test_theme_color_must_be_a_color(self) -> None:
        theme = Theme(
            id="t", name="T", occasion=OccasionType.CHRISTMAS,
            primary=Colors.RED, secondary=Colors.GREEN,
        )
        with pytest.raises(ValidationError):
            theme.primary = "red"  # type: ignore[assignment]

    def test_shape_stroke_width_is_checked(self) -> None:
        shape = Rectangle(x=0, y=0, width=1, height=1)
        with pytest.raises(ValidationError):
            shape.stroke_width = -1

    def test_panel_image_elements_are_validated_on_reassignment(self) -> None:
        panel = _panel()
        with pytest.raises(ValidationError):
            panel.image_elements = [*panel.image_elements, "not an image"]  # type: ignore[list-item]

    @pytest.mark.parametrize("name", _MUTABLE_MODEL_NAMES)
    def test_every_mutable_model_validates_assignment(self, name: str) -> None:
        cls = getattr(models, name)
        assert cls.model_config.get("validate_assignment") is True, name

    @pytest.mark.parametrize("name", _MUTABLE_MODEL_NAMES)
    def test_every_mutable_model_forbids_extra_keys(self, name: str) -> None:
        cls = getattr(models, name)
        assert cls.model_config.get("extra") == "forbid", name

    def test_the_mutable_model_list_is_not_empty(self) -> None:
        assert {"Card", "Panel", "TextElement", "Theme", "Rectangle"} <= set(_MUTABLE_MODEL_NAMES)


class TestWithInsideContent:
    """``TextElement.with_inside_content`` sets exactly one surface (#81)."""

    @staticmethod
    def _surfaces(text: TextElement) -> list[str]:
        set_ = []
        if text.letter_content is not None:
            set_.append("letter")
        if text.rich_content is not None:
            set_.append("rich")
        if text.content:
            set_.append("plain")
        return set_

    def test_with_inside_content_clears_other_surfaces(self) -> None:
        text = TextElement(id="message", content="old", x=1, y=2, font_family="Lato")
        text = text.with_inside_content(letter=_letter())
        assert self._surfaces(text) == ["letter"]
        text = text.with_inside_content(rich=_rich())
        assert self._surfaces(text) == ["rich"]
        text = text.with_inside_content(content="plain")
        assert self._surfaces(text) == ["plain"]
        text = text.with_inside_content(letter=_letter())
        assert self._surfaces(text) == ["letter"]
        assert (text.id, text.x, text.y, text.font_family) == ("message", 1, 2, "Lato")

    def test_with_inside_content_returns_a_copy(self) -> None:
        text = TextElement(content="old", x=0, y=0)
        new = text.with_inside_content(content="new")
        assert new is not text
        assert text.content == "old"

    def test_with_inside_content_refuses_two_surfaces(self) -> None:
        text = TextElement(content="", x=0, y=0)
        with pytest.raises(ValidationError, match="mutually exclusive"):
            text.with_inside_content(rich=_rich(), letter=_letter())


class TestCardHasNoTimestamps:
    """``created_at`` / ``updated_at`` had no reader (D17, #81)."""

    def test_card_has_no_timestamp_fields(self) -> None:
        assert "created_at" not in Card.model_fields
        assert "updated_at" not in Card.model_fields
