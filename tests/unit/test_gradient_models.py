"""Unit tests for gradient fill models."""

import pytest
from pydantic import ValidationError

from holiday_card.core.models import (
    ColorStop,
    LinearGradientFill,
    RadialGradientFill,
    SolidFill,
)


class TestColorStop:
    """Tests for ColorStop model."""

    def test_valid_color_stop(self):
        """Test creating a valid color stop."""
        stop = ColorStop(position=0.5, color="#FF0000")

        assert stop.position == 0.5
        assert stop.color == "#FF0000"

    def test_color_stop_position_zero(self):
        """Test color stop at position 0.0."""
        stop = ColorStop(position=0.0, color="#000000")
        assert stop.position == 0.0

    def test_color_stop_position_one(self):
        """Test color stop at position 1.0."""
        stop = ColorStop(position=1.0, color="#FFFFFF")
        assert stop.position == 1.0

    def test_color_stop_position_below_zero_fails(self):
        """Test that position < 0.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            ColorStop(position=-0.1, color="#FF0000")

    def test_color_stop_position_above_one_fails(self):
        """Test that position > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            ColorStop(position=1.1, color="#FF0000")

    def test_color_stop_hex_validation_with_hash(self):
        """Test that hex color with # is validated."""
        stop = ColorStop(position=0.5, color="#FF0000")
        assert stop.color == "#FF0000"

    def test_color_stop_hex_validation_without_hash(self):
        """Test that hex color without # is prefixed."""
        stop = ColorStop(position=0.5, color="FF0000")
        assert stop.color == "#FF0000"

    def test_color_stop_invalid_hex_length(self):
        """Test that invalid hex length raises ValidationError."""
        with pytest.raises(ValidationError, match="7 characters"):
            ColorStop(position=0.5, color="#FFF")

    def test_color_stop_invalid_hex_characters(self):
        """Test that invalid hex characters raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid hex color"):
            ColorStop(position=0.5, color="#GGGGGG")


class TestSolidFill:
    """Tests for SolidFill model."""

    def test_valid_solid_fill(self):
        """Test creating a valid solid fill."""
        fill = SolidFill(color="#FF0000")

        assert fill.type == "solid"
        assert fill.color == "#FF0000"

    def test_solid_fill_hex_without_hash(self):
        """Test solid fill accepts hex without #."""
        fill = SolidFill(color="0000FF")
        assert fill.color == "#0000FF"

    def test_solid_fill_invalid_hex(self):
        """Test that invalid hex raises ValidationError."""
        with pytest.raises(ValidationError):
            SolidFill(color="#GGG")


