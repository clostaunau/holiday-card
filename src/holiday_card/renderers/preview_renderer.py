"""Preview renderer for holiday cards.

This module provides preview generation capabilities, converting
card designs to raster images for visual preview before printing.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from holiday_card.core.models import (
    Card,
    Color,
    FoldType,
    Panel,
)
from holiday_card.utils.measurements import (
    PAGE_HEIGHT,
    PAGE_WIDTH,
)


class PreviewRenderer:
    """Generates preview images of card designs.

    Creates raster images showing how the card will look when printed,
    with optional fold line visualization.
    """

    def __init__(self, dpi: int = 150) -> None:
        """Initialize the preview renderer.

        Args:
            dpi: Resolution for preview image (dots per inch).
        """
        self.dpi = dpi
        self._image: Image.Image | None = None
        self._draw: ImageDraw.ImageDraw | None = None

    @property
    def width_px(self) -> int:
        """Get image width in pixels."""
        return int(PAGE_WIDTH * self.dpi)

    @property
    def height_px(self) -> int:
        """Get image height in pixels."""
        return int(PAGE_HEIGHT * self.dpi)

    def inches_to_px(self, inches: float) -> int:
        """Convert inches to pixels."""
        return int(inches * self.dpi)

    def create_preview(
        self,
        card: Card,
        show_guides: bool = True,
        output_path: Path | None = None,
        format: str = "png",
    ) -> Image.Image:
        """Create a preview image of the card.

        Args:
            card: Card to preview.
            show_guides: Whether to show fold line guides.
            output_path: Optional path to save the preview.
            format: Output format (png, jpg).

        Returns:
            PIL Image object.
        """
        # Create blank white image
        self._image = Image.new("RGB", (self.width_px, self.height_px), "white")
        self._draw = ImageDraw.Draw(self._image)

        # Render each panel
        for panel in card.panels:
            self._render_panel(panel)

        # Draw fold guides if requested
        if show_guides:
            self._draw_fold_guides(card.fold_type)

        # Save if path provided
        if output_path:
            self._save_preview(output_path, format)

        return self._image

    def _render_panel(self, panel: Panel) -> None:
        """Render a panel to the preview image.

        Args:
            panel: Panel to render.
        """
        if self._draw is None or self._image is None:
            return

        # Convert panel coordinates to pixels
        # Note: PIL uses top-left origin, so we need to flip Y
        x1 = self.inches_to_px(panel.x)
        y1 = self.height_px - self.inches_to_px(panel.y + panel.height)
        x2 = self.inches_to_px(panel.x + panel.width)
        y2 = self.height_px - self.inches_to_px(panel.y)

        # Draw background color if specified
        if panel.background_color:
            color = self._color_to_rgb(panel.background_color)
            self._draw.rectangle([x1, y1, x2, y2], fill=color)

        # Draw border if specified
        if panel.border:
            border_color = self._color_to_rgb(panel.border.color)
            border_width = max(1, int(panel.border.width))
            self._draw.rectangle([x1, y1, x2, y2], outline=border_color, width=border_width)

        # Note: Text and image rendering would require more complex handling
        # For preview purposes, we show the layout structure

    def _color_to_rgb(self, color: Color) -> tuple[int, int, int]:
        """Convert Color object to RGB tuple."""
        return (
            int(color.r * 255),
            int(color.g * 255),
            int(color.b * 255),
        )

    def _draw_fold_guides(self, fold_type: FoldType) -> None:
        """Draw fold line guides on the preview.

        Args:
            fold_type: Type of fold for the card.
        """
        if self._draw is None:
            return

        # Use a bright color for fold guides
        guide_color = (255, 100, 100)  # Light red
        guide_width = max(2, self.dpi // 72)  # Scale with DPI

        if fold_type == FoldType.HALF_FOLD:
            # Horizontal fold at middle
            mid_y = self.height_px // 2
            self._draw_dashed_line(0, mid_y, self.width_px, mid_y, guide_color, guide_width)

        elif fold_type == FoldType.QUARTER_FOLD:
            # Horizontal and vertical folds
            mid_x = self.width_px // 2
            mid_y = self.height_px // 2
            self._draw_dashed_line(0, mid_y, self.width_px, mid_y, guide_color, guide_width)
            self._draw_dashed_line(mid_x, 0, mid_x, self.height_px, guide_color, guide_width)

        elif fold_type == FoldType.TRI_FOLD:
            # Two vertical folds at 1/3 and 2/3
            third_x = self.width_px // 3
            self._draw_dashed_line(third_x, 0, third_x, self.height_px, guide_color, guide_width)
            self._draw_dashed_line(third_x * 2, 0, third_x * 2, self.height_px, guide_color, guide_width)

    def _draw_dashed_line(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: tuple[int, int, int],
        width: int,
    ) -> None:
        """Draw a dashed line on the image.

        Args:
            x1, y1: Start point.
            x2, y2: End point.
            color: Line color.
            width: Line width.
        """
        if self._draw is None:
            return

        dash_length = max(10, self.dpi // 10)
        gap_length = max(5, self.dpi // 20)

        # Determine if horizontal or vertical
        if x1 == x2:
            # Vertical line
            current_y = min(y1, y2)
            end_y = max(y1, y2)
            while current_y < end_y:
                segment_end = min(current_y + dash_length, end_y)
                self._draw.line([(x1, current_y), (x1, segment_end)], fill=color, width=width)
                current_y = segment_end + gap_length
        else:
            # Horizontal line
            current_x = min(x1, x2)
            end_x = max(x1, x2)
            while current_x < end_x:
                segment_end = min(current_x + dash_length, end_x)
                self._draw.line([(current_x, y1), (segment_end, y1)], fill=color, width=width)
                current_x = segment_end + gap_length

    def _save_preview(self, output_path: Path, format: str) -> None:
        """Save the preview image to a file.

        Args:
            output_path: Path to save the image.
            format: Image format (png, jpg).
        """
        if self._image is None:
            return

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save with appropriate format
        if format.lower() in ("jpg", "jpeg"):
            # Convert to RGB if needed (JPEG doesn't support alpha)
            if self._image.mode == "RGBA":
                self._image = self._image.convert("RGB")
            self._image.save(output_path, "JPEG", quality=90)
        else:
            self._image.save(output_path, "PNG")


def generate_preview(
    card: Card,
    output_path: Path,
    dpi: int = 150,
    format: str = "png",
    show_guides: bool = True,
) -> Path:
    """Generate a preview image of a card.

    Convenience function for one-shot preview generation.

    Args:
        card: Card to preview.
        output_path: Path to save the preview.
        dpi: Resolution (dots per inch).
        format: Output format (png, jpg).
        show_guides: Whether to show fold guides.

    Returns:
        Path to saved preview image.
    """
    renderer = PreviewRenderer(dpi=dpi)
    renderer.create_preview(card, show_guides=show_guides, output_path=output_path, format=format)
    return output_path
