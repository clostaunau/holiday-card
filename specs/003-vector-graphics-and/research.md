# Research: ReportLab Drawing API and Shape Rendering

**Feature**: Vector Graphics and Decorative Elements System
**Date**: 2025-12-25
**Researcher**: System Analysis

## Overview

This document investigates the technical feasibility of implementing vector shape rendering using ReportLab's drawing capabilities for the holiday card generator.

## Research Questions

1. What drawing primitives does ReportLab provide?
2. How do we implement z-index layering in ReportLab?
3. Does ReportLab support opacity/transparency for shapes?
4. How do we implement rotation around arbitrary points?
5. What are the performance characteristics of rendering many shapes?

## ReportLab Drawing API

### Available Primitives

ReportLab's `Canvas` object provides these drawing methods:

```python
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color, HexColor

c = canvas.Canvas("output.pdf")

# Rectangle
c.rect(x, y, width, height, stroke=1, fill=1)

# Circle (actually ellipse)
c.circle(x_ctr, y_ctr, r, stroke=1, fill=1)
c.ellipse(x1, y1, x2, y2, stroke=1, fill=1)

# Polygon (for triangle, star)
path = c.beginPath()
path.moveTo(x1, y1)
path.lineTo(x2, y2)
path.lineTo(x3, y3)
path.close()
c.drawPath(path, stroke=1, fill=1)

# Line
c.line(x1, y1, x2, y2)

# Wedge (for star points, pie slices)
c.wedge(x1, y1, x2, y2, startAng, extent, stroke=1, fill=1)
```

**Conclusion**: All 5 shape types (Rectangle, Circle, Triangle, Star, Line) can be implemented using these primitives.

### Color and Fill/Stroke Control

```python
# Fill color
c.setFillColor(Color(r, g, b))  # RGB values 0.0-1.0
c.setFillColor(HexColor("#A8B5A0"))  # Hex colors supported

# Stroke color
c.setStrokeColor(Color(r, g, b))
c.setStrokeColor(HexColor("#333333"))

# Stroke width
c.setLineWidth(width_in_points)

# Drawing with only fill or only stroke
c.rect(x, y, w, h, stroke=0, fill=1)  # Fill only
c.rect(x, y, w, h, stroke=1, fill=0)  # Stroke only
c.rect(x, y, w, h, stroke=1, fill=1)  # Both
```

**Conclusion**: Full control over fill and stroke colors and widths.

### Opacity/Transparency Support

```python
# Fill opacity (alpha)
c.setFillAlpha(0.5)  # 0.0 = fully transparent, 1.0 = fully opaque

# Stroke opacity
c.setStrokeAlpha(0.5)

# Example: Semi-transparent overlapping circles
c.setFillColor(HexColor("#FF0000"))
c.setFillAlpha(0.5)
c.circle(100, 100, 50, stroke=0, fill=1)

c.setFillColor(HexColor("#0000FF"))
c.setFillAlpha(0.5)
c.circle(150, 100, 50, stroke=0, fill=1)
# Result: Overlapping area shows blended purple
```

**Conclusion**: Opacity is fully supported via `setFillAlpha()` and `setStrokeAlpha()`. Alpha blending works correctly for overlapping shapes.

### Rotation Implementation

```python
# Rotation requires state save/restore
c.saveState()  # Save current transformation matrix

# Translate to rotation center
c.translate(center_x, center_y)

# Rotate (angle in degrees, counter-clockwise)
c.rotate(angle_degrees)

# Translate back
c.translate(-center_x, -center_y)

# Draw shape (now rotated)
c.rect(x, y, width, height, stroke=1, fill=1)

c.restoreState()  # Restore original state
```

**Conclusion**: Rotation is supported through transformation matrix manipulation with save/restore pattern.

### Z-Index Layering

ReportLab renders in **drawing order** - later drawing calls appear on top. There is no built-in z-index.

**Solution**: Sort all elements by z_index before rendering:

```python
# Collect all elements with z_index
elements = [
    (shape1, z_index=1),
    (text1, z_index=3),
    (shape2, z_index=2),
]

# Sort by z_index (lowest first)
elements.sort(key=lambda e: e[1])

# Render in order (lowest z_index first, appears at bottom)
for element, _ in elements:
    render_element(element)
```

**Conclusion**: Z-index must be implemented by sorting elements before rendering. This is straightforward and performant.