class TestLinearGradientFill:
    """Tests for LinearGradientFill model."""

    def test_valid_linear_gradient(self):
        """Test creating a valid linear gradient."""
        gradient = LinearGradientFill(
            angle=45.0,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

        assert gradient.type == "linear_gradient"
        assert gradient.angle == 45.0
        assert len(gradient.stops) == 2

    def test_linear_gradient_default_angle(self):
        """Test linear gradient with default angle."""
        gradient = LinearGradientFill(
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

        assert gradient.angle == 0.0

    def test_linear_gradient_angle_range(self):
        """Test linear gradient angle validation."""
        # Valid angles
        LinearGradientFill(
            angle=0.0,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

        LinearGradientFill(
            angle=359.9,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

    def test_linear_gradient_angle_negative_fails(self):
        """Test that negative angle raises ValidationError."""
        with pytest.raises(ValidationError):
            LinearGradientFill(
                angle=-1.0,
                stops=[
                    ColorStop(position=0.0, color="#FF0000"),
                    ColorStop(position=1.0, color="#0000FF")
                ]
            )

    def test_linear_gradient_angle_360_fails(self):
        """Test that angle >= 360 raises ValidationError."""
        with pytest.raises(ValidationError):
            LinearGradientFill(
                angle=360.0,
                stops=[
                    ColorStop(position=0.0, color="#FF0000"),
                    ColorStop(position=1.0, color="#0000FF")
                ]
            )

    def test_linear_gradient_minimum_stops(self):
        """Test that gradient requires at least 2 stops."""
        with pytest.raises(ValidationError):
            LinearGradientFill(
                angle=0.0,
                stops=[ColorStop(position=0.0, color="#FF0000")]
            )

    def test_linear_gradient_maximum_stops(self):
        """Test that gradient cannot have more than 20 stops."""
        stops = [
            ColorStop(position=i/21, color="#FF0000")
            for i in range(21)
        ]

        with pytest.raises(ValidationError):
            LinearGradientFill(angle=0.0, stops=stops)

    def test_linear_gradient_stops_ascending_order(self):
        """Test that stops must be in ascending position order."""
        with pytest.raises(ValidationError, match="ascending"):
            LinearGradientFill(
                angle=0.0,
                stops=[
                    ColorStop(position=1.0, color="#FF0000"),
                    ColorStop(position=0.0, color="#0000FF")
                ]
            )

    def test_linear_gradient_multiple_stops(self):
        """Test gradient with multiple color stops."""
        gradient = LinearGradientFill(
            angle=90.0,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=0.5, color="#00FF00"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

        assert len(gradient.stops) == 3
        assert gradient.stops[1].color == "#00FF00"


class TestRadialGradientFill:
    """Tests for RadialGradientFill model."""

    def test_valid_radial_gradient(self):
        """Test creating a valid radial gradient."""
        gradient = RadialGradientFill(
            center_x=0.5,
            center_y=0.5,
            radius=0.5,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

        assert gradient.type == "radial_gradient"
        assert gradient.center_x == 0.5
        assert gradient.center_y == 0.5
        assert gradient.radius == 0.5

    def test_radial_gradient_default_center(self):
        """Test radial gradient with default center."""
        gradient = RadialGradientFill(
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

        assert gradient.center_x == 0.5
        assert gradient.center_y == 0.5
        assert gradient.radius == 0.5

    def test_radial_gradient_center_range(self):
        """Test radial gradient center validation."""
        # Center at origin
        RadialGradientFill(
            center_x=0.0,
            center_y=0.0,
            radius=0.5,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

        # Center at corner
        RadialGradientFill(
            center_x=1.0,
            center_y=1.0,
            radius=0.5,
            stops=[
                ColorStop(position=0.0, color="#FF0000"),
                ColorStop(position=1.0, color="#0000FF")
            ]
        )

    def test_radial_gradient_center_below_zero_fails(self):
        """Test that center < 0.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            RadialGradientFill(
                center_x=-0.1,
                center_y=0.5,
                radius=0.5,
                stops=[
                    ColorStop(position=0.0, color="#FF0000"),
                    ColorStop(position=1.0, color="#0000FF")
                ]
            )

    def test_radial_gradient_center_above_one_fails(self):
        """Test that center > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            RadialGradientFill(
                center_x=0.5,
                center_y=1.1,
                radius=0.5,
                stops=[
                    ColorStop(position=0.0, color="#FF0000"),
                    ColorStop(position=1.0, color="#0000FF")
                ]
            )

    def test_radial_gradient_radius_zero_fails(self):
        """Test that radius = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            RadialGradientFill(
                center_x=0.5,
                center_y=0.5,
                radius=0.0,
                stops=[
                    ColorStop(position=0.0, color="#FF0000"),
                    ColorStop(position=1.0, color="#0000FF")
                ]
            )

    def test_radial_gradient_radius_above_one_fails(self):
        """Test that radius > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            RadialGradientFill(
                center_x=0.5,
                center_y=0.5,
                radius=1.1,
                stops=[
                    ColorStop(position=0.0, color="#FF0000"),
                    ColorStop(position=1.0, color="#0000FF")
                ]
            )

    def test_radial_gradient_stops_ascending_order(self):
        """Test that stops must be in ascending position order."""
        with pytest.raises(ValidationError, match="ascending"):
            RadialGradientFill(
                stops=[
                    ColorStop(position=0.5, color="#FF0000"),
                    ColorStop(position=0.0, color="#0000FF")
                ]
            )

    def test_radial_gradient_minimum_stops(self):
        """Test that gradient requires at least 2 stops."""
        with pytest.raises(ValidationError):
            RadialGradientFill(
                stops=[ColorStop(position=0.0, color="#FF0000")]
            )
