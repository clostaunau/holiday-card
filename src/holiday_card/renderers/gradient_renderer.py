"""Gradient rendering for linear and radial gradients.

This module provides rendering of gradient fills using ReportLab's
built-in gradient APIs.
"""

import logging

from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas

from holiday_card.core.models import LinearGradientFill, RadialGradientFill
from holiday_card.utils.gradient_utils import gradient_endpoints, radial_gradient_endpoints

logger = logging.getLogger(__name__)


class GradientRenderer:
    """Renders gradient fills to ReportLab canvas.

    Supports linear and radial gradients with multiple color stops.
    Uses ReportLab's native gradient APIs for smooth rendering.
    """

    POINTS_PER_INCH = 72  # ReportLab uses points (72 pts/inch)

    def render_linear_gradient(
        self,
        canvas: Canvas,
        gradient: LinearGradientFill,
        x: float,
        y: float,
        width: float,
        height: float,
        panel_offset_x: float = 0.0,
        panel_offset_y: float = 0.0
    ) -> None:
        """Render linear gradient fill.

        Args:
            canvas: ReportLab canvas
            gradient: LinearGradientFill model
            x: Shape X position in inches
            y: Shape Y position in inches
            width: Shape width in inches
            height: Shape height in inches
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        try:
            # Convert to points
            x_pts = (panel_offset_x + x) * self.POINTS_PER_INCH
            y_pts = (panel_offset_y + y) * self.POINTS_PER_INCH
            width_pts = width * self.POINTS_PER_INCH
            height_pts = height * self.POINTS_PER_INCH

            # Calculate gradient endpoints from angle
            start, end = gradient_endpoints(
                gradient.angle,
                width_pts,
                height_pts,
                x_pts,
                y_pts
            )

            # Convert color stops to ReportLab format
            colors = [HexColor(stop.color) for stop in gradient.stops]
            positions = [stop.position for stop in gradient.stops]

            logger.debug(
                f"Rendering linear gradient: angle={gradient.angle}, "
                f"stops={len(gradient.stops)}, bounds=({x_pts},{y_pts},{width_pts},{height_pts})"
            )

            # Create linear gradient using ReportLab API
            canvas.saveState()
            canvas.linearGradient(
                x_pts, y_pts, width_pts, height_pts,
                colors,
                positions=positions,
                extend=True
            )
            canvas.restoreState()

        except Exception as e:
            logger.error(f"Failed to render linear gradient: {e}")
            # Fallback to first color as solid fill
            if gradient.stops:
                canvas.setFillColor(HexColor(gradient.stops[0].color))

    def render_radial_gradient(
        self,
        canvas: Canvas,
        gradient: RadialGradientFill,
        x: float,
        y: float,
        width: float,
        height: float,
        panel_offset_x: float = 0.0,
        panel_offset_y: float = 0.0
    ) -> None:
        """Render radial gradient fill.

        Args:
            canvas: ReportLab canvas
            gradient: RadialGradientFill model
            x: Shape X position in inches
            y: Shape Y position in inches
            width: Shape width in inches
            height: Shape height in inches
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        try:
            # Convert to points
            x_pts = (panel_offset_x + x) * self.POINTS_PER_INCH
            y_pts = (panel_offset_y + y) * self.POINTS_PER_INCH
            width_pts = width * self.POINTS_PER_INCH
            height_pts = height * self.POINTS_PER_INCH

            # Calculate gradient center and radius
            center, radius = radial_gradient_endpoints(
                gradient.center_x,
                gradient.center_y,
                gradient.radius,
                width_pts,
                height_pts,
                x_pts,
                y_pts
            )

            # Convert color stops to ReportLab format
            colors = [HexColor(stop.color) for stop in gradient.stops]
            positions = [stop.position for stop in gradient.stops]

            logger.debug(
                f"Rendering radial gradient: center={center}, radius={radius}, "
                f"stops={len(gradient.stops)}"
            )

            # Create radial gradient using ReportLab API
            canvas.saveState()
            canvas.radialGradient(
                center[0], center[1], radius,
                colors,
                positions=positions,
                extend=True
            )
            canvas.restoreState()

        except Exception as e:
            logger.error(f"Failed to render radial gradient: {e}")
            # Fallback to first color as solid fill
            if gradient.stops:
                canvas.setFillColor(HexColor(gradient.stops[0].color))
