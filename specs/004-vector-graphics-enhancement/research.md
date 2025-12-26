# Technical Research: Vector Graphics Enhancement

**Feature**: 004-vector-graphics-enhancement
**Date**: 2025-12-25

## Overview

This document consolidates technical research findings for implementing SVG path import, gradient fills, image clipping masks, and pattern fills using ReportLab 4.0+ and Pillow 10.0+.

## Research Areas

### 1. SVG Path Rendering with ReportLab

**Decision**: Use ReportLab's `canvas.beginPath()` / `canvas.drawPath()` API with path object construction

**Rationale**:
- ReportLab provides native support for vector paths via `reportlab.graphics.shapes.Path`
- Path objects accept SVG-style commands through `moveTo()`, `lineTo()`, `curveTo()`, etc.
- No need to reinvent Bezier curve math - ReportLab handles rendering
- Maintains print accuracy (vector-based, resolution-independent)

**Implementation Approach**:
```python
from reportlab.pdfgen.canvas import Canvas
from reportlab.graphics.shapes import Path

# Parse SVG path data "M 10 10 L 20 20 C 30 30 40 40 50 50"
# Convert to ReportLab Path commands
path = Path()
path.moveTo(10, 10)
path.lineTo(20, 20)
path.curveTo(30, 30, 40, 40, 50, 50)

canvas.drawPath(path, fill=1, stroke=1)
```

**Supported SVG Commands**:
- **M/m** (moveTo): `path.moveTo(x, y)` - absolute/relative positioning
- **L/l** (lineTo): `path.lineTo(x, y)` - straight line
- **H/h** (horizontal line): Convert to `lineTo(x, current_y)`
- **V/v** (vertical line): Convert to `lineTo(current_x, y)`
- **C/c** (cubic Bezier): `path.curveTo(x1, y1, x2, y2, x, y)` - control points + end
- **S/s** (smooth cubic): Reflect previous control point + new control point
- **Q/q** (quadratic Bezier): `path.quadTo(x1, y1, x, y)` or convert to cubic
- **T/t** (smooth quadratic): Reflect previous control point
- **A/a** (arc): `path.arcTo(x1, y1, x2, y2, startAng, extent)` or convert to Bezier approximation
- **Z/z** (closePath): `path.closePath()`

**Unsupported Commands** (FR-006 graceful degradation):
- Log warning and skip if encountered
- Examples: embedded text, filters, masks (SVG-specific features)

**Alternatives Considered**:
- **svglib + ReportLab**: Full SVG file parsing - rejected due to over-engineering (metadata, transforms, groups not needed)
- **Cairo/Skia bindings**: Heavyweight dependencies, violates Simplicity principle
- **Custom Bezier renderer**: Reinventing wheel, error-prone math

**References**:
- ReportLab User Guide Chapter 8 (Graphics and Drawing)
- SVG Path specification: https://www.w3.org/TR/SVG/paths.html
- ReportLab graphics.shapes.Path source code

---

### 2. Gradient Fills (Linear and Radial)

**Decision**: Use ReportLab's `linearGradient` and `radialGradient` drawing operators via PDFCanvas

**Rationale**:
- ReportLab exposes PDF's native gradient capabilities
- Hardware-accelerated rendering in PDF viewers
- Smooth color transitions at any zoom level (vector-based)
- No additional dependencies required

**Implementation Approach - Linear Gradients**:
```python
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import Color

# Define gradient with angle and color stops
canvas.saveState()
canvas.linearGradient(
    x1, y1, x2, y2,  # Start and end points (calculated from angle)
    colors=[Color(1,0,0), Color(0,0,1)],  # Red to blue
    positions=[0.0, 1.0]  # Color stop positions
)
# Draw shape with gradient fill
canvas.rect(x, y, width, height, fill=1)
canvas.restoreState()
```

