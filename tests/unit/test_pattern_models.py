"""Unit tests for pattern fill models."""

import pytest
from pydantic import ValidationError

from holiday_card.core.models import PatternFill, PatternType


class TestPatternFill:
    """Tests for PatternFill model."""

    def test_valid_stripe_pattern(self):
        """Test creating a valid stripe pattern."""
        pattern = PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["#FF0000", "#FFFFFF"]
        )

        assert pattern.type == "pattern"
        assert pattern.pattern_type == PatternType.STRIPES
        assert len(pattern.colors) == 2
        assert pattern.spacing == 0.25  # default
        assert pattern.scale == 1.0  # default

    def test_valid_dot_pattern(self):
        """Test creating a valid dot pattern."""
        pattern = PatternFill(
            pattern_type=PatternType.DOTS,
            colors=["#FF0000"]
        )

        assert pattern.pattern_type == PatternType.DOTS
        assert len(pattern.colors) == 1

    def test_valid_grid_pattern(self):
        """Test creating a valid grid pattern."""
        pattern = PatternFill(
            pattern_type=PatternType.GRID,
            colors=["#000000"]
        )

        assert pattern.pattern_type == PatternType.GRID

    def test_valid_checkerboard_pattern(self):
        """Test creating a valid checkerboard pattern."""
        pattern = PatternFill(
            pattern_type=PatternType.CHECKERBOARD,
            colors=["#000000", "#FFFFFF"]
        )

        assert pattern.pattern_type == PatternType.CHECKERBOARD

    def test_pattern_with_custom_spacing(self):
        """Test pattern with custom spacing."""
        pattern = PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["#FF0000"],
            spacing=0.5
        )

        assert pattern.spacing == 0.5

    def test_pattern_with_custom_scale(self):
        """Test pattern with custom scale."""
        pattern = PatternFill(
            pattern_type=PatternType.DOTS,
            colors=["#FF0000"],
            scale=2.0
        )

        assert pattern.scale == 2.0

    def test_pattern_with_rotation(self):
        """Test pattern with rotation."""
        pattern = PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["#FF0000"],
            rotation=45.0
        )

        assert pattern.rotation == 45.0

    def test_pattern_spacing_minimum_fails(self):
        """Test that spacing <= 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            PatternFill(
                pattern_type=PatternType.STRIPES,
                colors=["#FF0000"],
                spacing=0.0
            )

    def test_pattern_spacing_maximum_fails(self):
        """Test that spacing > 2.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            PatternFill(
                pattern_type=PatternType.STRIPES,
                colors=["#FF0000"],
                spacing=2.1
            )

    def test_pattern_scale_minimum_fails(self):
        """Test that scale <= 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            PatternFill(
                pattern_type=PatternType.DOTS,
                colors=["#FF0000"],
                scale=0.0
            )

    def test_pattern_scale_maximum_fails(self):
        """Test that scale > 5.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            PatternFill(
                pattern_type=PatternType.DOTS,
                colors=["#FF0000"],
                scale=5.1
            )

    def test_pattern_rotation_negative_fails(self):
        """Test that rotation < 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            PatternFill(
                pattern_type=PatternType.STRIPES,
                colors=["#FF0000"],
                rotation=-1.0
            )

    def test_pattern_rotation_360_fails(self):
        """Test that rotation >= 360 raises ValidationError."""
        with pytest.raises(ValidationError):
            PatternFill(
                pattern_type=PatternType.STRIPES,
                colors=["#FF0000"],
                rotation=360.0
            )

    def test_pattern_no_colors_fails(self):
        """Test that pattern requires at least 1 color."""
        with pytest.raises(ValidationError):
            PatternFill(
                pattern_type=PatternType.STRIPES,
                colors=[]
            )

    def test_pattern_too_many_colors_fails(self):
        """Test that pattern cannot have more than 4 colors."""
        with pytest.raises(ValidationError):
            PatternFill(
                pattern_type=PatternType.CHECKERBOARD,
                colors=["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"]
            )

    def test_pattern_hex_validation_with_hash(self):
        """Test that hex colors with # are validated."""
        pattern = PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["#FF0000", "#00FF00"]
        )

        assert pattern.colors[0] == "#FF0000"
        assert pattern.colors[1] == "#00FF00"

    def test_pattern_hex_validation_without_hash(self):
        """Test that hex colors without # are prefixed."""
        pattern = PatternFill(
            pattern_type=PatternType.STRIPES,
            colors=["FF0000", "00FF00"]
        )

        assert pattern.colors[0] == "#FF0000"
        assert pattern.colors[1] == "#00FF00"

    def test_pattern_invalid_hex_length_fails(self):
        """Test that invalid hex length raises ValidationError."""
        with pytest.raises(ValidationError, match="7 characters"):
            PatternFill(
                pattern_type=PatternType.STRIPES,
                colors=["#FFF"]
            )

    def test_pattern_invalid_hex_characters_fails(self):
        """Test that invalid hex characters raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid hex color"):
            PatternFill(
                pattern_type=PatternType.STRIPES,
                colors=["#GGGGGG"]
            )

    def test_pattern_with_multiple_colors(self):
        """Test pattern with multiple colors."""
        pattern = PatternFill(
            pattern_type=PatternType.CHECKERBOARD,
            colors=["#FF0000", "#00FF00", "#0000FF"]
        )

        assert len(pattern.colors) == 3
