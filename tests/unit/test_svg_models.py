"""Unit tests for SVG path model validation."""

import pytest
from pydantic import ValidationError

from holiday_card.core.models import ShapeType, SVGPath


class TestSVGPath:
    """Tests for SVGPath model."""

    def test_valid_svg_path(self):
        """Test creating a valid SVG path."""
        path = SVGPath(
            path_data="M 10 10 L 20 20 Z",
            fill_color="#FF0000",
            stroke_color="#000000",
            stroke_width=2.0
        )

        assert path.type == ShapeType.SVG_PATH
        assert path.path_data == "M 10 10 L 20 20 Z"
        assert path.scale == 1.0
        assert path.fill_color == "#FF0000"

    def test_svg_path_with_scale(self):
        """Test SVG path with custom scale."""
        path = SVGPath(
            path_data="M 0 0 L 10 10",
            scale=2.5
        )

        assert path.scale == 2.5

    def test_svg_path_scale_validation_min(self):
        """Test that scale must be greater than 0."""
        with pytest.raises(ValidationError):
            SVGPath(path_data="M 0 0 L 10 10", scale=0.0)

    def test_svg_path_scale_validation_max(self):
        """Test that scale cannot exceed 10.0."""
        with pytest.raises(ValidationError):
            SVGPath(path_data="M 0 0 L 10 10", scale=11.0)

    def test_svg_path_empty_data_validation(self):
        """Test that empty path data raises ValidationError."""
        with pytest.raises(ValidationError, match="at least 1 character"):
            SVGPath(path_data="")

    def test_svg_path_whitespace_only_validation(self):
        """Test that whitespace-only path data raises ValidationError."""
        with pytest.raises(ValidationError, match="empty"):
            SVGPath(path_data="   ")

    def test_svg_path_no_commands_validation(self):
        """Test that path data without commands raises ValidationError."""
        with pytest.raises(ValidationError, match="valid command"):
            SVGPath(path_data="10 20 30 40")

    def test_svg_path_with_move_command(self):
        """Test path with only move command."""
        path = SVGPath(path_data="M 10 10")
        assert path.path_data == "M 10 10"

    def test_svg_path_with_line_commands(self):
        """Test path with line commands."""
        path = SVGPath(path_data="M 10 10 L 20 20 L 30 10")
        assert "L" in path.path_data

    def test_svg_path_with_curve_commands(self):
        """Test path with cubic Bezier curves."""
        path = SVGPath(path_data="M 10 10 C 20 20 30 20 40 10")
        assert "C" in path.path_data

    def test_svg_path_with_quadratic_curve(self):
        """Test path with quadratic Bezier curves."""
        path = SVGPath(path_data="M 10 10 Q 20 20 30 10")
        assert "Q" in path.path_data

    def test_svg_path_with_arc_command(self):
        """Test path with elliptical arc."""
        path = SVGPath(path_data="M 10 10 A 5 5 0 0 1 20 20")
        assert "A" in path.path_data

    def test_svg_path_with_close_command(self):
        """Test path with close command."""
        path = SVGPath(path_data="M 10 10 L 20 20 Z")
        assert path.path_data.endswith("Z")

    def test_svg_path_relative_commands(self):
        """Test path with relative commands."""
        path = SVGPath(path_data="m 10 10 l 20 20 z")
        assert "m" in path.path_data
        assert "l" in path.path_data

    def test_svg_path_with_fill_style(self):
        """Test SVG path with fill style."""
        from holiday_card.core.models import SolidFill

        path = SVGPath(
            path_data="M 0 0 L 10 10 Z",
            fill=SolidFill(color="#FF0000")
        )

        assert path.fill is not None
        assert path.fill.type == "solid"

    def test_svg_path_with_gradient_fill(self):
        """Test SVG path with gradient fill."""
        from holiday_card.core.models import ColorStop, LinearGradientFill

        path = SVGPath(
            path_data="M 0 0 L 10 10 Z",
            fill=LinearGradientFill(
                angle=45.0,
                stops=[
                    ColorStop(position=0.0, color="#FF0000"),
                    ColorStop(position=1.0, color="#0000FF")
                ]
            )
        )

        assert path.fill.type == "linear_gradient"
        assert len(path.fill.stops) == 2

    def test_svg_path_backward_compatibility_fill_color(self):
        """Test that legacy fill_color still works."""
        path = SVGPath(
            path_data="M 0 0 L 10 10 Z",
            fill_color="#FF0000"
        )

        assert path.fill_color == "#FF0000"

    def test_svg_path_with_rotation(self):
        """Test SVG path with rotation."""
        path = SVGPath(
            path_data="M 0 0 L 10 10 Z",
            rotation=45.0
        )

        assert path.rotation == 45.0

    def test_svg_path_with_opacity(self):
        """Test SVG path with opacity."""
        path = SVGPath(
            path_data="M 0 0 L 10 10 Z",
            opacity=0.5
        )

        assert path.opacity == 0.5

    def test_svg_path_z_index(self):
        """Test SVG path with z_index."""
        path = SVGPath(
            path_data="M 0 0 L 10 10 Z",
            z_index=10
        )

        assert path.z_index == 10

    def test_svg_path_complex_data(self):
        """Test SVG path with complex path data."""
        # Holly leaf path (simplified)
        path_data = "M 10 20 C 15 10 25 10 30 20 C 35 15 40 15 45 20 L 40 30 C 35 25 25 25 20 30 Z"
        path = SVGPath(path_data=path_data)

        assert path.path_data == path_data
        assert "C" in path.path_data
        assert "Z" in path.path_data
