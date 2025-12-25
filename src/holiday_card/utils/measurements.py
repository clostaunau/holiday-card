"""Measurement constants and conversion utilities for print-accurate PDF generation.

All measurements use inches as the primary unit, converted to PDF points (72 pts/inch)
only at render time. This ensures print accuracy per Constitution Principle IV.
"""

# Page dimensions (US Letter)
PAGE_WIDTH: float = 8.5  # inches
PAGE_HEIGHT: float = 11.0  # inches

# Safety margins
SAFE_MARGIN: float = 0.25  # inches - minimum margin from all edges

# PDF conversion
POINTS_PER_INCH: float = 72.0  # PDF points per inch

# Line widths (in points)
FOLD_LINE_WIDTH: float = 0.5  # points
CUT_LINE_WIDTH: float = 1.0  # points

# Image quality
MIN_DPI: int = 150  # minimum DPI for print quality
RECOMMENDED_DPI: int = 300  # recommended DPI for best print quality

# Fold type dimensions (folded sizes in inches)
HALF_FOLD_WIDTH: float = PAGE_HEIGHT / 2  # 5.5 inches when folded
HALF_FOLD_HEIGHT: float = PAGE_WIDTH  # 8.5 inches

QUARTER_FOLD_WIDTH: float = PAGE_WIDTH / 2  # 4.25 inches when folded
QUARTER_FOLD_HEIGHT: float = PAGE_HEIGHT / 2  # 5.5 inches

TRI_FOLD_PANEL_WIDTH: float = PAGE_WIDTH / 3  # ~2.83 inches per panel
TRI_FOLD_HEIGHT: float = PAGE_HEIGHT  # 11 inches


def inches_to_points(inches: float) -> float:
    """Convert inches to PDF points.

    Args:
        inches: Measurement in inches.

    Returns:
        Measurement in PDF points (72 points = 1 inch).
    """
    return inches * POINTS_PER_INCH


def points_to_inches(points: float) -> float:
    """Convert PDF points to inches.

    Args:
        points: Measurement in PDF points.

    Returns:
        Measurement in inches.
    """
    return points / POINTS_PER_INCH


def validate_within_page(x: float, y: float, width: float, height: float) -> bool:
    """Check if a rectangle fits within the page bounds with safe margins.

    Args:
        x: X position in inches from left edge.
        y: Y position in inches from bottom edge.
        width: Width in inches.
        height: Height in inches.

    Returns:
        True if rectangle fits within safe area, False otherwise.
    """
    if x < SAFE_MARGIN or y < SAFE_MARGIN:
        return False
    if x + width > PAGE_WIDTH - SAFE_MARGIN:
        return False
    if y + height > PAGE_HEIGHT - SAFE_MARGIN:
        return False
    return True


def validate_within_panel(
    x: float,
    y: float,
    width: float,
    height: float,
    panel_width: float,
    panel_height: float
) -> bool:
    """Check if a rectangle fits within a panel with safe margins.

    Args:
        x: X position in inches from panel left edge.
        y: Y position in inches from panel bottom edge.
        width: Width in inches.
        height: Height in inches.
        panel_width: Panel width in inches.
        panel_height: Panel height in inches.

    Returns:
        True if rectangle fits within panel safe area, False otherwise.
    """
    if x < SAFE_MARGIN or y < SAFE_MARGIN:
        return False
    if x + width > panel_width - SAFE_MARGIN:
        return False
    if y + height > panel_height - SAFE_MARGIN:
        return False
    return True
