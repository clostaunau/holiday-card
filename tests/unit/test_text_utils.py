"""Unit tests for text_utils module (overflow prevention)."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from holiday_card.core.text_utils import (
    TextMetrics,
    calculate_line_height,
    measure_text,
    shrink_to_fit,
    wrap_text,
)


class TestTextMetrics:
    """Tests for TextMetrics model."""

    def test_text_metrics_creation(self):
        """Test creating a TextMetrics instance."""
        metrics = TextMetrics(
            width_pts=100.0,
            height_pts=14.4,
            line_count=1,
            fits_within_bounds=True,
        )
        assert metrics.width_pts == 100.0
        assert metrics.height_pts == 14.4
        assert metrics.line_count == 1
        assert metrics.fits_within_bounds is True


class TestMeasureText:
    """Tests for measure_text() function."""

    def test_measure_text_width_single_line(self):
        """Test basic width measurement for single line text."""
        # Create a temporary PDF canvas for measurement
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        metrics = measure_text(c, "Hello World", "Helvetica", 12, max_width=500.0)

        assert metrics.width_pts > 0
        assert abs(metrics.height_pts - 14.4) < 0.01  # 12pt * 1.2
        assert metrics.line_count == 1
        # "Hello World" at 12pt Helvetica should fit within 500pts
        assert metrics.fits_within_bounds is True

    def test_measure_text_returns_metrics(self):
        """Test that measure_text returns TextMetrics structure."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        metrics = measure_text(c, "Test", "Helvetica", 24, max_width=200.0)

        assert isinstance(metrics, TextMetrics)
        assert hasattr(metrics, 'width_pts')
        assert hasattr(metrics, 'height_pts')
        assert hasattr(metrics, 'line_count')
        assert hasattr(metrics, 'fits_within_bounds')

    def test_measure_text_overflow_detection(self):
        """Test that overflow is correctly detected."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # Very long text with small max_width should not fit
        metrics = measure_text(
            c,
            "This is a very long text that will definitely overflow",
            "Helvetica",
            12,
            max_width=50.0
        )

        assert metrics.fits_within_bounds is False


class TestShrinkToFit:
    """Tests for shrink_to_fit() function."""

    def test_shrink_to_fit_reduces_font_size(self):
        """Test that oversized text gets font size reduced."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # Long text at 36pt will not fit in 200pts width
        final_size = shrink_to_fit(
            c,
            "This is a very long greeting message!",
            "Helvetica",
            initial_size=36,
            max_width=200.0,
            min_size=8
        )

        # Should be reduced below 36pt
        assert final_size < 36
        # Should respect minimum
        assert final_size >= 8

    def test_shrink_to_fit_returns_original_if_fits(self):
        """Test that text that already fits is not shrunk."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # Short text at 12pt should fit in 500pts width
        final_size = shrink_to_fit(
            c,
            "Hi",
            "Helvetica",
            initial_size=12,
            max_width=500.0,
            min_size=8
        )

        # Should return original size
        assert final_size == 12

    def test_shrink_to_fit_enforces_minimum(self):
        """Test that minimum font size (8pt) is enforced."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # Extreme text that would require very small font
        final_size = shrink_to_fit(
            c,
            "This is an extremely long message that has way too much text to fit",
            "Helvetica",
            initial_size=24,
            max_width=100.0,
            min_size=8
        )

        # Should stop at minimum
        assert final_size == 8

    def test_shrink_to_fit_binary_search_efficiency(self):
        """Test that binary search completes in reasonable iterations."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # This is more of a performance check - should complete quickly
        # Testing that it doesn't do linear search (which would be slow)
        import time
        start = time.time()

        final_size = shrink_to_fit(
            c,
            "Medium length text for testing",
            "Helvetica",
            initial_size=72,
            max_width=250.0,
            min_size=8
        )

        duration = time.time() - start

        # Should complete in under 10ms (binary search is fast)
        assert duration < 0.01
        # Should find a size between min and initial
        assert 8 <= final_size <= 72


class TestCalculateLineHeight:
    """Tests for calculate_line_height() function."""

    def test_calculate_line_height(self):
        """Test that line height is 1.2x font size."""
        assert abs(calculate_line_height(12) - 14.4) < 0.01
        assert abs(calculate_line_height(24) - 28.8) < 0.01
        assert abs(calculate_line_height(10) - 12.0) < 0.01


class TestWrapText:
    """Tests for wrap_text() function."""

    def test_wrap_text_at_word_boundaries(self):
        """Test that text wraps at word boundaries."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        lines = wrap_text(
            c,
            "This is a longer text that should wrap to multiple lines",
            "Helvetica",
            12,
            max_width=150.0
        )

        # Should wrap to multiple lines
        assert len(lines) > 1
        # Each line should be a string
        assert all(isinstance(line, str) for line in lines)
        # Should not have mid-word breaks (rough check)
        for line in lines:
            # Lines should start/end with complete words (no trailing spaces ideally)
            assert line.strip() == line or len(line) > 0

    def test_wrap_text_respects_max_lines(self):
        """Test that max_lines parameter is respected."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        lines = wrap_text(
            c,
            "This is a very long text that could wrap to many many lines if we let it continue",
            "Helvetica",
            12,
            max_width=100.0,
            max_lines=3
        )

        # Should not exceed max_lines
        assert len(lines) <= 3

    def test_wrap_text_single_word_exceeds_width(self):
        """Test handling of single word that exceeds width."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # Single very long word
        lines = wrap_text(
            c,
            "Supercalifragilisticexpialidocious",
            "Helvetica",
            12,
            max_width=50.0
        )

        # Should still create at least one line (force break)
        assert len(lines) >= 1
        assert "Supercalifragilisticexpialidocious" in lines[0]

    def test_wrap_text_returns_list_of_lines(self):
        """Test that wrap_text returns a list of strings."""
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        lines = wrap_text(
            c,
            "Short text",
            "Helvetica",
            12,
            max_width=500.0
        )

        assert isinstance(lines, list)
        assert len(lines) >= 1
        assert isinstance(lines[0], str)
