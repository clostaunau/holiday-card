"""Input validation utilities for holiday card generation.

Provides validation functions for file paths, colors, dimensions,
and other user inputs to ensure data integrity before processing.
"""

from pathlib import Path

from holiday_card.utils.measurements import (
    MIN_DPI,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    SAFE_MARGIN,
)


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def validate_file_path(path: Path, must_exist: bool = True) -> Path:
    """Validate a file path.

    Args:
        path: Path to validate.
        must_exist: If True, path must exist.

    Returns:
        Validated Path object.

    Raises:
        ValidationError: If path is invalid.
    """
    if must_exist and not path.exists():
        raise ValidationError(f"File not found: {path}")

    if must_exist and not path.is_file():
        raise ValidationError(f"Not a file: {path}")

    return path


def validate_output_path(path: Path) -> Path:
    """Validate an output file path.

    Args:
        path: Output path to validate.

    Returns:
        Validated Path object.

    Raises:
        ValidationError: If path is invalid or parent directory doesn't exist.
    """
    parent = path.parent
    if not parent.exists():
        raise ValidationError(f"Output directory does not exist: {parent}")

    if path.exists() and path.is_dir():
        raise ValidationError(f"Output path is a directory: {path}")

    return path


def validate_color_component(value: float, name: str = "color") -> float:
    """Validate a color component is in valid range.

    Args:
        value: Color component value.
        name: Name for error messages.

    Returns:
        Validated value.

    Raises:
        ValidationError: If value is out of range.
    """
    if not 0.0 <= value <= 1.0:
        raise ValidationError(f"Invalid {name} value: {value}. Must be between 0.0 and 1.0")
    return value


def validate_color_rgb(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Validate RGB color values.

    Args:
        r: Red component (0.0-1.0).
        g: Green component (0.0-1.0).
        b: Blue component (0.0-1.0).

    Returns:
        Validated (r, g, b) tuple.

    Raises:
        ValidationError: If any component is out of range.
    """
    validate_color_component(r, "red")
    validate_color_component(g, "green")
    validate_color_component(b, "blue")
    return (r, g, b)


def validate_dimensions(
    width: float,
    height: float,
    max_width: float = PAGE_WIDTH,
    max_height: float = PAGE_HEIGHT,
) -> tuple[float, float]:
    """Validate dimensions are positive and within bounds.

    Args:
        width: Width in inches.
        height: Height in inches.
        max_width: Maximum allowed width.
        max_height: Maximum allowed height.

    Returns:
        Validated (width, height) tuple.

    Raises:
        ValidationError: If dimensions are invalid.
    """
    if width <= 0:
        raise ValidationError(f"Width must be positive: {width}")
    if height <= 0:
        raise ValidationError(f"Height must be positive: {height}")
    if width > max_width:
        raise ValidationError(f"Width {width} exceeds maximum {max_width}")
    if height > max_height:
        raise ValidationError(f"Height {height} exceeds maximum {max_height}")
    return (width, height)


def validate_position(
    x: float,
    y: float,
    max_x: float = PAGE_WIDTH,
    max_y: float = PAGE_HEIGHT,
    respect_margins: bool = True,
) -> tuple[float, float]:
    """Validate position is within bounds.

    Args:
        x: X position in inches.
        y: Y position in inches.
        max_x: Maximum X value.
        max_y: Maximum Y value.
        respect_margins: If True, enforce safe margins.

    Returns:
        Validated (x, y) tuple.

    Raises:
        ValidationError: If position is invalid.
    """
    min_val = SAFE_MARGIN if respect_margins else 0.0

    if x < min_val:
        raise ValidationError(f"X position {x} is below minimum {min_val}")
    if y < min_val:
        raise ValidationError(f"Y position {y} is below minimum {min_val}")
    if x > max_x - (SAFE_MARGIN if respect_margins else 0):
        raise ValidationError(f"X position {x} exceeds maximum")
    if y > max_y - (SAFE_MARGIN if respect_margins else 0):
        raise ValidationError(f"Y position {y} exceeds maximum")

    return (x, y)


def validate_font_size(size: int) -> int:
    """Validate font size is within acceptable range.

    Args:
        size: Font size in points.

    Returns:
        Validated font size.

    Raises:
        ValidationError: If size is out of range.
    """
    if size < 6:
        raise ValidationError(f"Font size {size} is too small. Minimum is 6 points.")
    if size > 144:
        raise ValidationError(f"Font size {size} is too large. Maximum is 144 points.")
    return size


def validate_image_format(path: Path) -> str:
    """Validate image file format is supported.

    Args:
        path: Path to image file.

    Returns:
        Normalized file extension (lowercase, without dot).

    Raises:
        ValidationError: If format is not supported.
    """
    supported = {"png", "jpg", "jpeg"}
    ext = path.suffix.lower().lstrip(".")

    if ext not in supported:
        raise ValidationError(
            f"Unsupported image format: .{ext}. "
            f"Supported formats: {', '.join(sorted(supported))}"
        )

    return ext


def validate_dpi(dpi: int, warn_only: bool = True) -> str | None:
    """Validate image DPI for print quality.

    Args:
        dpi: Dots per inch.
        warn_only: If True, return warning instead of raising error.

    Returns:
        Warning message if DPI is low and warn_only is True, None otherwise.

    Raises:
        ValidationError: If DPI is too low and warn_only is False.
    """
    if dpi < MIN_DPI:
        msg = (
            f"Image DPI ({dpi}) is below recommended minimum ({MIN_DPI}). "
            "Print quality may be poor."
        )
        if warn_only:
            return msg
        raise ValidationError(msg)
    return None


def validate_template_name(name: str) -> str:
    """Validate template name format.

    Args:
        name: Template name.

    Returns:
        Validated name.

    Raises:
        ValidationError: If name is invalid.
    """
    if not name:
        raise ValidationError("Template name cannot be empty")

    if len(name) > 50:
        raise ValidationError(f"Template name too long: {len(name)} chars. Maximum is 50.")

    # Allow alphanumeric, hyphens, underscores
    valid_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
    invalid = set(name.lower()) - valid_chars
    if invalid:
        raise ValidationError(
            f"Template name contains invalid characters: {invalid}. "
            "Use only letters, numbers, hyphens, and underscores."
        )

    return name
