"""Shape rendering logic for vector graphics.

This module provides rendering methods for all shape types using ReportLab
drawing primitives. Handles conversion from inches to points, color parsing,
and geometric calculations for complex shapes like stars.
"""

import logging
import math

from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas

from holiday_card.core.models import (
    Circle,
    Line,
    LinearGradientFill,
    PatternFill,
    RadialGradientFill,
    Rectangle,
    SolidFill,
    Star,
    SVGPath,
    Triangle,
)
from holiday_card.utils.svg_parser import SVGCommand, SVGPathParser

logger = logging.getLogger(__name__)


class ShapeRenderer:
    """Renders vector graphics shapes to ReportLab canvas.

    Converts shape models to ReportLab drawing commands, handling:
    - Measurement conversion (inches to points)
    - Color conversion (hex strings to ReportLab Color objects)
    - Geometric calculations (star points, rotation centers)
    - Fill and stroke styling
    - SVG path rendering with full command support
    """

    POINTS_PER_INCH = 72  # ReportLab uses points (72 pts/inch)

    def __init__(self):
        """Initialize shape renderer with SVG parser."""
        self.svg_parser = SVGPathParser()
        self._gradient_renderer = None  # Lazy loaded to avoid circular imports
        self._pattern_renderer = None  # Lazy loaded to avoid circular imports

    def render_shape(
        self,
        canvas: Canvas,
        shape: Rectangle | Circle | Triangle | Star | Line | SVGPath,
        panel_offset_x: float,
        panel_offset_y: float
    ) -> None:
        """Render any shape type to canvas.

        Args:
            canvas: ReportLab canvas to draw on
            shape: Shape instance to render
            panel_offset_x: Panel X position in inches
            panel_offset_y: Panel Y position in inches
        """
        if isinstance(shape, Rectangle):
            self.render_rectangle(canvas, shape, panel_offset_x, panel_offset_y)
        elif isinstance(shape, Circle):
            self.render_circle(canvas, shape, panel_offset_x, panel_offset_y)
        elif isinstance(shape, Triangle):
            self.render_triangle(canvas, shape, panel_offset_x, panel_offset_y)
        elif isinstance(shape, Star):
            self.render_star(canvas, shape, panel_offset_x, panel_offset_y)
        elif isinstance(shape, Line):
            self.render_line(canvas, shape, panel_offset_x, panel_offset_y)
        elif isinstance(shape, SVGPath):
            self.render_svg_path(canvas, shape, panel_offset_x, panel_offset_y)

    def render_svg_path(
        self,
        canvas: Canvas,
        svg_path: SVGPath,
        panel_offset_x: float,
        panel_offset_y: float
    ) -> None:
        """Render SVG path shape using ReportLab Path API.

        Args:
            canvas: ReportLab canvas
            svg_path: SVGPath shape instance
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        try:
            # Parse SVG path data into commands
            commands = self.svg_parser.parse(svg_path.path_data)
            if not commands:
                logger.warning(f"SVG path has no valid commands: {svg_path.path_data}")
                return

            # Create ReportLab Path object
            path = canvas.beginPath()

            # Track current position for relative commands
            current_x = 0.0
            current_y = 0.0
            last_control_x = 0.0  # For smooth curve commands
            last_control_y = 0.0

            # Apply scale and panel offset
            scale = svg_path.scale

            def to_abs_x(x: float) -> float:
                """Convert inches to absolute points with scale and offset."""
                return (panel_offset_x + x * scale) * self.POINTS_PER_INCH

            def to_abs_y(y: float) -> float:
                """Convert inches to absolute points with scale and offset."""
                return (panel_offset_y + y * scale) * self.POINTS_PER_INCH

            # Process each command
            for cmd in commands:
                try:
                    if cmd.command in (SVGCommand.MOVE, SVGCommand.MOVE_REL):
                        # Move command
                        is_relative = cmd.command == SVGCommand.MOVE_REL
                        for i in range(0, len(cmd.params), 2):
                            x, y = cmd.params[i], cmd.params[i + 1]
                            if is_relative:
                                current_x += x
                                current_y += y
                            else:
                                current_x = x
                                current_y = y

                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)
                            path.moveTo(abs_x, abs_y)

                    elif cmd.command in (SVGCommand.LINE, SVGCommand.LINE_REL):
                        # Line to command
                        is_relative = cmd.command == SVGCommand.LINE_REL
                        for i in range(0, len(cmd.params), 2):
                            x, y = cmd.params[i], cmd.params[i + 1]
                            if is_relative:
                                current_x += x
                                current_y += y
                            else:
                                current_x = x
                                current_y = y

                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)
                            path.lineTo(abs_x, abs_y)

                    elif cmd.command in (SVGCommand.HORIZONTAL, SVGCommand.HORIZONTAL_REL):
                        # Horizontal line
                        is_relative = cmd.command == SVGCommand.HORIZONTAL_REL
                        for x in cmd.params:
                            if is_relative:
                                current_x += x
                            else:
                                current_x = x

                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)
                            path.lineTo(abs_x, abs_y)

                    elif cmd.command in (SVGCommand.VERTICAL, SVGCommand.VERTICAL_REL):
                        # Vertical line
                        is_relative = cmd.command == SVGCommand.VERTICAL_REL
                        for y in cmd.params:
                            if is_relative:
                                current_y += y
                            else:
                                current_y = y

                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)
                            path.lineTo(abs_x, abs_y)

                    elif cmd.command in (SVGCommand.CUBIC_BEZIER, SVGCommand.CUBIC_BEZIER_REL):
                        # Cubic Bezier curve
                        is_relative = cmd.command == SVGCommand.CUBIC_BEZIER_REL
                        for i in range(0, len(cmd.params), 6):
                            cp1x, cp1y, cp2x, cp2y, x, y = cmd.params[i:i+6]

                            if is_relative:
                                abs_cp1x = to_abs_x(current_x + cp1x)
                                abs_cp1y = to_abs_y(current_y + cp1y)
                                abs_cp2x = to_abs_x(current_x + cp2x)
                                abs_cp2y = to_abs_y(current_y + cp2y)
                                current_x += x
                                current_y += y
                            else:
                                abs_cp1x = to_abs_x(cp1x)
                                abs_cp1y = to_abs_y(cp1y)
                                abs_cp2x = to_abs_x(cp2x)
                                abs_cp2y = to_abs_y(cp2y)
                                current_x = x
                                current_y = y

                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)

                            path.curveTo(abs_cp1x, abs_cp1y, abs_cp2x, abs_cp2y, abs_x, abs_y)

                            # Track last control point for smooth curves
                            last_control_x = cp2x if not is_relative else current_x - x + cp2x
                            last_control_y = cp2y if not is_relative else current_y - y + cp2y

                    elif cmd.command in (SVGCommand.CUBIC_BEZIER_SMOOTH, SVGCommand.CUBIC_BEZIER_SMOOTH_REL):
                        # Smooth cubic Bezier (reflects last control point)
                        is_relative = cmd.command == SVGCommand.CUBIC_BEZIER_SMOOTH_REL
                        for i in range(0, len(cmd.params), 4):
                            cp2x, cp2y, x, y = cmd.params[i:i+4]

                            # Reflect last control point
                            cp1x = 2 * current_x - last_control_x
                            cp1y = 2 * current_y - last_control_y

                            if is_relative:
                                abs_cp1x = to_abs_x(cp1x)
                                abs_cp1y = to_abs_y(cp1y)
                                abs_cp2x = to_abs_x(current_x + cp2x)
                                abs_cp2y = to_abs_y(current_y + cp2y)
                                current_x += x
                                current_y += y
                            else:
                                abs_cp1x = to_abs_x(cp1x)
                                abs_cp1y = to_abs_y(cp1y)
                                abs_cp2x = to_abs_x(cp2x)
                                abs_cp2y = to_abs_y(cp2y)
                                current_x = x
                                current_y = y

                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)

                            path.curveTo(abs_cp1x, abs_cp1y, abs_cp2x, abs_cp2y, abs_x, abs_y)

                            last_control_x = cp2x if not is_relative else current_x - x + cp2x
                            last_control_y = cp2y if not is_relative else current_y - y + cp2y

                    elif cmd.command in (SVGCommand.QUADRATIC_BEZIER, SVGCommand.QUADRATIC_BEZIER_REL):
                        # Quadratic Bezier curve (convert to cubic)
                        is_relative = cmd.command == SVGCommand.QUADRATIC_BEZIER_REL
                        for i in range(0, len(cmd.params), 4):
                            cpx, cpy, x, y = cmd.params[i:i+4]

                            if is_relative:
                                abs_cpx = current_x + cpx
                                abs_cpy = current_y + cpy
                                current_x += x
                                current_y += y
                            else:
                                abs_cpx = cpx
                                abs_cpy = cpy
                                current_x = x
                                current_y = y

                            # Convert quadratic to cubic Bezier
                            # CP1 = start + 2/3 * (control - start)
                            # CP2 = end + 2/3 * (control - end)
                            start_x = (abs_x - to_abs_x(0)) / (scale * self.POINTS_PER_INCH) if i > 0 else current_x - (x if is_relative else 0)
                            start_y = (abs_y - to_abs_y(0)) / (scale * self.POINTS_PER_INCH) if i > 0 else current_y - (y if is_relative else 0)

                            cp1x = start_x + 2/3 * (abs_cpx - start_x)
                            cp1y = start_y + 2/3 * (abs_cpy - start_y)
                            cp2x = current_x + 2/3 * (abs_cpx - current_x)
                            cp2y = current_y + 2/3 * (abs_cpy - current_y)

                            abs_cp1x = to_abs_x(cp1x)
                            abs_cp1y = to_abs_y(cp1y)
                            abs_cp2x = to_abs_x(cp2x)
                            abs_cp2y = to_abs_y(cp2y)
                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)

                            path.curveTo(abs_cp1x, abs_cp1y, abs_cp2x, abs_cp2y, abs_x, abs_y)

                            last_control_x = abs_cpx
                            last_control_y = abs_cpy

                    elif cmd.command in (SVGCommand.QUADRATIC_BEZIER_SMOOTH, SVGCommand.QUADRATIC_BEZIER_SMOOTH_REL):
                        # Smooth quadratic Bezier
                        is_relative = cmd.command == SVGCommand.QUADRATIC_BEZIER_SMOOTH_REL
                        for i in range(0, len(cmd.params), 2):
                            x, y = cmd.params[i:i+2]

                            # Reflect last control point
                            cpx = 2 * current_x - last_control_x
                            cpy = 2 * current_y - last_control_y

                            if is_relative:
                                current_x += x
                                current_y += y
                            else:
                                current_x = x
                                current_y = y

                            # Convert to cubic (similar to Q command)
                            start_x = (abs_x - to_abs_x(0)) / (scale * self.POINTS_PER_INCH) if i > 0 else current_x - (x if is_relative else 0)
                            start_y = (abs_y - to_abs_y(0)) / (scale * self.POINTS_PER_INCH) if i > 0 else current_y - (y if is_relative else 0)

                            cp1x = start_x + 2/3 * (cpx - start_x)
                            cp1y = start_y + 2/3 * (cpy - start_y)
                            cp2x = current_x + 2/3 * (cpx - current_x)
                            cp2y = current_y + 2/3 * (cpy - current_y)

                            abs_cp1x = to_abs_x(cp1x)
                            abs_cp1y = to_abs_y(cp1y)
                            abs_cp2x = to_abs_x(cp2x)
                            abs_cp2y = to_abs_y(cp2y)
                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)

                            path.curveTo(abs_cp1x, abs_cp1y, abs_cp2x, abs_cp2y, abs_x, abs_y)

                            last_control_x = cpx
                            last_control_y = cpy

                    elif cmd.command in (SVGCommand.ARC, SVGCommand.ARC_REL):
                        # Elliptical arc - approximate with cubic Bezier curves
                        is_relative = cmd.command == SVGCommand.ARC_REL
                        for i in range(0, len(cmd.params), 7):
                            rx, ry, x_axis_rotation, large_arc, sweep, x, y = cmd.params[i:i+7]

                            start_x = current_x
                            start_y = current_y

                            if is_relative:
                                current_x += x
                                current_y += y
                            else:
                                current_x = x
                                current_y = y

                            # Simple arc approximation: just draw a line for now
                            # TODO: Implement proper arc-to-bezier conversion
                            logger.debug(f"Arc approximated as line: {cmd.params[i:i+7]}")
                            abs_x = to_abs_x(current_x)
                            abs_y = to_abs_y(current_y)
                            path.lineTo(abs_x, abs_y)

                    elif cmd.command in (SVGCommand.CLOSE, SVGCommand.CLOSE_REL):
                        # Close path
                        path.close()

                    else:
                        logger.warning(f"Unsupported SVG command: {cmd.command}")

                except (IndexError, ValueError) as e:
                    logger.warning(f"Error processing SVG command {cmd.command}: {e}")
                    continue

            # Apply opacity
            self._apply_opacity(canvas, svg_path.opacity)

            # Calculate bounding box center for rotation (approximate)
            # For now, use origin as rotation center
            center_x = to_abs_x(0)
            center_y = to_abs_y(0)
            self._apply_rotation(canvas, svg_path.rotation, center_x, center_y)

            # Determine fill and stroke from fill/fill_color fields
            fill_style = self._get_fill_style(svg_path)
            has_stroke = svg_path.stroke_color is not None and svg_path.stroke_width > 0

            # Apply gradient fill if using gradient
            if isinstance(fill_style, (LinearGradientFill, RadialGradientFill)):
                # Use gradient renderer for fill - use approximate bounds for SVG paths
                self._apply_gradient_fill(canvas, fill_style, 0, 0, 8.5, 11.0, panel_offset_x, panel_offset_y)
                has_fill = False  # Don't use solid fill
            elif isinstance(fill_style, SolidFill):
                canvas.setFillColor(self._hex_to_color(fill_style.color))
                has_fill = True
            elif svg_path.fill_color:
                canvas.setFillColor(self._hex_to_color(svg_path.fill_color))
                has_fill = True
            else:
                has_fill = False

            if has_stroke:
                canvas.setStrokeColor(self._hex_to_color(svg_path.stroke_color))
                canvas.setLineWidth(svg_path.stroke_width)

            # Draw the path
            canvas.drawPath(path, stroke=int(has_stroke), fill=int(has_fill))

            # Restore state
            self._restore_rotation(canvas, svg_path.rotation)
            self._reset_opacity(canvas)

            logger.debug(f"Successfully rendered SVG path with {len(commands)} commands")

        except Exception as e:
            logger.error(f"Failed to render SVG path: {e}", exc_info=True)
            # Graceful degradation: skip this shape

    def _get_fill_style(self, shape):
        """Get the fill style for a shape, handling both fill and fill_color."""
        if hasattr(shape, 'fill') and shape.fill is not None:
            return shape.fill
        elif hasattr(shape, 'fill_color') and shape.fill_color is not None:
            return SolidFill(color=shape.fill_color)
        return None

    def _apply_gradient_fill(self, canvas, fill_style, x: float, y: float, width: float, height: float,
                             panel_offset_x: float, panel_offset_y: float):
        """Apply gradient fill using GradientRenderer.
        
        Args:
            canvas: ReportLab canvas
            fill_style: LinearGradientFill or RadialGradientFill
            x: Shape X in inches
            y: Shape Y in inches
            width: Shape width in inches
            height: Shape height in inches
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel offset Y in inches
        """
        # Lazy load to avoid circular imports
        if self._gradient_renderer is None:
            from holiday_card.renderers.gradient_renderer import GradientRenderer
            self._gradient_renderer = GradientRenderer()

        if isinstance(fill_style, LinearGradientFill):
            self._gradient_renderer.render_linear_gradient(
                canvas, fill_style, x, y, width, height, panel_offset_x, panel_offset_y
            )
        elif isinstance(fill_style, RadialGradientFill):
            self._gradient_renderer.render_radial_gradient(
                canvas, fill_style, x, y, width, height, panel_offset_x, panel_offset_y
            )

    def _apply_pattern_fill(self, canvas, fill_style: PatternFill,
                           x: float, y: float, width: float, height: float,
                           panel_offset_x: float, panel_offset_y: float):
        """Apply pattern fill using PatternRenderer.
        
        Args:
            canvas: ReportLab canvas
            fill_style: PatternFill configuration
            x: Shape X in inches
            y: Shape Y in inches
            width: Shape width in inches
            height: Shape height in inches
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        # Lazy load to avoid circular imports
        if self._pattern_renderer is None:
            from holiday_card.renderers.pattern_renderer import PatternRenderer
            self._pattern_renderer = PatternRenderer()

        # Convert dimensions from inches to points
        x_pts = (x + panel_offset_x) * self.POINTS_PER_INCH
        y_pts = (y + panel_offset_y) * self.POINTS_PER_INCH
        width_pts = width * self.POINTS_PER_INCH
        height_pts = height * self.POINTS_PER_INCH

        # Render the pattern
        self._pattern_renderer.render_pattern_fill(
            canvas, fill_style, x_pts, y_pts, width_pts, height_pts
        )

    def _apply_fill(self, canvas, shape, x: float, y: float, width: float, height: float,
                    panel_offset_x: float, panel_offset_y: float) -> bool:
        """Apply fill (solid, gradient, or pattern) to a shape.
        
        Args:
            canvas: ReportLab canvas
            shape: Shape with fill/fill_color attributes
            x: Shape X in inches
            y: Shape Y in inches  
            width: Shape width in inches
            height: Shape height in inches
            panel_offset_x: Panel offset X in inches
            panel_offset_y: Panel offset Y in inches
            
        Returns:
            True if fill should be drawn, False otherwise
        """
        fill_style = self._get_fill_style(shape)

        if isinstance(fill_style, (LinearGradientFill, RadialGradientFill)):
            # Use gradient renderer
            self._apply_gradient_fill(canvas, fill_style, x, y, width, height,
                                     panel_offset_x, panel_offset_y)
            return False  # Gradient already drawn
        elif isinstance(fill_style, PatternFill):
            # Use pattern renderer (T091)
            self._apply_pattern_fill(canvas, fill_style, x, y, width, height,
                                    panel_offset_x, panel_offset_y)
            return False  # Pattern already drawn
        elif isinstance(fill_style, SolidFill):
            canvas.setFillColor(self._hex_to_color(fill_style.color))
            return True
        elif hasattr(shape, 'fill_color') and shape.fill_color:
            canvas.setFillColor(self._hex_to_color(shape.fill_color))
            return True
        return False

    def render_rectangle(
        self,
        canvas: Canvas,
        rect: Rectangle,
        panel_offset_x: float,
        panel_offset_y: float
    ) -> None:
        """Render rectangle shape.

        Args:
            canvas: ReportLab canvas
            rect: Rectangle shape
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        # Convert to points
        x = (panel_offset_x + rect.x) * self.POINTS_PER_INCH
        y = (panel_offset_y + rect.y) * self.POINTS_PER_INCH
        width = rect.width * self.POINTS_PER_INCH
        height = rect.height * self.POINTS_PER_INCH

        # Apply opacity
        self._apply_opacity(canvas, rect.opacity)

        # Apply rotation
        center_x = x + width / 2
        center_y = y + height / 2
        self._apply_rotation(canvas, rect.rotation, center_x, center_y)

        # Apply fill (solid or gradient)
        has_fill = self._apply_fill(canvas, rect, rect.x, rect.y, rect.width, rect.height,
                                      panel_offset_x, panel_offset_y)
        has_stroke = rect.stroke_color is not None and rect.stroke_width > 0

        if has_stroke:
            canvas.setStrokeColor(self._hex_to_color(rect.stroke_color))
            canvas.setLineWidth(rect.stroke_width)

        # Draw rectangle
        canvas.rect(x, y, width, height, stroke=int(has_stroke), fill=int(has_fill))

        # Restore rotation and opacity
        self._restore_rotation(canvas, rect.rotation)
        self._reset_opacity(canvas)

    def render_circle(
        self,
        canvas: Canvas,
        circle: Circle,
        panel_offset_x: float,
        panel_offset_y: float
    ) -> None:
        """Render circle shape.

        Args:
            canvas: ReportLab canvas
            circle: Circle shape
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        # Convert to points
        center_x = (panel_offset_x + circle.center_x) * self.POINTS_PER_INCH
        center_y = (panel_offset_y + circle.center_y) * self.POINTS_PER_INCH
        radius = circle.radius * self.POINTS_PER_INCH

        # Apply opacity
        self._apply_opacity(canvas, circle.opacity)

        # Apply rotation (no visual effect for circle, but for consistency)
        self._apply_rotation(canvas, circle.rotation, center_x, center_y)

        # Calculate bounding box for gradient support
        x = circle.center_x - circle.radius
        y = circle.center_y - circle.radius
        diameter = circle.radius * 2

        # Apply fill (solid or gradient)
        has_fill = self._apply_fill(canvas, circle, x, y, diameter, diameter,
                                      panel_offset_x, panel_offset_y)
        has_stroke = circle.stroke_color is not None and circle.stroke_width > 0

        if has_stroke:
            canvas.setStrokeColor(self._hex_to_color(circle.stroke_color))
            canvas.setLineWidth(circle.stroke_width)

        # Draw circle
        canvas.circle(center_x, center_y, radius, stroke=int(has_stroke), fill=int(has_fill))

        # Restore rotation and opacity
        self._restore_rotation(canvas, circle.rotation)
        self._reset_opacity(canvas)

    def render_triangle(
        self,
        canvas: Canvas,
        triangle: Triangle,
        panel_offset_x: float,
        panel_offset_y: float
    ) -> None:
        """Render triangle shape using polygon path.

        Args:
            canvas: ReportLab canvas
            triangle: Triangle shape
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        # Convert vertices to points
        x1 = (panel_offset_x + triangle.x1) * self.POINTS_PER_INCH
        y1 = (panel_offset_y + triangle.y1) * self.POINTS_PER_INCH
        x2 = (panel_offset_x + triangle.x2) * self.POINTS_PER_INCH
        y2 = (panel_offset_y + triangle.y2) * self.POINTS_PER_INCH
        x3 = (panel_offset_x + triangle.x3) * self.POINTS_PER_INCH
        y3 = (panel_offset_y + triangle.y3) * self.POINTS_PER_INCH

        # Calculate geometric center for rotation
        center_x = (x1 + x2 + x3) / 3
        center_y = (y1 + y2 + y3) / 3

        # Apply opacity
        self._apply_opacity(canvas, triangle.opacity)

        # Apply rotation
        self._apply_rotation(canvas, triangle.rotation, center_x, center_y)

        # Calculate bounding box for gradient support
        min_x = min(triangle.x1, triangle.x2, triangle.x3)
        min_y = min(triangle.y1, triangle.y2, triangle.y3)
        max_x = max(triangle.x1, triangle.x2, triangle.x3)
        max_y = max(triangle.y1, triangle.y2, triangle.y3)
        bbox_width = max_x - min_x
        bbox_height = max_y - min_y

        # Apply fill (solid or gradient)
        has_fill = self._apply_fill(canvas, triangle, min_x, min_y, bbox_width, bbox_height,
                                      panel_offset_x, panel_offset_y)
        has_stroke = triangle.stroke_color is not None and triangle.stroke_width > 0

        if has_stroke:
            canvas.setStrokeColor(self._hex_to_color(triangle.stroke_color))
            canvas.setLineWidth(triangle.stroke_width)

        # Create polygon path
        path = canvas.beginPath()
        path.moveTo(x1, y1)
        path.lineTo(x2, y2)
        path.lineTo(x3, y3)
        path.close()

        # Draw path
        canvas.drawPath(path, stroke=int(has_stroke), fill=int(has_fill))

        # Restore rotation and opacity
        self._restore_rotation(canvas, triangle.rotation)
        self._reset_opacity(canvas)

    def render_star(
        self,
        canvas: Canvas,
        star: Star,
        panel_offset_x: float,
        panel_offset_y: float
    ) -> None:
        """Render star shape using polygon path.

        Calculates star points alternating between outer and inner radius.

        Args:
            canvas: ReportLab canvas
            star: Star shape
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        # Convert to points
        center_x = (panel_offset_x + star.center_x) * self.POINTS_PER_INCH
        center_y = (panel_offset_y + star.center_y) * self.POINTS_PER_INCH
        outer_radius = star.outer_radius * self.POINTS_PER_INCH
        inner_radius = star.inner_radius * self.POINTS_PER_INCH

        # Apply opacity
        self._apply_opacity(canvas, star.opacity)

        # Apply rotation
        self._apply_rotation(canvas, star.rotation, center_x, center_y)

        # Calculate star points
        points = self._calculate_star_points(
            center_x, center_y, outer_radius, inner_radius, star.points
        )

        # Calculate bounding box for gradient support
        x = star.center_x - star.outer_radius
        y = star.center_y - star.outer_radius
        diameter = star.outer_radius * 2

        # Apply fill (solid or gradient)
        has_fill = self._apply_fill(canvas, star, x, y, diameter, diameter,
                                      panel_offset_x, panel_offset_y)
        has_stroke = star.stroke_color is not None and star.stroke_width > 0

        if has_stroke:
            canvas.setStrokeColor(self._hex_to_color(star.stroke_color))
            canvas.setLineWidth(star.stroke_width)

        # Create polygon path
        path = canvas.beginPath()
        path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, y)
        path.close()

        # Draw path
        canvas.drawPath(path, stroke=int(has_stroke), fill=int(has_fill))

        # Restore rotation and opacity
        self._restore_rotation(canvas, star.rotation)
        self._reset_opacity(canvas)

    def render_line(
        self,
        canvas: Canvas,
        line: Line,
        panel_offset_x: float,
        panel_offset_y: float
    ) -> None:
        """Render line shape.

        Args:
            canvas: ReportLab canvas
            line: Line shape
            panel_offset_x: Panel X offset in inches
            panel_offset_y: Panel Y offset in inches
        """
        # Convert to points
        start_x = (panel_offset_x + line.start_x) * self.POINTS_PER_INCH
        start_y = (panel_offset_y + line.start_y) * self.POINTS_PER_INCH
        end_x = (panel_offset_x + line.end_x) * self.POINTS_PER_INCH
        end_y = (panel_offset_y + line.end_y) * self.POINTS_PER_INCH

        # Calculate midpoint for rotation
        mid_x = (start_x + end_x) / 2
        mid_y = (start_y + end_y) / 2

        # Apply opacity
        self._apply_opacity(canvas, line.opacity)

        # Apply rotation
        self._apply_rotation(canvas, line.rotation, mid_x, mid_y)

        # Apply stroke (lines don't have fill)
        stroke_color = line.stroke_color or "#000000"  # Default to black
        canvas.setStrokeColor(self._hex_to_color(stroke_color))
        canvas.setLineWidth(line.stroke_width if line.stroke_width > 0 else 1)

        # Draw line
        canvas.line(start_x, start_y, end_x, end_y)

        # Restore rotation and opacity
        self._restore_rotation(canvas, line.rotation)
        self._reset_opacity(canvas)

    def _hex_to_color(self, hex_string: str) -> HexColor:
        """Convert hex color string to ReportLab Color.

        Args:
            hex_string: Hex color (#RRGGBB or RRGGBB)

        Returns:
            ReportLab HexColor object
        """
        if not hex_string.startswith("#"):
            hex_string = f"#{hex_string}"
        return HexColor(hex_string)

    def _calculate_star_points(
        self,
        center_x: float,
        center_y: float,
        outer_radius: float,
        inner_radius: float,
        num_points: int
    ) -> list[tuple[float, float]]:
        """Calculate star polygon vertices.

        Alternates between outer and inner radius points.
        First point starts at top (270 degrees).

        Args:
            center_x: Center X in points
            center_y: Center Y in points
            outer_radius: Outer point radius in points
            inner_radius: Inner point radius in points
            num_points: Number of star points

        Returns:
            List of (x, y) coordinates in points
        """
        points = []
        angle_step = 360.0 / (num_points * 2)  # Alternating outer/inner

        for i in range(num_points * 2):
            # Calculate angle (start at top, rotate clockwise)
            angle = math.radians(i * angle_step - 90)

            # Alternate between outer and inner radius
            radius = outer_radius if i % 2 == 0 else inner_radius

            # Calculate point coordinates
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)

            points.append((x, y))

        return points


    def _apply_opacity(self, canvas: Canvas, opacity: float) -> None:
        """Apply opacity to fill and stroke.

        Args:
            canvas: ReportLab canvas
            opacity: Opacity value 0.0-1.0
        """
        if opacity < 1.0:
            canvas.setFillAlpha(opacity)
            canvas.setStrokeAlpha(opacity)

    def _reset_opacity(self, canvas: Canvas) -> None:
        """Reset opacity to fully opaque.

        Args:
            canvas: ReportLab canvas
        """
        canvas.setFillAlpha(1.0)
        canvas.setStrokeAlpha(1.0)

    def _apply_rotation(
        self,
        canvas: Canvas,
        rotation: float,
        center_x: float,
        center_y: float
    ) -> None:
        """Apply rotation around center point.

        Args:
            canvas: ReportLab canvas
            rotation: Rotation in degrees
            center_x: Rotation center X in points
            center_y: Rotation center Y in points
        """
        if rotation != 0.0:
            canvas.saveState()
            canvas.translate(center_x, center_y)
            canvas.rotate(rotation)
            canvas.translate(-center_x, -center_y)

    def _restore_rotation(self, canvas: Canvas, rotation: float) -> None:
        """Restore canvas state after rotation.

        Args:
            canvas: ReportLab canvas
            rotation: Rotation value to check if restore needed
        """
        if rotation != 0.0:
            canvas.restoreState()

    def _inches_to_points(self, inches: float) -> float:
        """Convert inches to PDF points.

        Args:
            inches: Measurement in inches

        Returns:
            Measurement in points (72 pts/inch)
        """
        return inches * self.POINTS_PER_INCH
