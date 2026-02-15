"""Text measurement and fitting utilities for overflow prevention.

This module provides functions for measuring text dimensions and applying
overflow adjustment strategies (shrink, wrap, truncate).
"""


from pydantic import BaseModel, Field
from reportlab.pdfgen import canvas


class TextMetrics(BaseModel):
    """Measured dimensions of rendered text.

    Used internally for overflow detection and fitting calculations.
    """

    width_pts: float = Field(
        ge=0.0,
        description="Calculated text width in points"
    )
    height_pts: float = Field(
        ge=0.0,
        description="Calculated text height in points"
    )
    line_count: int = Field(
        ge=1,
        description="Number of lines (1 for single-line)"
    )
    fits_within_bounds: bool = Field(
        description="Whether text fits in max_width and max_height"
    )


def calculate_line_height(font_size_pt: int) -> float:
    """Calculate line height for text.

    Uses typography standard of 1.2x font size for line spacing.

    Args:
        font_size_pt: Font size in points.

    Returns:
        Line height in points (1.2 * font_size).
    """
    return font_size_pt * 1.2


def measure_text(
    c: canvas.Canvas,
    content: str,
    font_name: str,
    font_size: int,
    max_width: float,
    max_height: float | None = None,
    lines: list[str] | None = None,
) -> TextMetrics:
    """Measure text dimensions using ReportLab's stringWidth.

    Args:
        c: ReportLab Canvas for measurement.
        content: Text content to measure.
        font_name: Font name (e.g., "Helvetica").
        font_size: Font size in points.
        max_width: Maximum width boundary in points.
        max_height: Maximum height boundary in points (optional).
        lines: Pre-split lines for multi-line measurement (optional).

    Returns:
        TextMetrics with width, height, line count, and fit status.
    """
    if lines is not None:
        # Multi-line measurement
        line_count = len(lines)
        # Measure widest line
        width_pts = max(c.stringWidth(line, font_name, font_size) for line in lines) if lines else 0.0
        # Calculate total height
        line_height = calculate_line_height(font_size)
        height_pts = line_height * line_count
    else:
        # Single-line measurement
        line_count = 1
        width_pts = c.stringWidth(content, font_name, font_size)
        height_pts = calculate_line_height(font_size)

    # Check if fits within bounds
    fits_width = width_pts <= max_width
    fits_height = (max_height is None) or (height_pts <= max_height)
    fits_within_bounds = fits_width and fits_height

    return TextMetrics(
        width_pts=width_pts,
        height_pts=height_pts,
        line_count=line_count,
        fits_within_bounds=fits_within_bounds,
    )


def shrink_to_fit(
    c: canvas.Canvas,
    content: str,
    font_name: str,
    initial_size: int,
    max_width: float,
    min_size: int = 8,
) -> int:
    """Shrink font size using binary search until text fits within width.

    Args:
        c: ReportLab Canvas for measurement.
        content: Text content to fit.
        font_name: Font name (e.g., "Helvetica").
        initial_size: Starting font size in points.
        max_width: Maximum width in points.
        min_size: Minimum allowed font size (default 8pt).

    Returns:
        Final font size that fits (may equal min_size if can't fit).
    """
    # Binary search for optimal font size
    low = min_size
    high = initial_size
    best_size = min_size

    while low <= high:
        mid = (low + high) // 2
        metrics = measure_text(c, content, font_name, mid, max_width)

        if metrics.fits_within_bounds:
            # This size fits - try larger
            best_size = mid
            low = mid + 1
        else:
            # This size too large - try smaller
            high = mid - 1

    return best_size


def wrap_text(
    c: canvas.Canvas,
    content: str,
    font_name: str,
    font_size: int,
    max_width: float,
    max_lines: int | None = None,
) -> list[str]:
    """Wrap text at word boundaries to fit within width.

    Args:
        c: ReportLab Canvas for measurement.
        content: Text content to wrap.
        font_name: Font name (e.g., "Helvetica").
        font_size: Font size in points.
        max_width: Maximum width per line in points.
        max_lines: Maximum number of lines (None = unlimited).

    Returns:
        List of wrapped lines.
    """
    words = content.split()
    lines = []
    current_line = []

    for word in words:
        # Try adding this word to current line
        test_line = ' '.join(current_line + [word])
        test_width = c.stringWidth(test_line, font_name, font_size)

        if test_width <= max_width:
            # Word fits - add it
            current_line.append(word)
        else:
            # Word doesn't fit
            if current_line:
                # Save current line and start new one
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Single word exceeds width - force it on its own line
                lines.append(word)

        # Check line limit
        if max_lines and len(lines) >= max_lines:
            break

    # Add remaining words if any
    if current_line and (not max_lines or len(lines) < max_lines):
        lines.append(' '.join(current_line))

    # Trim to max_lines if needed
    if max_lines:
        lines = lines[:max_lines]

    return lines
