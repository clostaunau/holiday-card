"""Unit tests for input validators."""

from pathlib import Path

import pytest

from holiday_card.utils.validators import (
    ValidationError,
    validate_color_component,
    validate_color_rgb,
    validate_dimensions,
    validate_dpi,
    validate_font_size,
    validate_image_format,
    validate_position,
    validate_template_name,
)


class TestColorValidation:
    """Tests for color validation functions."""

    def test_valid_color_component(self):
        """Test valid color component values."""
        assert validate_color_component(0.0) == 0.0
        assert validate_color_component(0.5) == 0.5
        assert validate_color_component(1.0) == 1.0

    def test_invalid_color_component(self):
        """Test invalid color component values."""
        with pytest.raises(ValidationError):
            validate_color_component(-0.1)
        with pytest.raises(ValidationError):
            validate_color_component(1.1)

    def test_valid_color_rgb(self):
        """Test valid RGB color."""
        result = validate_color_rgb(0.5, 0.5, 0.5)
        assert result == (0.5, 0.5, 0.5)

    def test_invalid_color_rgb(self):
        """Test invalid RGB color."""
        with pytest.raises(ValidationError):
            validate_color_rgb(1.5, 0.5, 0.5)


class TestDimensionValidation:
    """Tests for dimension validation functions."""

    def test_valid_dimensions(self):
        """Test valid dimensions."""
        result = validate_dimensions(4.25, 5.5)
        assert result == (4.25, 5.5)

    def test_zero_dimensions(self):
        """Test that zero dimensions are invalid."""
        with pytest.raises(ValidationError):
            validate_dimensions(0, 5.5)
        with pytest.raises(ValidationError):
            validate_dimensions(4.25, 0)

    def test_negative_dimensions(self):
        """Test that negative dimensions are invalid."""
        with pytest.raises(ValidationError):
            validate_dimensions(-1, 5.5)

    def test_exceeding_max_dimensions(self):
        """Test dimensions exceeding maximum."""
        with pytest.raises(ValidationError):
            validate_dimensions(100, 5.5)


class TestPositionValidation:
    """Tests for position validation functions."""

    def test_valid_position(self):
        """Test valid positions."""
        result = validate_position(1.0, 1.0)
        assert result == (1.0, 1.0)

    def test_position_with_margins(self):
        """Test position respecting margins."""
        # Should work within margins
        result = validate_position(0.5, 0.5)
        assert result == (0.5, 0.5)


class TestFontSizeValidation:
    """Tests for font size validation."""

    def test_valid_font_sizes(self):
        """Test valid font sizes."""
        assert validate_font_size(12) == 12
        assert validate_font_size(6) == 6
        assert validate_font_size(144) == 144

    def test_too_small_font_size(self):
        """Test font size below minimum."""
        with pytest.raises(ValidationError):
            validate_font_size(5)

    def test_too_large_font_size(self):
        """Test font size above maximum."""
        with pytest.raises(ValidationError):
            validate_font_size(145)


class TestImageValidation:
    """Tests for image validation functions."""

    def test_valid_image_formats(self):
        """Test valid image formats."""
        assert validate_image_format(Path("test.png")) == "png"
        assert validate_image_format(Path("test.jpg")) == "jpg"
        assert validate_image_format(Path("test.jpeg")) == "jpeg"

    def test_invalid_image_format(self):
        """Test invalid image format."""
        with pytest.raises(ValidationError):
            validate_image_format(Path("test.gif"))
        with pytest.raises(ValidationError):
            validate_image_format(Path("test.bmp"))

    def test_dpi_warning(self):
        """Test DPI validation with warning."""
        warning = validate_dpi(72, warn_only=True)
        assert warning is not None
        assert "below recommended" in warning

    def test_valid_dpi(self):
        """Test valid DPI values."""
        result = validate_dpi(150)
        assert result is None  # No warning

    def test_dpi_error(self):
        """Test DPI validation with error."""
        with pytest.raises(ValidationError):
            validate_dpi(72, warn_only=False)


class TestTemplateNameValidation:
    """Tests for template name validation."""

    def test_valid_template_names(self):
        """Test valid template names."""
        assert validate_template_name("test") == "test"
        assert validate_template_name("my-template") == "my-template"
        assert validate_template_name("template_123") == "template_123"

    def test_empty_template_name(self):
        """Test empty template name."""
        with pytest.raises(ValidationError):
            validate_template_name("")

    def test_too_long_template_name(self):
        """Test template name exceeding maximum length."""
        with pytest.raises(ValidationError):
            validate_template_name("a" * 51)

    def test_invalid_characters(self):
        """Test template name with invalid characters."""
        with pytest.raises(ValidationError):
            validate_template_name("test@template")
