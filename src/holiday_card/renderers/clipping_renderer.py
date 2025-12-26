"""Clipping mask rendering for images.

This module provides rendering of image clipping masks using ReportLab's
clipPath functionality with support for various shapes.
"""

import logging
import math

from reportlab.graphics.shapes import Path
from reportlab.pdfgen.canvas import Canvas

from holiday_card.core.models import (
    CircleClipMask,
    ClipMask,
    EllipseClipMask,
    RectangleClipMask,
    StarClipMask,
    SVGPathClipMask,
)
from holiday_card.utils.svg_parser import SVGPathParser

logger = logging.getLogger(__name__)


class ClippingRenderer:
    """Renders clipping masks for images.

    Supports circle, rectangle, ellipse, star, and SVG path clipping masks.
    Uses ReportLab's clipPath API with saveState/restoreState for proper isolation.
    """

    POINTS_PER_INCH = 72  # ReportLab uses points (72 pts/inch)

    def create_circle_path(
        self,
        mask: CircleClipMask,
        image_x: float,
        image_y: float
    ) -> Path:
        """Create a circular clipping path.

        Args:
            mask: CircleClipMask model with center and radius
            image_x: Image X position in points
            image_y: Image Y position in points

        Returns:
            ReportLab Path object for circular clip
        """
        # Convert mask coordinates (in inches) to points
        center_x_pts = mask.center_x * self.POINTS_PER_INCH
        center_y_pts = mask.center_y * self.POINTS_PER_INCH
        radius_pts = mask.radius * self.POINTS_PER_INCH

        # Create path with circle
        path = Path()
        path.circle(
            image_x + center_x_pts,
            image_y + center_y_pts,
            radius_pts
        )
        path.close()

        logger.debug(
            f"Created circle clip path: center=({center_x_pts:.2f},{center_y_pts:.2f}), "
            f"radius={radius_pts:.2f}pts"
        )

        return path

    def create_rectangle_path(
        self,
        mask: RectangleClipMask,
        image_x: float,
        image_y: float
    ) -> Path:
        """Create a rectangular clipping path.

        Args:
            mask: RectangleClipMask model
            image_x: Image X position in points
            image_y: Image Y position in points

        Returns:
            ReportLab Path object for rectangular clip
        """
        # Convert to points
        x_pts = mask.x * self.POINTS_PER_INCH
        y_pts = mask.y * self.POINTS_PER_INCH
        width_pts = mask.width * self.POINTS_PER_INCH
        height_pts = mask.height * self.POINTS_PER_INCH

        # Create rectangular path
        path = Path()
        path.rect(
            image_x + x_pts,
            image_y + y_pts,
            width_pts,
            height_pts
        )
        path.close()

        logger.debug(
            f"Created rectangle clip path: "
            f"bounds=({x_pts:.2f},{y_pts:.2f},{width_pts:.2f},{height_pts:.2f})pts"
        )

        return path

    def create_ellipse_path(
        self,
        mask: EllipseClipMask,
        image_x: float,
        image_y: float
    ) -> Path:
        """Create an elliptical clipping path.

        Args:
            mask: EllipseClipMask model
            image_x: Image X position in points
            image_y: Image Y position in points

        Returns:
            ReportLab Path object for elliptical clip
        """
        # Convert to points
        center_x_pts = mask.center_x * self.POINTS_PER_INCH
        center_y_pts = mask.center_y * self.POINTS_PER_INCH
        radius_x_pts = mask.radius_x * self.POINTS_PER_INCH
        radius_y_pts = mask.radius_y * self.POINTS_PER_INCH

        # Create ellipse path using ellipse method
        path = Path()
        path.ellipse(
            image_x + center_x_pts,
            image_y + center_y_pts,
            radius_x_pts,
            radius_y_pts
        )
        path.close()

        logger.debug(
            f"Created ellipse clip path: center=({center_x_pts:.2f},{center_y_pts:.2f}), "
            f"radii=({radius_x_pts:.2f},{radius_y_pts:.2f})pts"
        )

        return path

    def create_star_path(
        self,
        mask: StarClipMask,
        image_x: float,
        image_y: float
    ) -> Path:
        """Create a star-shaped clipping path.

        Args:
            mask: StarClipMask model with points and radii
            image_x: Image X position in points
            image_y: Image Y position in points

        Returns:
            ReportLab Path object for star clip
        """
        # Convert to points
        center_x_pts = mask.center_x * self.POINTS_PER_INCH
        center_y_pts = mask.center_y * self.POINTS_PER_INCH
        outer_radius_pts = mask.outer_radius * self.POINTS_PER_INCH
        inner_radius_pts = mask.inner_radius * self.POINTS_PER_INCH

        # Calculate star points
        path = Path()
        angle_step = 2 * math.pi / mask.points

        # Start at the first outer point (top)
        first_outer_angle = -math.pi / 2  # Start at top
        first_x = center_x_pts + outer_radius_pts * math.cos(first_outer_angle)
        first_y = center_y_pts + outer_radius_pts * math.sin(first_outer_angle)
        path.moveTo(image_x + first_x, image_y + first_y)

        # Generate star points alternating between outer and inner radii
        for i in range(mask.points):
            # Inner point
            inner_angle = first_outer_angle + (i + 0.5) * angle_step
            inner_x = center_x_pts + inner_radius_pts * math.cos(inner_angle)
            inner_y = center_y_pts + inner_radius_pts * math.sin(inner_angle)
            path.lineTo(image_x + inner_x, image_y + inner_y)

            # Outer point (next)
            if i < mask.points - 1:
                outer_angle = first_outer_angle + (i + 1) * angle_step
                outer_x = center_x_pts + outer_radius_pts * math.cos(outer_angle)
                outer_y = center_y_pts + outer_radius_pts * math.sin(outer_angle)
                path.lineTo(image_x + outer_x, image_y + outer_y)

        path.close()

        logger.debug(
            f"Created star clip path: points={mask.points}, "
            f"outer_r={outer_radius_pts:.2f}pts, inner_r={inner_radius_pts:.2f}pts"
        )

        return path

    def create_svg_path(
        self,
        mask: SVGPathClipMask,
        image_x: float,
        image_y: float
    ) -> Path:
        """Create an SVG path-based clipping path.

        Args:
            mask: SVGPathClipMask model with path data
            image_x: Image X position in points
            image_y: Image Y position in points

        Returns:
            ReportLab Path object for SVG path clip
        """
        # Parse SVG path data
        parser = SVGPathParser()
        commands = parser.parse(mask.path_data)

        # Create ReportLab path from SVG commands
        path = Path()
        current_x = 0.0
        current_y = 0.0
        start_x = 0.0
        start_y = 0.0

        for cmd in commands:
            cmd_type = cmd.command.upper()
            params = cmd.params

            if cmd_type == "M":  # Move
                if len(params) >= 2:
                    x = params[0] * mask.scale
                    y = params[1] * mask.scale
                    path.moveTo(image_x + x, image_y + y)
                    current_x = x
                    current_y = y
                    start_x = x
                    start_y = y

            elif cmd_type == "L":  # Line
                if len(params) >= 2:
                    x = params[0] * mask.scale
                    y = params[1] * mask.scale
                    path.lineTo(image_x + x, image_y + y)
                    current_x = x
                    current_y = y

            elif cmd_type == "H":  # Horizontal line
                if len(params) >= 1:
                    x = params[0] * mask.scale
                    path.lineTo(image_x + x, image_y + current_y)
                    current_x = x

            elif cmd_type == "V":  # Vertical line
                if len(params) >= 1:
                    y = params[0] * mask.scale
                    path.lineTo(image_x + current_x, image_y + y)
                    current_y = y

            elif cmd_type == "C":  # Cubic bezier
                if len(params) >= 6:
                    cp1x = params[0] * mask.scale
                    cp1y = params[1] * mask.scale
                    cp2x = params[2] * mask.scale
                    cp2y = params[3] * mask.scale
                    x = params[4] * mask.scale
                    y = params[5] * mask.scale
                    path.curveTo(
                        image_x + cp1x, image_y + cp1y,
                        image_x + cp2x, image_y + cp2y,
                        image_x + x, image_y + y
                    )
                    current_x = x
                    current_y = y

            elif cmd_type == "Q":  # Quadratic bezier
                if len(params) >= 4:
                    cpx = params[0] * mask.scale
                    cpy = params[1] * mask.scale
                    x = params[2] * mask.scale
                    y = params[3] * mask.scale
                    # Convert quadratic to cubic bezier
                    cp1x = current_x + 2/3 * (cpx - current_x)
                    cp1y = current_y + 2/3 * (cpy - current_y)
                    cp2x = x + 2/3 * (cpx - x)
                    cp2y = y + 2/3 * (cpy - y)
                    path.curveTo(
                        image_x + cp1x, image_y + cp1y,
                        image_x + cp2x, image_y + cp2y,
                        image_x + x, image_y + y
                    )
                    current_x = x
                    current_y = y

            elif cmd_type == "Z":  # Close path
                path.close()
                current_x = start_x
                current_y = start_y

        logger.debug(f"Created SVG path clip: scale={mask.scale}, commands={len(commands)}")

        return path

    def apply_clip_mask(
        self,
        canvas: Canvas,
        mask: ClipMask,
        image_x: float,
        image_y: float
    ) -> None:
        """Apply a clipping mask to the canvas.

        This method should be called after saveState() and before drawing the image.
        The caller is responsible for calling restoreState() after drawing.

        Args:
            canvas: ReportLab canvas
            mask: ClipMask (discriminated union)
            image_x: Image X position in points
            image_y: Image Y position in points
        """
        try:
            # Create appropriate path based on mask type
            if mask.type == "circle":
                path = self.create_circle_path(mask, image_x, image_y)
            elif mask.type == "rectangle":
                path = self.create_rectangle_path(mask, image_x, image_y)
            elif mask.type == "ellipse":
                path = self.create_ellipse_path(mask, image_x, image_y)
            elif mask.type == "star":
                path = self.create_star_path(mask, image_x, image_y)
            elif mask.type == "svg_path":
                path = self.create_svg_path(mask, image_x, image_y)
            else:
                logger.warning(f"Unsupported clip mask type: {mask.type}")
                return

            # Apply clipping path to canvas
            canvas.clipPath(path, stroke=0, fill=1)

            logger.info(f"Applied {mask.type} clipping mask at ({image_x:.2f},{image_y:.2f})pts")

        except Exception as e:
            logger.error(f"Failed to apply clipping mask: {e}")
            # Don't raise - allow image to render without clipping
