"""Gradient utilities for color interpolation and coordinate calculation.

This module provides helper functions for gradient rendering:
- Color interpolation between stops
- Gradient endpoint calculation from angle
- Color stop position mapping
"""

import math

from reportlab.lib.colors import Color, HexColor


def gradient_endpoints(
    angle: float,
    width: float,
    height: float,
    x_offset: float = 0.0,
    y_offset: float = 0.0
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Calculate gradient start and end points from angle.

    Converts a gradient angle to start/end coordinates for ReportLab's
    linear gradient API. Angle 0 = horizontal right, 90 = vertical up.

    Args:
        angle: Gradient angle in degrees (0-360)
        width: Shape width in points
        height: Shape height in points
        x_offset: X position offset in points
        y_offset: Y position offset in points

    Returns:
        Tuple of (start_point, end_point) where each point is (x, y)
    """
    # Normalize angle to 0-360 range
    angle = angle % 360

    # Convert angle to radians
    rad = math.radians(angle)

    # Calculate gradient vector
    # Use shape diagonal to ensure gradient covers entire shape
    diagonal = math.sqrt(width**2 + height**2)

    # Calculate direction vector
    dx = math.cos(rad) * diagonal / 2
    dy = math.sin(rad) * diagonal / 2

    # Center point
    center_x = x_offset + width / 2
    center_y = y_offset + height / 2

    # Start and end points
    start = (center_x - dx, center_y - dy)
    end = (center_x + dx, center_y + dy)

    return start, end


def interpolate_color(
    color1: str,
    color2: str,
    position: float
) -> Color:
    """Interpolate between two colors at a given position.

    Args:
        color1: Start color as hex string (#RRGGBB)
        color2: End color as hex string (#RRGGBB)
        position: Interpolation position (0.0 = color1, 1.0 = color2)

    Returns:
        ReportLab Color object at interpolated position
    """
    # Ensure position is in valid range
    position = max(0.0, min(1.0, position))

    # Parse hex colors
    c1 = HexColor(color1)
    c2 = HexColor(color2)

    # Interpolate RGB components
    r = c1.red + (c2.red - c1.red) * position
    g = c1.green + (c2.green - c1.green) * position
    b = c1.blue + (c2.blue - c1.blue) * position

    return Color(r, g, b)


def find_color_at_position(
    stops: list[tuple[float, str]],
    position: float
) -> str:
    """Find interpolated color at a specific position along gradient.

    Args:
        stops: List of (position, color) tuples in ascending position order
        position: Position along gradient (0.0-1.0)

    Returns:
        Hex color string at the requested position
    """
    if not stops:
        return "#000000"

    # Clamp position to valid range
    position = max(0.0, min(1.0, position))

    # If before first stop, use first color
    if position <= stops[0][0]:
        return stops[0][1]

    # If after last stop, use last color
    if position >= stops[-1][0]:
        return stops[-1][1]

    # Find surrounding stops
    for i in range(len(stops) - 1):
        pos1, color1 = stops[i]
        pos2, color2 = stops[i + 1]

        if pos1 <= position <= pos2:
            # Interpolate between these two stops
            if pos2 - pos1 == 0:
                return color1

            local_pos = (position - pos1) / (pos2 - pos1)
            interpolated = interpolate_color(color1, color2, local_pos)

            # Convert back to hex
            r = int(interpolated.red * 255)
            g = int(interpolated.green * 255)
            b = int(interpolated.blue * 255)
            return f"#{r:02x}{g:02x}{b:02x}"

    return "#000000"


def radial_gradient_endpoints(
    center_x: float,
    center_y: float,
    radius: float,
    shape_width: float,
    shape_height: float,
    x_offset: float = 0.0,
    y_offset: float = 0.0
) -> tuple[tuple[float, float], float]:
    """Calculate radial gradient center and radius in points.

    Converts relative gradient parameters (0.0-1.0) to absolute coordinates
    for ReportLab's radial gradient API.

    Args:
        center_x: Center X position (0.0-1.0 relative to shape)
        center_y: Center Y position (0.0-1.0 relative to shape)
        radius: Gradient radius (0.0-1.0 relative to shape size)
        shape_width: Shape width in points
        shape_height: Shape height in points
        x_offset: X position offset in points
        y_offset: Y position offset in points

    Returns:
        Tuple of ((center_x, center_y), radius) in points
    """
    # Convert relative to absolute coordinates
    abs_center_x = x_offset + (center_x * shape_width)
    abs_center_y = y_offset + (center_y * shape_height)

    # Calculate radius relative to shape diagonal
    diagonal = math.sqrt(shape_width**2 + shape_height**2)
    abs_radius = radius * diagonal

    return (abs_center_x, abs_center_y), abs_radius
