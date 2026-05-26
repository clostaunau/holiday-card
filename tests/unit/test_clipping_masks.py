"""Unit tests for clipping mask models."""

import pytest
from pydantic import ValidationError

from holiday_card.core.models import (
    CircleClipMask,
    EllipseClipMask,
    RectangleClipMask,
    StarClipMask,
)


class TestCircleClipMask:
    """Tests for CircleClipMask model."""

    def test_circle_clip_mask_valid(self):
        """Test creating a valid circular clipping mask."""
        mask = CircleClipMask(
            center_x=1.5,
            center_y=2.0,
            radius=1.0
        )

        assert mask.type == "circle"
        assert mask.center_x == 1.5
        assert mask.center_y == 2.0
        assert mask.radius == 1.0

    def test_circle_clip_mask_zero_radius_fails(self):
        """Test that radius = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            CircleClipMask(
                center_x=1.0,
                center_y=1.0,
                radius=0.0
            )

    def test_circle_clip_mask_negative_radius_fails(self):
        """Test that negative radius raises ValidationError."""
        with pytest.raises(ValidationError):
            CircleClipMask(
                center_x=1.0,
                center_y=1.0,
                radius=-0.5
            )

    def test_circle_clip_mask_negative_center_x_fails(self):
        """Test that negative center_x raises ValidationError."""
        with pytest.raises(ValidationError):
            CircleClipMask(
                center_x=-1.0,
                center_y=1.0,
                radius=1.0
            )

    def test_circle_clip_mask_negative_center_y_fails(self):
        """Test that negative center_y raises ValidationError."""
        with pytest.raises(ValidationError):
            CircleClipMask(
                center_x=1.0,
                center_y=-1.0,
                radius=1.0
            )

    def test_circle_clip_mask_large_radius(self):
        """Test that large radius values are allowed."""
        mask = CircleClipMask(
            center_x=5.0,
            center_y=5.0,
            radius=10.0
        )

        assert mask.radius == 10.0

    def test_circle_clip_mask_small_radius(self):
        """Test that very small radius values are allowed."""
        mask = CircleClipMask(
            center_x=1.0,
            center_y=1.0,
            radius=0.01
        )

        assert mask.radius == 0.01


class TestRectangleClipMask:
    """Tests for RectangleClipMask model."""

    def test_rectangle_clip_mask_valid(self):
        """Test creating a valid rectangular clipping mask."""
        mask = RectangleClipMask(
            x=0.5,
            y=0.5,
            width=3.0,
            height=2.0
        )

        assert mask.type == "rectangle"
        assert mask.x == 0.5
        assert mask.y == 0.5
        assert mask.width == 3.0
        assert mask.height == 2.0

    def test_rectangle_clip_mask_zero_width_fails(self):
        """Test that width = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            RectangleClipMask(
                x=0.0,
                y=0.0,
                width=0.0,
                height=2.0
            )

    def test_rectangle_clip_mask_zero_height_fails(self):
        """Test that height = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            RectangleClipMask(
                x=0.0,
                y=0.0,
                width=2.0,
                height=0.0
            )

    def test_rectangle_clip_mask_negative_width_fails(self):
        """Test that negative width raises ValidationError."""
        with pytest.raises(ValidationError):
            RectangleClipMask(
                x=0.0,
                y=0.0,
                width=-1.0,
                height=2.0
            )

    def test_rectangle_clip_mask_negative_height_fails(self):
        """Test that negative height raises ValidationError."""
        with pytest.raises(ValidationError):
            RectangleClipMask(
                x=0.0,
                y=0.0,
                width=2.0,
                height=-1.0
            )

    def test_rectangle_clip_mask_negative_x_fails(self):
        """Test that negative x raises ValidationError."""
        with pytest.raises(ValidationError):
            RectangleClipMask(
                x=-1.0,
                y=0.0,
                width=2.0,
                height=2.0
            )

    def test_rectangle_clip_mask_negative_y_fails(self):
        """Test that negative y raises ValidationError."""
        with pytest.raises(ValidationError):
            RectangleClipMask(
                x=0.0,
                y=-1.0,
                width=2.0,
                height=2.0
            )


class TestEllipseClipMask:
    """Tests for EllipseClipMask model."""

    def test_ellipse_clip_mask_valid(self):
        """Test creating a valid elliptical clipping mask."""
        mask = EllipseClipMask(
            center_x=2.0,
            center_y=1.5,
            radius_x=1.8,
            radius_y=1.2
        )

        assert mask.type == "ellipse"
        assert mask.center_x == 2.0
        assert mask.center_y == 1.5
        assert mask.radius_x == 1.8
        assert mask.radius_y == 1.2

    def test_ellipse_clip_mask_zero_radius_x_fails(self):
        """Test that radius_x = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            EllipseClipMask(
                center_x=1.0,
                center_y=1.0,
                radius_x=0.0,
                radius_y=1.0
            )

    def test_ellipse_clip_mask_zero_radius_y_fails(self):
        """Test that radius_y = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            EllipseClipMask(
                center_x=1.0,
                center_y=1.0,
                radius_x=1.0,
                radius_y=0.0
            )

    def test_ellipse_clip_mask_negative_radius_x_fails(self):
        """Test that negative radius_x raises ValidationError."""
        with pytest.raises(ValidationError):
            EllipseClipMask(
                center_x=1.0,
                center_y=1.0,
                radius_x=-0.5,
                radius_y=1.0
            )

    def test_ellipse_clip_mask_negative_radius_y_fails(self):
        """Test that negative radius_y raises ValidationError."""
        with pytest.raises(ValidationError):
            EllipseClipMask(
                center_x=1.0,
                center_y=1.0,
                radius_x=1.0,
                radius_y=-0.5
            )

    def test_ellipse_clip_mask_negative_center_x_fails(self):
        """Test that negative center_x raises ValidationError."""
        with pytest.raises(ValidationError):
            EllipseClipMask(
                center_x=-1.0,
                center_y=1.0,
                radius_x=1.0,
                radius_y=1.0
            )

    def test_ellipse_clip_mask_negative_center_y_fails(self):
        """Test that negative center_y raises ValidationError."""
        with pytest.raises(ValidationError):
            EllipseClipMask(
                center_x=1.0,
                center_y=-1.0,
                radius_x=1.0,
                radius_y=1.0
            )

    def test_ellipse_clip_mask_equal_radii_creates_circle(self):
        """Test that equal radii creates a circle-like ellipse."""
        mask = EllipseClipMask(
            center_x=1.0,
            center_y=1.0,
            radius_x=1.5,
            radius_y=1.5
        )

        assert mask.radius_x == mask.radius_y


class TestStarClipMask:
    """Tests for StarClipMask model."""

    def test_star_clip_mask_valid(self):
        """Test creating a valid star clipping mask."""
        mask = StarClipMask(
            center_x=2.0,
            center_y=1.5,
            points=5,
            outer_radius=1.4,
            inner_radius=0.7
        )

        assert mask.type == "star"
        assert mask.center_x == 2.0
        assert mask.center_y == 1.5
        assert mask.points == 5
        assert mask.outer_radius == 1.4
        assert mask.inner_radius == 0.7

    def test_star_clip_mask_six_points(self):
        """Test creating a 6-pointed star."""
        mask = StarClipMask(
            center_x=1.0,
            center_y=1.0,
            points=6,
            outer_radius=1.0,
            inner_radius=0.5
        )

        assert mask.points == 6

    def test_star_clip_mask_equal_radii_fails(self):
        """Test that inner_radius = outer_radius raises ValidationError."""
        with pytest.raises(ValidationError, match="inner_radius.*must be less than outer_radius"):
            StarClipMask(
                center_x=1.0,
                center_y=1.0,
                points=5,
                outer_radius=2.0,
                inner_radius=2.0
            )

    def test_star_clip_mask_inner_greater_than_outer_fails(self):
        """Test that inner_radius > outer_radius raises ValidationError."""
        with pytest.raises(ValidationError, match="inner_radius.*must be less than outer_radius"):
            StarClipMask(
                center_x=1.0,
                center_y=1.0,
                points=5,
                outer_radius=1.0,
                inner_radius=2.0
            )

    def test_star_clip_mask_too_few_points_fails(self):
        """Test that points < 3 raises ValidationError."""
        with pytest.raises(ValidationError):
            StarClipMask(
                center_x=1.0,
                center_y=1.0,
                points=2,
                outer_radius=2.0,
                inner_radius=1.0
            )

    def test_star_clip_mask_zero_points_fails(self):
        """Test that points = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            StarClipMask(
                center_x=1.0,
                center_y=1.0,
                points=0,
                outer_radius=2.0,
                inner_radius=1.0
            )

    def test_star_clip_mask_zero_outer_radius_fails(self):
        """Test that outer_radius = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            StarClipMask(
                center_x=1.0,
                center_y=1.0,
                points=5,
                outer_radius=0.0,
                inner_radius=0.5
            )

    def test_star_clip_mask_zero_inner_radius_fails(self):
        """Test that inner_radius = 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            StarClipMask(
                center_x=1.0,
                center_y=1.0,
                points=5,
                outer_radius=2.0,
                inner_radius=0.0
            )

    def test_star_clip_mask_negative_center_x_fails(self):
        """Test that negative center_x raises ValidationError."""
        with pytest.raises(ValidationError):
            StarClipMask(
                center_x=-1.0,
                center_y=1.0,
                points=5,
                outer_radius=2.0,
                inner_radius=1.0
            )

    def test_star_clip_mask_negative_center_y_fails(self):
        """Test that negative center_y raises ValidationError."""
        with pytest.raises(ValidationError):
            StarClipMask(
                center_x=1.0,
                center_y=-1.0,
                points=5,
                outer_radius=2.0,
                inner_radius=1.0
            )
