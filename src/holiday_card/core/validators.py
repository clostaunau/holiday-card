"""Validation utilities for vector graphics features.

This module provides validation functions for:
- SVG path data syntax and structure
- Gradient color stop ordering and ranges
- Pattern fill parameters
- Clipping mask dimensions
"""

import logging

from holiday_card.core.models import (
    ClipMask,
    ColorStop,
    FillStyle,
    LinearGradientFill,
    PatternFill,
    RadialGradientFill,
)

logger = logging.getLogger(__name__)


def validate_svg_path_data(path_data: str) -> tuple[bool, str | None]:
    """Validate SVG path data syntax.

    Args:
        path_data: SVG path data string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path_data or not path_data.strip():
        return False, "SVG path data cannot be empty"

    # Check for valid SVG commands
    valid_commands = set('MmLlHhVvCcSsQqTtAaZz')
    has_command = any(c in valid_commands for c in path_data)

    if not has_command:
        return False, "SVG path must contain at least one valid command (M, L, C, Q, A, Z)"

    # Basic syntax check - must start with Move command
    path_data = path_data.strip()
    if path_data[0] not in 'Mm':
        logger.warning(f"SVG path should start with M/m command, got: {path_data[0]}")

    return True, None


def validate_gradient_stops(stops: list[ColorStop]) -> tuple[bool, str | None]:
    """Validate gradient color stops.

    Args:
        stops: List of ColorStop objects

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(stops) < 2:
        return False, "Gradient must have at least 2 color stops"

    if len(stops) > 20:
        return False, "Gradient cannot have more than 20 color stops"

    # Check positions are in ascending order
    positions = [stop.position for stop in stops]
    if positions != sorted(positions):
        return False, "Color stop positions must be in ascending order"

    # Check all positions are in valid range
    for stop in stops:
        if not (0.0 <= stop.position <= 1.0):
            return False, f"Color stop position {stop.position} out of range (0.0-1.0)"

    return True, None


def validate_pattern_fill(pattern: PatternFill) -> tuple[bool, str | None]:
    """Validate pattern fill parameters.

    Args:
        pattern: PatternFill model

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check spacing range
    if not (0.0 < pattern.spacing <= 2.0):
        return False, f"Pattern spacing {pattern.spacing} out of range (0.0-2.0)"

    # Check scale range
    if not (0.0 < pattern.scale <= 5.0):
        return False, f"Pattern scale {pattern.scale} out of range (0.0-5.0)"

    # Check color count
    if len(pattern.colors) < 1:
        return False, "Pattern must have at least 1 color"

    if len(pattern.colors) > 4:
        return False, "Pattern cannot have more than 4 colors"

    return True, None


def validate_clip_mask_dimensions(
    clip_mask: ClipMask,
    image_width: float,
    image_height: float
) -> tuple[bool, str | None]:
    """Validate clipping mask dimensions are within image bounds.

    Args:
        clip_mask: ClipMask model
        image_width: Image width in inches
        image_height: Image height in inches

    Returns:
        Tuple of (is_valid, warning_message)
    """
    # Note: This is a warning-level validation, not strict error
    # Clipping masks can extend beyond image bounds (will be cropped)

    if clip_mask.type == "circle":
        max_extent = clip_mask.center_x + clip_mask.radius
        if max_extent > image_width:
            return False, f"Circle clip mask extends beyond image width ({max_extent} > {image_width})"

        max_extent = clip_mask.center_y + clip_mask.radius
        if max_extent > image_height:
            return False, f"Circle clip mask extends beyond image height ({max_extent} > {image_height})"

    elif clip_mask.type == "rectangle":
        max_extent = clip_mask.x + clip_mask.width
        if max_extent > image_width:
            return False, f"Rectangle clip mask extends beyond image width ({max_extent} > {image_width})"

        max_extent = clip_mask.y + clip_mask.height
        if max_extent > image_height:
            return False, f"Rectangle clip mask extends beyond image height ({max_extent} > {image_height})"

    elif clip_mask.type == "ellipse":
        max_extent = clip_mask.center_x + clip_mask.radius_x
        if max_extent > image_width:
            return False, f"Ellipse clip mask extends beyond image width ({max_extent} > {image_width})"

        max_extent = clip_mask.center_y + clip_mask.radius_y
        if max_extent > image_height:
            return False, f"Ellipse clip mask extends beyond image height ({max_extent} > {image_height})"

    elif clip_mask.type == "star":
        max_extent = clip_mask.center_x + clip_mask.outer_radius
        if max_extent > image_width:
            return False, f"Star clip mask extends beyond image width ({max_extent} > {image_width})"

        max_extent = clip_mask.center_y + clip_mask.outer_radius
        if max_extent > image_height:
            return False, f"Star clip mask extends beyond image height ({max_extent} > {image_height})"

    return True, None


def validate_fill_style(fill: FillStyle) -> tuple[bool, str | None]:
    """Validate fill style parameters.

    Args:
        fill: FillStyle model (solid, gradient, or pattern)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if isinstance(fill, LinearGradientFill) or isinstance(fill, RadialGradientFill):
        return validate_gradient_stops(fill.stops)

    elif isinstance(fill, PatternFill):
        return validate_pattern_fill(fill)

    # SolidFill has no additional validation beyond Pydantic
    return True, None