**Implementation Approach - Radial Gradients**:
```python
# Define radial gradient with center and radius
canvas.saveState()
canvas.radialGradient(
    cx, cy, radius,  # Center and outer radius
    colors=[Color(1,1,1), Color(0,0,0)],  # White to black
    positions=[0.0, 1.0]
)
canvas.circle(cx, cy, radius, fill=1)
canvas.restoreState()
```

**Angle-to-Coordinates Conversion** (Linear Gradients):
```python
import math

def gradient_endpoints(x, y, width, height, angle_degrees):
    """Calculate gradient start/end points from angle."""
    angle_rad = math.radians(angle_degrees)
    # 0° = left-to-right, 90° = bottom-to-top
    x1 = x
    y1 = y
    x2 = x + width * math.cos(angle_rad)
    y2 = y + height * math.sin(angle_rad)
    return (x1, y1, x2, y2)
```

**Color Stop Validation**:
- Positions MUST be in range 0.0 to 1.0 (Pydantic validator)
- Positions MUST be in ascending order
- Minimum 2 color stops required
- Maximum 20 color stops (reasonable limit)

**Alternatives Considered**:
- **PIL gradient images**: Bitmap approach, violates print quality
- **Custom color interpolation**: Unnecessary, PDF native support exists
- **CSS-style gradient syntax**: Over-engineering for YAML use case

**References**:
- ReportLab PDFCanvas gradient methods
- PDF Reference 1.7, Section 4.6 (Shading Patterns)

---

### 3. Image Clipping Masks

**Decision**: Use ReportLab's `canvas.clipPath()` combined with Pillow for image preprocessing

**Rationale**:
- ReportLab supports vector clipping paths via PDF clipping operators
- Pillow handles image loading and format conversion
- No need for external image editing tools
- Maintains print quality (vector mask boundary)

**Implementation Approach**:
```python
from reportlab.pdfgen.canvas import Canvas
from reportlab.graphics.shapes import Path

# 1. Create clipping mask path (e.g., circle)
clip_path = Path()
clip_path.circle(center_x, center_y, radius)

# 2. Apply clipping region
canvas.saveState()
canvas.clipPath(clip_path, stroke=0, fill=0)

# 3. Draw image (only visible within clipped region)
canvas.drawImage(image_path, x, y, width, height)

# 4. Restore state (remove clipping)
canvas.restoreState()
```

**Supported Mask Shapes**:
- **Circle**: `Path.circle(cx, cy, radius)`
- **Rectangle**: `Path.rect(x, y, width, height)`
- **Ellipse**: `Path.ellipse(x, y, width, height)`
- **Star**: Composed of line segments (reuse Star shape logic)
- **SVG Path**: Any arbitrary path defined via SVG path data

**Image Positioning**:
- Image maintains aspect ratio by default
- User specifies target width/height in YAML
- Clipping mask applied after scaling

**Alternatives Considered**:
- **Pillow Image.putalpha()**: Bitmap masking, increases file size, reduces quality
- **PIL ImageDraw mask**: Rasterizes mask, violates vector principle
- **External tools (ImageMagick)**: Violates offline operation and Simplicity

**References**:
- ReportLab User Guide Section on Clipping
- PDF Reference 1.7, Section 4.4.3 (Clipping Path Operators)
- Pillow documentation on image formats

---

### 4. Pattern Fills

**Decision**: Implement pattern fills using ReportLab's tiling pattern functionality with simple geometric repeats

**Rationale**:
- PDF natively supports tiling patterns (Type 1 patterns)
- Simple repeating shapes (stripes, dots) don't require complex algorithms
- Maintains vector quality and small file size
- ReportLab provides `canvas.beginForm()` / `endForm()` for pattern definition

**Implementation Approach - Stripe Pattern**:
```python
from reportlab.pdfgen.canvas import Canvas

# 1. Define pattern tile as a Form XObject
pattern_id = "stripe_pattern"
canvas.beginForm(pattern_id)
# Draw stripe within tile bounds
canvas.setStrokeColor(color)
canvas.line(0, 0, tile_width, tile_height)
canvas.endForm()

# 2. Apply pattern as fill
canvas.setFillPattern(pattern_id, tile_width, tile_height)
canvas.rect(x, y, width, height, fill=1, stroke=0)
```

