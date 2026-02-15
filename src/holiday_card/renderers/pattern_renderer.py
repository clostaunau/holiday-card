"""Pattern fill rendering for shapes.

This module provides rendering of pattern fills (stripes, dots, grid, checkerboard)
using ReportLab's Form XObject (beginForm/endForm) for efficient tiling patterns.
"""

import logging
import math

from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas

from holiday_card.core.models import PatternFill, PatternType

logger = logging.getLogger(__name__)


class PatternRenderer:
    """Renders pattern fills for shapes.

    Supports stripe, dot, grid, and checkerboard patterns using ReportLab's
    Form XObjects for efficient tiling. Patterns can be rotated and scaled.
    """

    POINTS_PER_INCH = 72  # ReportLab uses points (72 pts/inch)

    def _create_stripe_tile(
        self,
        canvas: Canvas,
        pattern: PatternFill,
        tile_size: float
    ) -> None:
        """Create a stripe pattern tile.

        Args:
            canvas: ReportLab canvas
            pattern: PatternFill configuration
            tile_size: Size of the tile in points
        """
        # Get colors
        colors = [HexColor(c if c.startswith('#') else f'#{c}') for c in pattern.colors]

        # Calculate stripe width based on spacing and number of colors
        num_stripes = len(colors)
        stripe_width = tile_size / num_stripes

        # Draw stripes
        for i, color in enumerate(colors):
            canvas.setFillColor(color)
            x = i * stripe_width
            canvas.rect(x, 0, stripe_width, tile_size, fill=1, stroke=0)

        logger.debug(
            f"Created stripe tile: size={tile_size:.2f}pts, "
            f"stripes={num_stripes}, stripe_width={stripe_width:.2f}pts"
        )

    def _create_dot_tile(
        self,
        canvas: Canvas,
        pattern: PatternFill,
        tile_size: float
    ) -> None:
        """Create a dot/polka pattern tile.

        Args:
            canvas: ReportLab canvas
            pattern: PatternFill configuration
            tile_size: Size of the tile in points
        """
        # Get colors (use first color for dots, second for background if available)
        dot_color = HexColor(
            pattern.colors[0] if pattern.colors[0].startswith('#')
            else f'#{pattern.colors[0]}'
        )
        bg_color = None
        if len(pattern.colors) > 1:
            bg_color = HexColor(
                pattern.colors[1] if pattern.colors[1].startswith('#')
                else f'#{pattern.colors[1]}'
            )

        # Draw background if specified
        if bg_color:
            canvas.setFillColor(bg_color)
            canvas.rect(0, 0, tile_size, tile_size, fill=1, stroke=0)

        # Draw dot in center
        canvas.setFillColor(dot_color)
        dot_radius = tile_size * 0.3  # Dot is 30% of tile size
        center = tile_size / 2
        canvas.circle(center, center, dot_radius, fill=1, stroke=0)

        logger.debug(
            f"Created dot tile: size={tile_size:.2f}pts, "
            f"radius={dot_radius:.2f}pts"
        )

    def _create_grid_tile(
        self,
        canvas: Canvas,
        pattern: PatternFill,
        tile_size: float
    ) -> None:
        """Create a grid pattern tile.

        Args:
            canvas: ReportLab canvas
            pattern: PatternFill configuration
            tile_size: Size of the tile in points
        """
        # Get grid line color
        line_color = HexColor(
            pattern.colors[0] if pattern.colors[0].startswith('#')
            else f'#{pattern.colors[0]}'
        )

        # Draw grid lines
        canvas.setStrokeColor(line_color)
        line_width = max(1.0, tile_size * 0.05)  # 5% of tile size, minimum 1pt
        canvas.setLineWidth(line_width)

        # Draw horizontal and vertical lines at tile edges
        canvas.line(0, 0, tile_size, 0)  # Bottom edge
        canvas.line(0, 0, 0, tile_size)  # Left edge

        logger.debug(
            f"Created grid tile: size={tile_size:.2f}pts, "
            f"line_width={line_width:.2f}pts"
        )

    def _create_checkerboard_tile(
        self,
        canvas: Canvas,
        pattern: PatternFill,
        tile_size: float
    ) -> None:
        """Create a checkerboard pattern tile.

        Args:
            canvas: ReportLab canvas
            pattern: PatternFill configuration
            tile_size: Size of the tile in points
        """
        # Get colors (two colors for checkerboard)
        color1 = HexColor(
            pattern.colors[0] if pattern.colors[0].startswith('#')
            else f'#{pattern.colors[0]}'
        )
        color2 = HexColor(
            pattern.colors[1] if pattern.colors[1].startswith('#')
            else f'#{pattern.colors[1]}'
        ) if len(pattern.colors) > 1 else HexColor('#FFFFFF')

        # Create 2x2 checkerboard tile
        half_size = tile_size / 2

        # Top-left and bottom-right: color1
        canvas.setFillColor(color1)
        canvas.rect(0, half_size, half_size, half_size, fill=1, stroke=0)  # Top-left
        canvas.rect(half_size, 0, half_size, half_size, fill=1, stroke=0)  # Bottom-right

        # Top-right and bottom-left: color2
        canvas.setFillColor(color2)
        canvas.rect(half_size, half_size, half_size, half_size, fill=1, stroke=0)  # Top-right
        canvas.rect(0, 0, half_size, half_size, fill=1, stroke=0)  # Bottom-left

        logger.debug(
            f"Created checkerboard tile: size={tile_size:.2f}pts"
        )

    def render_pattern_fill(
        self,
        canvas: Canvas,
        pattern: PatternFill,
        x: float,
        y: float,
        width: float,
        height: float
    ) -> None:
        """Render a pattern fill to the canvas.

        Creates a tiling pattern using ReportLab Form XObjects and fills
        the specified rectangular area.

        Args:
            canvas: ReportLab canvas
            pattern: PatternFill configuration
            x: Fill area X in points
            y: Fill area Y in points
            width: Fill area width in points
            height: Fill area height in points
        """
        try:
            # Calculate tile size based on spacing (convert inches to points)
            base_tile_size = pattern.spacing * self.POINTS_PER_INCH
            tile_size = base_tile_size * pattern.scale

            # Ensure minimum tile size for visibility
            tile_size = max(tile_size, 2.0)  # Minimum 2 points

            # Create Form XObject for the pattern tile
            form_name = f"pattern_{pattern.pattern_type.value}_{id(pattern)}"

            # Begin form (tile)
            canvas.beginForm(form_name, lowerx=0, lowery=0,
                           upperx=tile_size, uppery=tile_size)

            # Create the appropriate tile pattern
            if pattern.pattern_type == PatternType.STRIPES:
                self._create_stripe_tile(canvas, pattern, tile_size)
            elif pattern.pattern_type == PatternType.DOTS:
                self._create_dot_tile(canvas, pattern, tile_size)
            elif pattern.pattern_type == PatternType.GRID:
                self._create_grid_tile(canvas, pattern, tile_size)
            elif pattern.pattern_type == PatternType.CHECKERBOARD:
                self._create_checkerboard_tile(canvas, pattern, tile_size)
            else:
                logger.warning(f"Unsupported pattern type: {pattern.pattern_type}")
                canvas.endForm()
                return

            # End form definition
            canvas.endForm()

            # Save canvas state for transformations
            canvas.saveState()

            # CRITICAL: Create clipping path to constrain pattern to shape bounds
            # Without this, pattern tiles extend beyond the specified area
            path = canvas.beginPath()
            path.rect(x, y, width, height)
            canvas.clipPath(path, stroke=0, fill=0)

            # Apply rotation if specified
            if pattern.rotation != 0:
                # Rotate around the center of the fill area
                center_x = x + width / 2
                center_y = y + height / 2
                canvas.translate(center_x, center_y)
                canvas.rotate(pattern.rotation)
                canvas.translate(-center_x, -center_y)

            # Tile the pattern across the fill area
            # Calculate how many tiles we need
            num_tiles_x = math.ceil(width / tile_size) + 1
            num_tiles_y = math.ceil(height / tile_size) + 1

            # Move to starting position before tiling
            canvas.translate(x, y)

            # Draw the tiled pattern
            for i in range(num_tiles_x):
                for j in range(num_tiles_y):
                    canvas.doForm(form_name)
                    canvas.translate(0, tile_size)
                canvas.translate(tile_size, -num_tiles_y * tile_size)

            # Restore canvas state
            canvas.restoreState()

            logger.info(
                f"Rendered {pattern.pattern_type.value} pattern: "
                f"area=({x:.2f},{y:.2f},{width:.2f},{height:.2f})pts, "
                f"tile_size={tile_size:.2f}pts, rotation={pattern.rotation}°"
            )

        except Exception as e:
            logger.error(f"Failed to render pattern fill: {e}")
            # Fallback: draw solid fill with first color
            if pattern.colors:
                fallback_color = HexColor(
                    pattern.colors[0] if pattern.colors[0].startswith('#')
                    else f'#{pattern.colors[0]}'
                )
                canvas.setFillColor(fallback_color)
                canvas.rect(x, y, width, height, fill=1, stroke=0)
                logger.warning("Fell back to solid fill due to pattern error")
