"""Unit tests for core domain models."""

import pytest
from pydantic import ValidationError

from holiday_card.core.models import (
    Border,
    BorderStyle,
    Card,
    Color,
    Colors,
    FoldType,
    FontStyle,
    ImageElement,
    OccasionType,
    Panel,
    PanelPosition,
    Template,
    TextAlignment,
    TextElement,
    Theme,
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