**Implementation Approach - Dot Pattern**:
```python
# Define polka dot tile
canvas.beginForm("dot_pattern")
canvas.circle(tile_width/2, tile_height/2, dot_radius, fill=1)
canvas.endForm()

canvas.setFillPattern("dot_pattern", tile_width, tile_height)
canvas.rect(x, y, width, height, fill=1)
```

**Supported Pattern Types**:
- **Stripes**: Parallel lines at specified angle and spacing
- **Dots/Polka**: Circular dots in grid layout
- **Grid**: Perpendicular lines forming squares
- **Checkerboard**: Alternating filled/empty squares

**Pattern Parameters**:
- `pattern_type`: Enum (stripes, dots, grid, checkerboard)
- `scale`: Float (1.0 = default size, 2.0 = double size)
- `rotation`: Degrees (0-360)
- `colors`: List of colors (primary, secondary for alternating patterns)

**Edge Cases**:
- Very small shapes (<0.5"): Scale pattern down or fallback to solid fill
- Pattern colors identical: Render as solid fill
- Invalid scale (<=0): Use default scale 1.0

**Alternatives Considered**:
- **Bitmap pattern images**: Violates vector quality, file size bloat
- **Complex pattern library (arabesque, floral)**: Over-engineering, use SVG paths instead
- **CSS-style pattern syntax**: Not applicable to PDF rendering

**References**:
- ReportLab Forms and Patterns documentation
- PDF Reference 1.7, Section 4.6.2 (Tiling Patterns)

---

### 5. YAML Schema Extensions

**Decision**: Extend existing YAML template schema with new element types using Pydantic discriminated unions

**Rationale**:
- Pydantic 2.0+ supports discriminated unions via `type` field
- Maintains type safety and validation
- Backwards compatible (existing templates don't use new types)
- Clear error messages for invalid configurations

**Schema Extension - SVG Path**:
```yaml
shapes:
  - type: svg_path
    path_data: "M 10 10 L 20 20 C 30 30 40 40 50 50 Z"
    fill_color: "#FF0000"
    stroke_color: "#000000"
    stroke_width: 2.0
    scale: 1.0  # Applied to path coordinates
    rotation: 45.0
    opacity: 1.0
```

**Schema Extension - Gradient Fill**:
```yaml
shapes:
  - type: rectangle
    x: 0.0
    y: 0.0
    width: 4.0
    height: 6.0
    fill:
      type: linear_gradient
      angle: 45  # Degrees
      stops:
        - position: 0.0
          color: "#FF0000"
        - position: 1.0
          color: "#0000FF"
```

**Schema Extension - Clipping Mask**:
```yaml
images:
  - source_path: "family_photo.jpg"
    x: 1.0
    y: 1.0
    width: 3.0
    height: 3.0
    clip_mask:
      type: circle
      center_x: 2.5
      center_y: 2.5
      radius: 1.5
```

**Schema Extension - Pattern Fill**:
```yaml
shapes:
  - type: rectangle
    x: 0.0
    y: 0.0
    width: 4.0
    height: 6.0
    fill:
      type: pattern
      pattern_type: stripes
      angle: 45
      spacing: 0.25  # Inches between stripes
      colors:
        - "#FF0000"
        - "#FFFFFF"
      scale: 1.0
```

**Validation Rules**:
- SVG path data: Non-empty string, basic command syntax check
- Gradient stops: 2-20 stops, positions 0.0-1.0 ascending
- Clipping mask: Valid shape reference or SVG path
- Pattern type: Enum validation (stripes, dots, grid, checkerboard)

**Backwards Compatibility**:
- Existing templates use `fill_color: "#RRGGBB"` (string)
- New templates use `fill: {type: gradient|pattern, ...}` (object)
- Parser checks type: if string, treat as solid color; if object, dispatch to gradient/pattern

---

## Performance Considerations

**SVG Path Complexity**:
- Limit to 1000 path commands per element
- Complex paths (>100 commands) log performance warning
- Very complex paths (>500 commands) suggest simplification

**Gradient Rendering**:
- ReportLab gradients are GPU-accelerated in PDF viewers
- No performance penalty vs. solid colors at render time
- File size increase: ~100 bytes per gradient definition

**Clipping Mask Performance**:
- Clipping adds minimal overhead (PDF native operation)
- Image file size dominates (use JPEG compression for photos)
- Multiple clipped images: reuse clip paths where possible

**Pattern Fill Performance**:
- Pattern definition cached (Form XObject)
- Tiling handled by PDF renderer, not application
- File size: ~50-200 bytes per pattern + tile contents

**Overall Performance Target**:
- Card generation with new features: <20% slower than basic templates
- Mitigation: Lazy loading of SVG paths, gradient caching

---

## Best Practices

### SVG Path Usage
- Keep paths simple (prefer <50 commands per path)
- Use absolute coordinates (M, L, C) for clarity
- Close paths with Z command for filled shapes
- Test rendering at print resolution (300 DPI preview)

### Gradient Design
- Use 2-4 color stops for smooth transitions
- Avoid extreme angles (prefer 0°, 45°, 90°, 180°, 270°)
- Test color contrast at print (screen vs. paper color shifts)
- Consider color laser printer gamut limitations

### Clipping Mask Design
- Ensure mask fully contains image region of interest
- Use simple shapes (circle, rectangle) for best performance
- Avoid very small masks (<0.5" diameter) - details lost in print
- Maintain 0.25" safe margin from page edges

### Pattern Fill Design
- Test patterns at actual print size (not screen preview)
- Use contrasting colors (avoid low-contrast patterns)
- Scale patterns appropriately (stripes 0.1"-0.5" wide)
- Avoid very fine patterns (<0.05" spacing) - printer resolution limits

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SVG command parsing errors | Medium | High | Comprehensive test suite with edge cases; graceful degradation (FR-006) |
| Gradient color banding in print | Low | Medium | Use sufficient color stops (recommend 3-4); test with actual printer |
| Clipping mask performance on large images | Low | Low | Document image size limits (recommend <5MB); use JPEG compression |
| Pattern fills not visible at small scales | Medium | Low | Auto-scale detection; fallback to solid fill with warning |
| ReportLab version incompatibilities | Low | High | Pin ReportLab >=4.0 in requirements; test with 4.0, 4.1, 4.2 |

---

## Open Questions

**Q1**: Should we support SVG transform attributes (scale, rotate, translate) or require pre-transformed path data?
**A1**: Require pre-transformed path data in YAML. Simplifies implementation and keeps YAML schema flat. Users can transform paths using external tools before copying to YAML.

**Q2**: How to handle gradient fills on shapes with stroke borders?
**A2**: Apply gradient to fill only, stroke remains solid color. Matches SVG/CSS behavior and user expectations.

**Q3**: Should pattern fills support custom tile images (e.g., user-provided PNG)?
**A3**: No. Limit to built-in geometric patterns (stripes, dots, grid, checkerboard). Custom images would violate Simplicity principle and introduce file size issues. Users can achieve similar effects with repeated SVG shapes.

**Q4**: How to handle overlapping clipped images with different masks?
**A4**: Each image has independent clipping context (saveState/restoreState). No interference between clipped images.

**Q5**: Should we validate SVG path data syntax at template load time or render time?
**A5**: Validate at template load time (Pydantic validator). Fail fast with clear error message. Prevents surprise render failures.

---

## Conclusion

All technical approaches leverage ReportLab's native PDF capabilities, maintaining the Simplicity principle while achieving the 70% template coverage goal. No external dependencies beyond existing ReportLab and Pillow. Implementation follows established patterns in the codebase (BaseShape model extension, ShapeRenderer coordination).

**Next Steps**: Proceed to Phase 1 (data-model.md and contracts/)