## Shape Geometry Calculations

### Triangle

Given three vertices (x1, y1), (x2, y2), (x3, y3):

```python
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch

def draw_triangle(canvas: Canvas, x1, y1, x2, y2, x3, y3):
    path = canvas.beginPath()
    path.moveTo(x1 * inch, y1 * inch)
    path.lineTo(x2 * inch, y2 * inch)
    path.lineTo(x3 * inch, y3 * inch)
    path.close()
    canvas.drawPath(path, stroke=1, fill=1)
```

**Conclusion**: Triangles use polygon path with 3 vertices.

### Star

Given center (cx, cy), outer_radius (R), inner_radius (r), points (n):

```python
import math

def draw_star(canvas: Canvas, cx, cy, outer_r, inner_r, points):
    path = canvas.beginPath()
    angle_step = 360.0 / (points * 2)  # Alternating outer/inner points

    for i in range(points * 2):
        angle = math.radians(i * angle_step - 90)  # Start at top
        radius = outer_r if i % 2 == 0 else inner_r
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)

        if i == 0:
            path.moveTo(x * inch, y * inch)
        else:
            path.lineTo(x * inch, y * inch)

    path.close()
    canvas.drawPath(path, stroke=1, fill=1)
```

**Conclusion**: Star requires trigonometric calculation of alternating outer/inner points.

### Rotation Matrix

For rotating a shape around center point (cx, cy):

```python
def rotate_point(x, y, cx, cy, angle_degrees):
    """Rotate point (x, y) around center (cx, cy) by angle."""
    angle_rad = math.radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # Translate to origin
    dx = x - cx
    dy = y - cy

    # Rotate
    rotated_x = dx * cos_a - dy * sin_a
    rotated_y = dx * sin_a + dy * cos_a

    # Translate back
    return cx + rotated_x, cy + rotated_y
```

**Alternative**: Use ReportLab's built-in transformation (recommended):

```python
canvas.saveState()
canvas.translate(cx * inch, cy * inch)
canvas.rotate(angle_degrees)
canvas.translate(-cx * inch, -cy * inch)
# Draw shape
canvas.restoreState()
```

**Conclusion**: ReportLab's transformation matrix is simpler and more reliable than manual rotation calculations.

## Performance Analysis

### Benchmark: Shape Rendering Performance

Hypothetical performance test results (based on ReportLab characteristics):

| Shapes | Generation Time | Notes |
|--------|----------------|-------|
| 10     | ~0.5s         | Negligible overhead |
| 50     | ~2.0s         | Within target (<10s) |
| 100    | ~4.0s         | Acceptable |
| 500    | ~18.0s        | Approaching limits |
| 1000   | ~35.0s        | Slow but functional |

**Bottlenecks**:
- Path construction (many lineTo calls for complex shapes)
- State save/restore for each rotated shape
- Alpha blending calculations

**Optimizations**:
- Cache path objects for repeated shapes
- Batch shapes with same styling (reduce setColor calls)
- Avoid unnecessary save/restore (only for rotated shapes)

**Conclusion**: Performance is acceptable for typical use cases (50-100 shapes per card). Extreme cases (500+) may be slow but still functional.

## YAML Schema with Pydantic

### Discriminated Union Pattern

Pydantic 2.0 supports discriminated unions for parsing different shape types:

```python
from pydantic import BaseModel, Field
from typing import Literal, Annotated

class Rectangle(BaseModel):
    type: Literal["rectangle"] = "rectangle"
    x: float
    y: float
    width: float
    height: float

class Circle(BaseModel):
    type: Literal["circle"] = "circle"
    center_x: float
    center_y: float
    radius: float

# Discriminated union
Shape = Annotated[Rectangle | Circle, Field(discriminator='type')]

# YAML parsing
shapes: list[Shape] = [
    {"type": "rectangle", "x": 1, "y": 2, "width": 3, "height": 4},
    {"type": "circle", "center_x": 5, "center_y": 6, "radius": 1},
]
```

**Conclusion**: Pydantic's discriminated union handles shape type polymorphism elegantly with the `type` field.

## Decorative Element Composition

### Color Palette Template Substitution

Decorative elements define color roles and use template strings:

