"""Unit tests for measurement utilities."""


from holiday_card.utils.measurements import (
    FOLD_LINE_WIDTH,
    MIN_DPI,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    POINTS_PER_INCH,
    SAFE_MARGIN,
    inches_to_points,
    points_to_inches,
)


class TestConstants:
    """Tests for measurement constants."""

    def test_page_dimensions(self):
        """Test standard page dimensions."""
        assert PAGE_WIDTH == 8.5
        assert PAGE_HEIGHT == 11.0

    def test_safe_margin(self):
        """Test safe margin constant."""
        assert SAFE_MARGIN == 0.25

    def test_points_per_inch(self):
        """Test points per inch constant."""
        assert POINTS_PER_INCH == 72.0

    def test_min_dpi(self):
        """Test minimum DPI constant."""
        assert MIN_DPI == 150

    def test_fold_line_width(self):
        """Test fold line width constant."""
        assert FOLD_LINE_WIDTH > 0


class TestConversions:
    """Tests for unit conversion functions."""

    def test_inches_to_points(self):
        """Test inches to points conversion."""
        assert inches_to_points(1.0) == 72.0
        assert inches_to_points(0.5) == 36.0
        assert inches_to_points(8.5) == 612.0

    def test_points_to_inches(self):
        """Test points to inches conversion."""
        assert points_to_inches(72.0) == 1.0
        assert points_to_inches(36.0) == 0.5
        assert points_to_inches(612.0) == 8.5

    def test_conversion_roundtrip(self):
        """Test that conversion is reversible."""
        original = 5.5
        points = inches_to_points(original)
        result = points_to_inches(points)
        assert result == original

    def test_page_dimensions_in_points(self):
        """Test page dimensions converted to points."""
        width_pts = inches_to_points(PAGE_WIDTH)
        height_pts = inches_to_points(PAGE_HEIGHT)
        # Letter size in points is 612 x 792
        assert width_pts == 612.0
        assert height_pts == 792.0
