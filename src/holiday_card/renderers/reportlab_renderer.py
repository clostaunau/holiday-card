"""ReportLab PDF renderer for holiday cards.

This module implements PDF generation using ReportLab, providing precise
control over measurements for print-accurate output.
"""

from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from holiday_card.core.decorative import get_library
from holiday_card.core.models import (
    AdjustmentResult,
    Border,
    BorderStyle,
    Card,
    Color,
    Colors,
    ImageElement,
    OverflowStrategy,
    Panel,
    TextElement,
)
from holiday_card.core.text_utils import (
    calculate_line_height,
    measure_text,
    shrink_to_fit,
    wrap_text,
)
from holiday_card.renderers.base import BaseRenderer
from holiday_card.renderers.clipping_renderer import ClippingRenderer  # T072
from holiday_card.renderers.shape_renderer import ShapeRenderer
from holiday_card.utils.measurements import (
    FOLD_LINE_WIDTH,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    inches_to_points,
)


class ReportLabRenderer(BaseRenderer):
    """PDF renderer using ReportLab.

    Generates print-ready PDFs with precise measurements for
    accurate fold lines and content positioning.
    """

    def __init__(self) -> None:
        """Initialize the renderer."""
        super().__init__()
        self._shape_renderer = ShapeRenderer()
        self._clipping_renderer = ClippingRenderer()  # T072
        self._canvas: canvas.Canvas | None = None
        self._output_path: Path | None = None

    def setup_canvas(self, width: float, height: float) -> None:
        """Initialize the PDF canvas.

        Args:
            width: Canvas width in inches.
            height: Canvas height in inches.
        """
        super().setup_canvas(width, height)
        # Note: Canvas will be created when save path is known

    def create_canvas(self, output_path: Path) -> None:
        """Create the PDF canvas for output.

        Args:
            output_path: Path for the output PDF file.
        """
        self._output_path = output_path
        # Use letter size (8.5" x 11")
        self._canvas = canvas.Canvas(
            str(output_path),
            pagesize=letter,
        )

    def render_panel(self, panel: Panel) -> None:
        """Render a single panel with its content.

        Args:
            panel: Panel to render with all its elements.
        """
        if self._canvas is None:
            raise RuntimeError("Canvas not initialized. Call create_canvas first.")

        # Convert panel position and dimensions to points
        x = inches_to_points(panel.x)
        y = inches_to_points(panel.y)
        width = inches_to_points(panel.width)
        height = inches_to_points(panel.height)

        # Save graphics state for rotation
        self._canvas.saveState()

        # Apply rotation if needed (for quarter-fold back panel)
        if panel.rotation != 0:
            # Rotate around panel center
            cx = x + width / 2
            cy = y + height / 2
            self._canvas.translate(cx, cy)
            self._canvas.rotate(panel.rotation)
            self._canvas.translate(-cx, -cy)

        # Draw background color if specified
        if panel.background_color:
            self._canvas.setFillColorRGB(*panel.background_color.to_tuple())
            self._canvas.rect(x, y, width, height, fill=1, stroke=0)

        # Draw border if specified
        if panel.border:
            self._render_border(x, y, width, height, panel.border)

        # Collect all elements with z_index for sorted rendering
        elements = []

        # Add shapes (default z_index = 0)
        for shape in panel.shape_elements:
            z = getattr(shape, 'z_index', 0)
            elements.append(('shape', shape, z))

        # Add images (default z_index = 100)
        for image in panel.image_elements:
            z = getattr(image, 'z_index', 100)
            elements.append(('image', image, z))

        # Add text (default z_index = 100)
        for text in panel.text_elements:
            z = getattr(text, 'z_index', 100)
            elements.append(('text', text, z))

        # Sort by z_index (lowest first = bottom layer), then by definition order
        elements_with_order = [(elem_type, elem, z, idx) for idx, (elem_type, elem, z) in enumerate(elements)]
        elements_with_order.sort(key=lambda e: (e[2], e[3]))  # z_index, then original index
        elements = [(e[0], e[1], e[2]) for e in elements_with_order]  # Remove order index

        # Render in sorted order
        for elem_type, elem, _ in elements:
            if elem_type == 'shape':
                # Check if this is a decorative element
                if hasattr(elem, 'type') and elem.type == 'decorative_element':
                    # Expand decorative element into component shapes
                    library = get_library()
                    component_shapes = library.expand_element(elem)
                    # Render each component shape
                    for component in component_shapes:
                        self._shape_renderer.render_shape(self._canvas, component, panel.x, panel.y)
                else:
                    # Regular shape
                    self._shape_renderer.render_shape(self._canvas, elem, panel.x, panel.y)
            elif elem_type == 'image':
                self.render_image(elem, panel)
            elif elem_type == 'text':
                self.render_text(elem, panel)

        # Restore graphics state
        self._canvas.restoreState()

    def render_text(self, text: TextElement, panel: Panel) -> None:
        """Render a text element within a panel.

        Args:
            text: Text element to render.
            panel: Parent panel for coordinate reference.
        """
        if self._canvas is None:
            raise RuntimeError("Canvas not initialized. Call create_canvas first.")

        # Calculate absolute position
        abs_x = inches_to_points(panel.x + text.x)
        abs_y = inches_to_points(panel.y + text.y)

        # Get font name
        font_name = self._get_font_name(text.font_family, text.font_style.value)

        # Fit text using overflow strategy
        if text.width:
            final_font_size, lines, adjustment_result = self._fit_text_element(text, panel)
            text.set_adjustment_result(adjustment_result)
        else:
            # No width constraint - use original text as-is
            final_font_size = text.font_size
            lines = [text.content]

        # Set font with potentially adjusted size
        self._canvas.setFont(font_name, final_font_size)

        # Set color
        if text.color:
            self._canvas.setFillColorRGB(*text.color.to_tuple())
        else:
            self._canvas.setFillColorRGB(0, 0, 0)  # Default to black

        # Render lines
        alignment = text.alignment.value if hasattr(text, 'alignment') else "left"
        line_height = calculate_line_height(final_font_size)

        for i, line in enumerate(lines):
            # Calculate y position for this line (move down for each line)
            line_y = abs_y - (i * line_height)

            # Handle text alignment
            if alignment == "center":
                self._canvas.drawCentredString(abs_x, line_y, line)
            elif alignment == "right":
                self._canvas.drawRightString(abs_x, line_y, line)
            else:
                self._canvas.drawString(abs_x, line_y, line)

    def render_image(self, image: ImageElement, panel: Panel) -> None:
        """Render an image element within a panel.

        Supports optional clipping masks for circular, star, SVG path, and other shapes.

        Args:
            image: Image element to render.
            panel: Parent panel for coordinate reference.
        """
        if self._canvas is None:
            raise RuntimeError("Canvas not initialized. Call create_canvas first.")

        try:
            # Load image with Pillow to get dimensions
            pil_image = Image.open(image.source_path)
            img_width_px, img_height_px = pil_image.size

            # Get DPI for size calculation (default to 72 if not available)
            dpi = pil_image.info.get("dpi", (72, 72))
            if isinstance(dpi, tuple):
                dpi_x, dpi_y = dpi
            else:
                dpi_x = dpi_y = dpi

            # Calculate natural size in inches
            natural_width = img_width_px / dpi_x
            natural_height = img_height_px / dpi_y

            # Determine final dimensions
            final_width, final_height = self._calculate_image_size(
                natural_width,
                natural_height,
                image.width,
                image.height,
                image.preserve_aspect,
                panel.width,
                panel.height,
            )

            # Calculate absolute position with safe margin enforcement
            abs_x = inches_to_points(panel.x + image.x)
            abs_y = inches_to_points(panel.y + image.y)

            # Enforce safe margins (0.25" from edges)
            safe_margin_pts = inches_to_points(0.25)
            page_width_pts = inches_to_points(PAGE_WIDTH)
            page_height_pts = inches_to_points(PAGE_HEIGHT)

            # Clamp position to safe area
            abs_x = max(safe_margin_pts, min(abs_x, page_width_pts - safe_margin_pts - inches_to_points(final_width)))
            abs_y = max(safe_margin_pts, min(abs_y, page_height_pts - safe_margin_pts - inches_to_points(final_height)))

            # Convert dimensions to points
            width_pts = inches_to_points(final_width)
            height_pts = inches_to_points(final_height)

            # T072-T073: Apply clipping mask if present
            if image.clip_mask is not None:
                # Save canvas state before clipping
                self._canvas.saveState()

                # Apply the clipping mask
                self._clipping_renderer.apply_clip_mask(
                    self._canvas,
                    image.clip_mask,
                    abs_x,
                    abs_y
                )

                # Draw the image within the clipping path
                self._canvas.drawImage(
                    image.source_path,
                    abs_x,
                    abs_y,
                    width=width_pts,
                    height=height_pts,
                    preserveAspectRatio=image.preserve_aspect,
                    mask="auto",  # Handle transparency
                )

                # Restore canvas state after clipping
                self._canvas.restoreState()
            else:
                # Draw the image without clipping
                self._canvas.drawImage(
                    image.source_path,
                    abs_x,
                    abs_y,
                    width=width_pts,
                    height=height_pts,
                    preserveAspectRatio=image.preserve_aspect,
                    mask="auto",  # Handle transparency
                )

            pil_image.close()

        except FileNotFoundError:
            raise RuntimeError(f"Image file not found: {image.source_path}")
        except Exception as e:
            raise RuntimeError(f"Error rendering image: {e}")

    def _calculate_image_size(
        self,
        natural_width: float,
        natural_height: float,
        target_width: float | None,
        target_height: float | None,
        preserve_aspect: bool,
        max_width: float,
        max_height: float,
    ) -> tuple[float, float]:
        """Calculate final image dimensions with aspect ratio handling.

        Args:
            natural_width: Natural image width in inches.
            natural_height: Natural image height in inches.
            target_width: Requested width (None for auto).
            target_height: Requested height (None for auto).
            preserve_aspect: Whether to preserve aspect ratio.
            max_width: Maximum allowed width.
            max_height: Maximum allowed height.

        Returns:
            Tuple of (final_width, final_height) in inches.
        """
        aspect_ratio = natural_width / natural_height if natural_height > 0 else 1.0

        if target_width is not None and target_height is not None:
            # Both specified
            if preserve_aspect:
                # Fit within the specified bounds
                if target_width / target_height > aspect_ratio:
                    return (target_height * aspect_ratio, target_height)
                else:
                    return (target_width, target_width / aspect_ratio)
            else:
                return (target_width, target_height)

        elif target_width is not None:
            # Width specified, calculate height
            if preserve_aspect:
                return (target_width, target_width / aspect_ratio)
            else:
                return (target_width, natural_height)

        elif target_height is not None:
            # Height specified, calculate width
            if preserve_aspect:
                return (target_height * aspect_ratio, target_height)
            else:
                return (natural_width, target_height)

        else:
            # Neither specified, use natural size but fit within panel
            final_width = min(natural_width, max_width)
            final_height = min(natural_height, max_height)

            if preserve_aspect:
                # Scale down if needed while preserving aspect
                scale_x = final_width / natural_width
                scale_y = final_height / natural_height
                scale = min(scale_x, scale_y)
                return (natural_width * scale, natural_height * scale)

            return (final_width, final_height)

    def _handle_text_overflow(self, content: str, font_name: str, font_size: int, max_width: float) -> str:
        """Handle text that exceeds the available width.

        Truncates text with ellipsis if it exceeds the maximum width.

        Args:
            content: Original text content.
            font_name: Font name for width calculation.
            font_size: Font size in points.
            max_width: Maximum width in points.

        Returns:
            Potentially truncated text with ellipsis.
        """
        if self._canvas is None:
            return content

        text_width = self._canvas.stringWidth(content, font_name, font_size)
        if text_width <= max_width:
            return content

        # Truncate with ellipsis
        ellipsis = "..."
        ellipsis_width = self._canvas.stringWidth(ellipsis, font_name, font_size)
        available_width = max_width - ellipsis_width

        # Binary search for the right truncation point
        truncated = content
        while self._canvas.stringWidth(truncated, font_name, font_size) > available_width and len(truncated) > 0:
            truncated = truncated[:-1]

        return truncated.rstrip() + ellipsis


    def _select_auto_strategy(self, text: TextElement) -> OverflowStrategy:
        """Select overflow strategy automatically based on text characteristics.

        Args:
            text: Text element to analyze.

        Returns:
            Selected OverflowStrategy (SHRINK or WRAP).
        """
        text_length = len(text.content)
        has_height = text.width is not None

        # Short text (< 30 chars) - shrink preserves impact
        if text_length < 30:
            return OverflowStrategy.SHRINK

        # Long text with width constraint - wrap for readability
        if text_length >= 30 and has_height:
            return OverflowStrategy.WRAP

        # Long text without height - shrink to single line
        return OverflowStrategy.SHRINK

    def _apply_shrink_strategy(self, text: TextElement, panel: Panel) -> tuple[int, str]:
        """Apply shrink strategy to fit text within width.

        Args:
            text: Text element to fit.
            panel: Parent panel.

        Returns:
            Tuple of (final_font_size, content).
        """
        if self._canvas is None or text.width is None:
            return (text.font_size, text.content)

        font_name = self._get_font_name(text.font_family, text.font_style.value)
        max_width_pts = inches_to_points(text.width)

        # Shrink font to fit
        final_size = shrink_to_fit(
            self._canvas,
            text.content,
            font_name,
            text.font_size,
            max_width_pts,
            text.min_font_size,
        )

        # If shrunk to minimum and still doesn't fit, truncate
        if final_size == text.min_font_size:
            metrics = measure_text(
                self._canvas,
                text.content,
                font_name,
                final_size,
                max_width_pts,
            )
            if not metrics.fits_within_bounds:
                # Fall back to truncation
                content = self._handle_text_overflow(
                    text.content,
                    font_name,
                    final_size,
                    max_width_pts,
                )
                return (final_size, content)

        return (final_size, text.content)

    def _apply_wrap_strategy(self, text: TextElement, panel: Panel) -> tuple[int, list[str]]:
        """Apply wrap strategy to fit text within width and height.

        Args:
            text: Text element to fit.
            panel: Parent panel.

        Returns:
            Tuple of (final_font_size, list_of_lines).
        """
        if self._canvas is None or text.width is None:
            return (text.font_size, [text.content])

        font_name = self._get_font_name(text.font_family, text.font_style.value)
        max_width_pts = inches_to_points(text.width)
        font_size = text.font_size

        # Try wrapping at current font size
        lines = wrap_text(
            self._canvas,
            text.content,
            font_name,
            font_size,
            max_width_pts,
            text.max_lines,
        )

        # Check if wrapped text fits within height (if specified)
        if text.width and hasattr(panel, 'height'):
            max_height_pts = inches_to_points(panel.height) if panel.height else None
            if max_height_pts:
                metrics = measure_text(
                    self._canvas,
                    text.content,
                    font_name,
                    font_size,
                    max_width_pts,
                    max_height_pts,
                    lines,
                )

                # If doesn't fit vertically, reduce font size and re-wrap
                if not metrics.fits_within_bounds and font_size > text.min_font_size:
                    # Binary search for font size that fits with wrapping
                    low = text.min_font_size
                    high = font_size
                    best_size = text.min_font_size
                    best_lines = lines

                    while low <= high:
                        mid = (low + high) // 2
                        test_lines = wrap_text(
                            self._canvas,
                            text.content,
                            font_name,
                            mid,
                            max_width_pts,
                            text.max_lines,
                        )
                        test_metrics = measure_text(
                            self._canvas,
                            text.content,
                            font_name,
                            mid,
                            max_width_pts,
                            max_height_pts,
                            test_lines,
                        )

                        if test_metrics.fits_within_bounds:
                            best_size = mid
                            best_lines = test_lines
                            low = mid + 1
                        else:
                            high = mid - 1

                    return (best_size, best_lines)

        return (font_size, lines)

    def _apply_truncate_strategy(self, text: TextElement, panel: Panel) -> tuple[int, str]:
        """Apply truncate strategy (existing behavior).

        Args:
            text: Text element to fit.
            panel: Parent panel.

        Returns:
            Tuple of (original_font_size, truncated_content).
        """
        if self._canvas is None or text.width is None:
            return (text.font_size, text.content)

        font_name = self._get_font_name(text.font_family, text.font_style.value)
        max_width_pts = inches_to_points(text.width)

        content = self._handle_text_overflow(
            text.content,
            font_name,
            text.font_size,
            max_width_pts,
        )

        return (text.font_size, content)

    def _fit_text_element(self, text: TextElement, panel: Panel) -> tuple[int, list[str], AdjustmentResult]:
        """Fit text element using configured overflow strategy.

        Args:
            text: Text element to fit.
            panel: Parent panel.

        Returns:
            Tuple of (font_size, lines, adjustment_result).
        """
        # Select strategy
        strategy = text.overflow_strategy
        if strategy == OverflowStrategy.AUTO:
            strategy = self._select_auto_strategy(text)

        original_font_size = text.font_size

        # Apply strategy
        if strategy == OverflowStrategy.SHRINK:
            final_size, content = self._apply_shrink_strategy(text, panel)
            lines = [content]
            truncated = content != text.content and content.endswith("...")
        elif strategy == OverflowStrategy.WRAP:
            final_size, lines = self._apply_wrap_strategy(text, panel)
            truncated = False
        elif strategy == OverflowStrategy.TRUNCATE:
            final_size, content = self._apply_truncate_strategy(text, panel)
            lines = [content]
            truncated = content != text.content
        else:
            # Fallback
            final_size = text.font_size
            lines = [text.content]
            truncated = False

        # Create adjustment result
        was_adjusted = (final_size != original_font_size) or truncated or (len(lines) > 1)
        result = AdjustmentResult(
            was_adjusted=was_adjusted,
            strategy_applied=strategy,
            original_font_size=original_font_size,
            final_font_size=final_size,
            lines_used=len(lines),
            content_truncated=truncated,
        )

        return (final_size, lines, result)


    def _render_border(self, x: float, y: float, width: float, height: float, border: Border) -> None:
        """Render a border around a region.

        Args:
            x: X position in points.
            y: Y position in points.
            width: Width in points.
            height: Height in points.
            border: Border styling configuration.
        """
        if self._canvas is None:
            return

        self._canvas.saveState()

        # Set border color and width
        self._canvas.setStrokeColorRGB(*border.color.to_tuple())
        self._canvas.setLineWidth(border.width)

        # Set dash pattern based on style
        if border.style == BorderStyle.DASHED:
            self._canvas.setDash(6, 3)
        elif border.style == BorderStyle.DOTTED:
            self._canvas.setDash(1, 2)
        elif border.style == BorderStyle.DECORATIVE:
            # Double line effect with varying dash
            self._canvas.setDash(8, 2, 2, 2)
        # SOLID has no dash pattern

        # Draw rectangle with optional rounded corners
        if border.corner_radius > 0:
            self._canvas.roundRect(x, y, width, height, border.corner_radius, fill=0, stroke=1)
        else:
            self._canvas.rect(x, y, width, height, fill=0, stroke=1)

        self._canvas.restoreState()

    def _get_font_name(self, family: str, style: str) -> str:
        """Get ReportLab font name from family and style.

        Args:
            family: Font family name.
            style: Font style (normal, bold, italic, bold_italic).

        Returns:
            ReportLab font name.
        """
        # Map common font families
        family_map = {
            "helvetica": "Helvetica",
            "times": "Times-Roman",
            "courier": "Courier",
        }
        base_font = family_map.get(family.lower(), family)

        # Apply style
        if style == "bold":
            if base_font == "Times-Roman":
                return "Times-Bold"
            return f"{base_font}-Bold"
        elif style == "italic":
            if base_font == "Times-Roman":
                return "Times-Italic"
            elif base_font == "Helvetica":
                return "Helvetica-Oblique"
            return f"{base_font}-Italic"
        elif style == "bold_italic":
            if base_font == "Times-Roman":
                return "Times-BoldItalic"
            elif base_font == "Helvetica":
                return "Helvetica-BoldOblique"
            return f"{base_font}-BoldItalic"

        return base_font

    def draw_fold_lines(self, fold_type: str) -> None:
        """Draw fold guide lines on the canvas.

        Args:
            fold_type: Type of fold (half_fold, quarter_fold, tri_fold).
        """
        if self._canvas is None:
            raise RuntimeError("Canvas not initialized. Call create_canvas first.")

        # Set fold line style
        self._canvas.setStrokeColorRGB(0.7, 0.7, 0.7)  # Light gray
        self._canvas.setLineWidth(FOLD_LINE_WIDTH)
        self._canvas.setDash(3, 3)  # Dashed line

        page_width = inches_to_points(PAGE_WIDTH)
        page_height = inches_to_points(PAGE_HEIGHT)

        if fold_type == "half_fold":
            self._draw_half_fold_lines(page_width, page_height)
        elif fold_type == "quarter_fold":
            self._draw_quarter_fold_lines(page_width, page_height)
        elif fold_type == "tri_fold":
            self._draw_tri_fold_lines(page_width, page_height)

        # Reset dash pattern
        self._canvas.setDash()

    def _draw_half_fold_lines(self, width: float, height: float) -> None:
        """Draw fold line for half-fold card.

        Single horizontal fold at the middle of the page.
        """
        mid_y = height / 2
        self._canvas.line(0, mid_y, width, mid_y)

    def _draw_quarter_fold_lines(self, width: float, height: float) -> None:
        """Draw fold lines for quarter-fold card.

        Horizontal fold at middle, vertical fold at middle.
        """
        mid_x = width / 2
        mid_y = height / 2

        # Horizontal fold
        self._canvas.line(0, mid_y, width, mid_y)

        # Vertical fold
        self._canvas.line(mid_x, 0, mid_x, height)

    def _draw_tri_fold_lines(self, width: float, height: float) -> None:
        """Draw fold lines for tri-fold card.

        Two vertical folds dividing the page into thirds.
        """
        third_x = width / 3

        # First fold line
        self._canvas.line(third_x, 0, third_x, height)

        # Second fold line
        self._canvas.line(third_x * 2, 0, third_x * 2, height)

    def save(self, path: Path) -> None:
        """Save the rendered PDF to a file.

        Args:
            path: Output file path.
        """
        if self._canvas is None:
            raise RuntimeError("Canvas not initialized. Call create_canvas first.")

        self._canvas.save()

    def render_card(self, card: Card) -> None:
        """Render a complete card with all panels.

        Args:
            card: Card to render.
        """
        if self._canvas is None:
            raise RuntimeError("Canvas not initialized. Call create_canvas first.")

        # Render each panel
        for panel in card.panels:
            self.render_panel(panel)

        # Draw fold lines
        self.draw_fold_lines(card.fold_type.value)

    def render(self, card: Card, output_path: Path) -> None:
        """Convenience method to render a card to PDF in one call.

        Args:
            card: Card to render.
            output_path: Output PDF file path.
        """
        self.create_canvas(output_path)
        self.setup_canvas(PAGE_WIDTH, PAGE_HEIGHT)
        self.render_card(card)
        self.save(output_path)