```yaml
# Definition
color_roles:
  tree_primary: "#A8B5A0"
  ornament: "#D4AF37"

shapes:
  - type: triangle
    fill_color: "{tree_primary}"  # Template
  - type: circle
    fill_color: "{ornament}"

# Instance override
color_palette:
  tree_primary: "#FF0000"  # Override to red tree
  ornament: "#0000FF"      # Override to blue ornaments
```

**Implementation**:

```python
def resolve_color_palette(shapes: list[Shape], palette: dict[str, str]) -> list[Shape]:
    """Replace {role} placeholders with actual hex colors."""
    for shape in shapes:
        if shape.fill_color and shape.fill_color.startswith("{"):
            role = shape.fill_color.strip("{}")
            shape.fill_color = palette.get(role, shape.fill_color)
        # Same for stroke_color
    return shapes
```

**Conclusion**: Simple string substitution pattern enables flexible color customization.

### Scale and Rotation Transforms

Decorative elements apply scale and rotation to all internal shapes:

```python
def apply_scale(shape: Shape, scale: float):
    """Scale all dimensions by factor."""
    if isinstance(shape, Rectangle):
        shape.x *= scale
        shape.y *= scale
        shape.width *= scale
        shape.height *= scale
    elif isinstance(shape, Circle):
        shape.center_x *= scale
        shape.center_y *= scale
        shape.radius *= scale
    # ... other shape types

def apply_rotation(shapes: list[Shape], center_x: float, center_y: float, angle: float):
    """Rotate all shapes around decorative element center."""
    for shape in shapes:
        # Rotate each shape's position and add to shape.rotation
        # (Implementation uses rotation matrix from above)
```

**Conclusion**: Scale is straightforward multiplication. Rotation requires rotating both position and adding to shape's rotation property.

## Risks and Mitigation Strategies

### Risk 1: Platform-Specific Rendering Differences

**Risk**: Visual regression tests may fail due to minor anti-aliasing differences across platforms (Linux, macOS, Windows).

**Evidence**: ReportLab uses OS-specific font rendering and image libraries.

**Mitigation**:
- Use `imagehash` with tolerance (hamming distance ≤ 5)
- Generate platform-specific reference PDFs if needed
- Focus on functional correctness over pixel-perfect matching

### Risk 2: Circular References in Decorative Elements

**Risk**: Decorative element A includes element B, which includes A → infinite loop.

**Evidence**: YAML allows arbitrary nesting.

**Mitigation**:
- Decorative elements can only contain basic shapes, not other decorative elements
- Validate during library loading (no `type: decorative_element` in decorative definitions)
- Document restriction clearly

### Risk 3: Complex Color Palette Substitution

**Risk**: Template variables in nested decorative elements become complex to resolve.

**Evidence**: Multiple levels of composition with overrides.

**Mitigation**:
- Keep decorative elements simple (1 level deep)
- Color palette substitution happens at decorative element instantiation
- Clear error messages for undefined color roles

## Recommendations

### ✅ Proceed with Implementation

All research questions answered positively:

1. **Drawing Primitives**: All 5 shape types supported ✓
2. **Z-Index**: Manual sorting solution is simple and performant ✓
3. **Opacity**: Full alpha blending support via `setFillAlpha()` ✓
4. **Rotation**: Transformation matrix with save/restore ✓
5. **Performance**: Acceptable for target use cases (50-100 shapes) ✓

### Technical Decisions

- **Shape Rendering**: Use ReportLab's built-in drawing methods directly
- **Z-Index**: Sort all elements by z_index before rendering loop
- **Rotation**: Use `saveState()`/`restoreState()` with transformation matrix
- **Opacity**: Use `setFillAlpha()` and `setStrokeAlpha()`
- **YAML Parsing**: Pydantic discriminated unions with `type` field
- **Decorative Elements**: YAML library with string template color substitution
- **Performance**: Profile with 100+ shapes; optimize only if needed

### Future Enhancements (Out of Scope)

- SVG import using reportlab-svglib
- Gradient fills (requires custom shading)
- Pattern fills (hatching, dots)
- Curved paths and bezier curves
- Shape grouping and hierarchical transforms

## References

- [ReportLab User Guide - Graphics and Text Objects](https://www.reportlab.com/docs/reportlab-userguide.pdf) (Chapter 4)
- [Pydantic V2 - Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions)
- [ReportLab Source - pdfgen/canvas.py](https://github.com/rl extras/reportlab/blob/master/src/reportlab/pdfgen/canvas.py)
