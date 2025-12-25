"""Shape rendering logic for vector graphics.

This module provides rendering methods for all shape types using ReportLab
drawing primitives. Handles conversion from inches to points, color parsing,
and geometric calculations for complex shapes like stars.
"""

import math
from typing import Union

from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas

from holiday_card.core.models import Circle, Line, Rectangle, Star, Triangle


class ShapeRenderer:
    """Renders vector graphics shapes to ReportLab canvas.

    Converts shape models to ReportLab drawing commands, handling:
    - Measurement conversion (inches to points)
    - Color conversion (hex strings to ReportLab Color objects)
    - Geometric calculations (star points, rotation centers)
    - Fill and stroke styling
    """

    POINTS_PER_INCH = 72  # ReportLab uses points (72 pts/inch)

    def render_shape(
        self,
        canvas: Canvas,
        shape: Union[Rectangle, Circle, Triangle, Star, Line],
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

        # Apply colors
        has_fill = rect.fill_color is not None
        has_stroke = rect.stroke_color is not None and rect.stroke_width > 0

        if has_fill:
            canvas.setFillColor(self._hex_to_color(rect.fill_color))
        if has_stroke:
            canvas.setStrokeColor(self._hex_to_color(rect.stroke_color))
            canvas.setLineWidth(rect.stroke_width)

        # Draw rectangle
        canvas.rect(x, y, width, height, stroke=int(has_stroke), fill=int(has_fill))

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

        # Apply colors
        has_fill = circle.fill_color is not None
        has_stroke = circle.stroke_color is not None and circle.stroke_width > 0

        if has_fill:
            canvas.setFillColor(self._hex_to_color(circle.fill_color))
        if has_stroke:
            canvas.setStrokeColor(self._hex_to_color(circle.stroke_color))
            canvas.setLineWidth(circle.stroke_width)

        # Draw circle
        canvas.circle(center_x, center_y, radius, stroke=int(has_stroke), fill=int(has_fill))

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

        # Apply colors
        has_fill = triangle.fill_color is not None
        has_stroke = triangle.stroke_color is not None and triangle.stroke_width > 0

        if has_fill:
            canvas.setFillColor(self._hex_to_color(triangle.fill_color))
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

        # Calculate star points
        points = self._calculate_star_points(
            center_x, center_y, outer_radius, inner_radius, star.points
        )

        # Apply colors
        has_fill = star.fill_color is not None
        has_stroke = star.stroke_color is not None and star.stroke_width > 0

        if has_fill:
            canvas.setFillColor(self._hex_to_color(star.fill_color))
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

        # Apply stroke (lines don't have fill)
        stroke_color = line.stroke_color or "#000000"  # Default to black
        canvas.setStrokeColor(self._hex_to_color(stroke_color))
        canvas.setLineWidth(line.stroke_width if line.stroke_width > 0 else 1)

        # Draw line
        canvas.line(start_x, start_y, end_x, end_y)

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

    def _inches_to_points(self, inches: float) -> float:
        """Convert inches to PDF points.

        Args:
            inches: Measurement in inches

        Returns:
            Measurement in points (72 pts/inch)
        """
        return inches * self.POINTS_PER_INCH