def create_half_fold_panels(
    greeting: str = "Happy Holidays!",
    message: str = "",
    front_color: Color | None = None,
    text_color: Color | None = None,
) -> list[Panel]:
    """Create panels for a half-fold card layout.

    Args:
        greeting: Front panel greeting text.
        message: Inside message text.
        front_color: Front panel background color.
        text_color: Text color.

    Returns:
        List of panels for half-fold layout.
    """
    if front_color is None:
        front_color = Colors.WHITE
    if text_color is None:
        text_color = Colors.BLACK

    # Half-fold: page folds horizontally
    # Top half = inside panels, Bottom half = front/back
    half_height = PAGE_HEIGHT / 2
    half_width = PAGE_WIDTH / 2

    panels = [
        # Front panel (bottom right when unfolded)
        Panel(
            position="front",
            x=half_width,
            y=0,
            width=half_width,
            height=half_height,
            background_color=front_color,
            text_elements=[
                TextElement(
                    content=greeting,
                    x=half_width / 2,
                    y=half_height / 2,
                    font_family="Helvetica",
                    font_size=36,
                    color=text_color,
                )
            ],
        ),
        # Back panel (bottom left when unfolded)
        Panel(
            position="back",
            x=0,
            y=0,
            width=half_width,
            height=half_height,
        ),
        # Inside left (top left when unfolded)
        Panel(
            position="inside_left",
            x=0,
            y=half_height,
            width=half_width,
            height=half_height,
        ),
        # Inside right (top right when unfolded)
        Panel(
            position="inside_right",
            x=half_width,
            y=half_height,
            width=half_width,
            height=half_height,
            text_elements=[
                TextElement(
                    content=message,
                    x=0.5,
                    y=half_height / 2,
                    font_family="Helvetica",
                    font_size=14,
                    color=text_color,
                )
            ] if message else [],
        ),
    ]

    return panels
