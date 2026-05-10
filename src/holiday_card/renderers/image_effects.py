"""Image processing effects for photos.

Applies visual effects (grayscale, sepia, vignette, blur) to images
using Pillow before they are rendered to PDF.
"""

import math

from PIL import Image, ImageFilter

from holiday_card.core.models import ImageEffects


def apply_effects(image: Image.Image, effects: ImageEffects) -> Image.Image:
    """Apply all configured effects to an image.

    Args:
        image: PIL Image to process.
        effects: Effects configuration.

    Returns:
        Processed PIL Image.
    """
    result = image.copy()

    if effects.grayscale:
        result = apply_grayscale(result)

    if effects.sepia:
        result = apply_sepia(result)

    if effects.blur > 0:
        result = apply_blur(result, effects.blur)

    if effects.vignette > 0:
        result = apply_vignette(result, effects.vignette)

    return result


def apply_grayscale(image: Image.Image) -> Image.Image:
    """Convert image to grayscale."""
    return image.convert("L").convert("RGB")


def apply_sepia(image: Image.Image) -> Image.Image:
    """Apply sepia tone effect."""
    gray = image.convert("L")
    result = Image.merge("RGB", (
        gray.point(lambda x: min(255, int(x * 1.2))),
        gray.point(lambda x: int(x * 1.0)),
        gray.point(lambda x: int(x * 0.8)),
    ))
    return result


def apply_blur(image: Image.Image, radius: float) -> Image.Image:
    """Apply Gaussian blur."""
    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_vignette(image: Image.Image, intensity: float) -> Image.Image:
    """Apply vignette darkening at edges."""
    width, height = image.size
    result = image.copy()
    pixels = result.load()

    cx, cy = width / 2, height / 2
    max_dist = math.sqrt(cx ** 2 + cy ** 2)

    for y_pos in range(height):
        for x_pos in range(width):
            dist = math.sqrt((x_pos - cx) ** 2 + (y_pos - cy) ** 2)
            factor = 1.0 - (dist / max_dist) * intensity
            factor = max(0.0, factor)
            r, g, b = pixels[x_pos, y_pos][:3]
            pixels[x_pos, y_pos] = (
                int(r * factor),
                int(g * factor),
                int(b * factor),
            )

    return result
