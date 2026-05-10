"""Unit tests for measurement utilities."""


import pytest

from holiday_card.utils.measurements import (
    DEFAULT_BLEED,
    FOLD_LINE_WIDTH,
    MIN_DPI,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    POINTS_PER_INCH,
    SAFE_MARGIN,
    PageGeometry,
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


class TestPageGeometryNoBleed:
    """``PageGeometry`` collapses to flat trim==media when bleed==0."""

    @pytest.fixture
    def geom(self) -> PageGeometry:
        return PageGeometry.us_letter(bleed_in=0.0)

    def test_all_boxes_equal_when_no_bleed(self, geom: PageGeometry) -> None:
        # ArtBox is inset by SAFE_MARGIN, so it's smaller than the rest.
        # Media / Trim / Bleed all collapse to the same rect when bleed=0.
        assert geom.media_box_pts == (0.0, 0.0, 612.0, 792.0)
        assert geom.trim_box_pts == (0.0, 0.0, 612.0, 792.0)
        assert geom.bleed_box_pts == (0.0, 0.0, 612.0, 792.0)

    def test_art_box_is_inset_by_safe_margin(self, geom: PageGeometry) -> None:
        margin_pt = inches_to_points(SAFE_MARGIN)
        x, y, w, h = geom.art_box_pts
        assert (x, y) == (margin_pt, margin_pt)
        assert w == 612.0 - 2 * margin_pt
        assert h == 792.0 - 2 * margin_pt


class TestPageGeometryWithBleed:
    """``PageGeometry`` with the industry-standard 0.125" bleed."""

    @pytest.fixture
    def geom(self) -> PageGeometry:
        return PageGeometry.us_letter()  # default bleed = 0.125"

    def test_default_bleed_matches_industry_standard(self, geom: PageGeometry) -> None:
        assert geom.bleed_in == DEFAULT_BLEED == 0.125
        assert geom.bleed_pts == 9.0

    def test_media_box_extends_past_trim_on_every_side(self, geom: PageGeometry) -> None:
        # Trim is 612 x 792 pt; bleed adds 9 pt on every side.
        x, y, w, h = geom.media_box_pts
        assert (x, y) == (0.0, 0.0)
        assert w == 612.0 + 18.0
        assert h == 792.0 + 18.0

    def test_trim_box_is_offset_by_bleed(self, geom: PageGeometry) -> None:
        # TrimBox sits inside the MediaBox, anchored at (bleed, bleed).
        x, y, w, h = geom.trim_box_pts
        assert (x, y) == (9.0, 9.0)
        assert (w, h) == (612.0, 792.0)

    def test_bleed_box_equals_media_box(self, geom: PageGeometry) -> None:
        # Until a slug area is added, BleedBox == MediaBox by spec.
        assert geom.bleed_box_pts == geom.media_box_pts

    def test_art_box_is_inset_from_trim_corner(self, geom: PageGeometry) -> None:
        margin_pt = inches_to_points(SAFE_MARGIN)
        x, y, w, h = geom.art_box_pts
        assert (x, y) == (9.0 + margin_pt, 9.0 + margin_pt)
        assert w == 612.0 - 2 * margin_pt
        assert h == 792.0 - 2 * margin_pt


class TestPageGeometryMOO:
    """``PageGeometry.moo_a6()`` is a stub for the upcoming --export-for PR."""

    def test_moo_a6_has_industry_bleed_and_a6_trim(self) -> None:
        geom = PageGeometry.moo_a6()
        assert geom.bleed_in == 0.125
        # A6 is roughly 4.13 x 5.83 inches
        assert geom.trim_width_in == 4.13
        assert geom.trim_height_in == 5.83
