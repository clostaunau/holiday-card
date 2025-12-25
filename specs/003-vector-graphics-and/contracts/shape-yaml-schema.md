# YAML Schema: Shape Elements

**Feature**: Vector Graphics and Decorative Elements System
**Date**: 2025-12-25
**Version**: 1.0

## Overview

This document defines the YAML schema for vector graphics shapes and decorative elements in holiday card templates. All examples are validated against Pydantic models defined in `src/holiday_card/core/models.py`.

## Shape Elements in Templates

###

 Panel with Shape Elements

Shapes are added to panels via the `shape_elements` list:

```yaml
panels:
  - position: front
    x: 0.0
    y: 5.5
    width: 8.5
    height: 5.5
    background_color: "#F5F5DC"

    shape_elements:
      - type: rectangle
        # ... rectangle properties
      - type: circle
        # ... circle properties
      - type: decorative_element
        # ... decorative element properties

    text_elements:
      # ... existing text elements

    image_elements:
      # ... existing image elements
```

## Basic Shape Types

### Rectangle

```yaml
type: rectangle          # Required: Discriminator
x: 1.0                   # Required: X position in inches (≥ 0.0)
y: 2.0                   # Required: Y position in inches (≥ 0.0)
width: 3.0               # Required: Width in inches (> 0.0)
height: 1.5              # Required: Height in inches (> 0.0)

# Optional styling (defaults shown)
fill_color: "#A8B5A0"    # Hex color or null for no fill
stroke_color: "#333333"  # Hex color or null for no stroke
stroke_width: 2          # Points (default: 0.0)
opacity: 0.8             # 0.0-1.0 (default: 1.0)
rotation: 15             # Degrees 0-360 (default: 0.0)
z_index: 1               # Integer (default: 0)
```

**Notes**:
- Position (x, y) is the bottom-left corner
- Rotation occurs around center: (x + width/2, y + height/2)
- At least one of `fill_color` or `stroke_color` should be set

### Circle

```yaml
type: circle             # Required: Discriminator
center_x: 4.0            # Required: Center X in inches (≥ 0.0)
center_y: 5.0            # Required: Center Y in inches (≥ 0.0)
radius: 0.5              # Required: Radius in inches (> 0.0)

# Optional styling
fill_color: "#B85C50"    # Hex color
stroke_color: null       # No stroke
opacity: 0.9
z_index: 2
```

**Notes**:
- Rotation has no visual effect on circles (but can be set for consistency)
- For ellipses, use future `ellipse` type (not yet implemented)

### Triangle

```yaml
type: triangle           # Required: Discriminator
x1: 2.0                  # Required: Vertex 1 X in inches (≥ 0.0)
y1: 3.0                  # Required: Vertex 1 Y in inches (≥ 0.0)
x2: 3.0                  # Required: Vertex 2 X in inches (≥ 0.0)
y2: 3.0                  # Required: Vertex 2 Y in inches (≥ 0.0)
x3: 2.5                  # Required: Vertex 3 X in inches (≥ 0.0)
y3: 4.0                  # Required: Vertex 3 Y in inches (≥ 0.0)

# Optional styling
fill_color: "#D4AF37"    # Gold
rotation: 10
z_index: 3
```

**Notes**:
- Vertices should not be collinear (validation warning if area ≈ 0)
- Rotation occurs around geometric center: ((x1+x2+x3)/3, (y1+y2+y3)/3)

### Star

```yaml
type: star               # Required: Discriminator
center_x: 4.25           # Required: Center X in inches (≥ 0.0)
center_y: 7.5            # Required: Center Y in inches (≥ 0.0)
outer_radius: 0.4        # Required: Outer point radius in inches (> 0.0)
inner_radius: 0.2        # Required: Inner point radius in inches (> 0.0)
points: 5                # Optional: Number of points (default: 5, range: 3-20)

# Optional styling
fill_color: "#FFD700"    # Bright gold
stroke_color: "#DAA520"  # Goldenrod outline
stroke_width: 1
z_index: 10
```

**Notes**:
- `inner_radius` must be less than `outer_radius`
- First point starts at top (270 degrees)
- Total vertices = points × 2 (alternating outer/inner)

### Line

```yaml
type: line               # Required: Discriminator
start_x: 1.0             # Required: Start X in inches (≥ 0.0)
start_y: 2.0             # Required: Start Y in inches (≥ 0.0)
end_x: 4.0               # Required: End X in inches (≥ 0.0)
end_y: 2.0               # Required: End Y in inches (≥ 0.0)

# Stroke styling (fill_color ignored for lines)
stroke_color: "#000000"  # Required for lines (default: black)
stroke_width: 3          # Points
opacity: 1.0
z_index: 0
```

**Notes**:
- Lines have no fill (fill_color is ignored)
- Start and end points should differ (validation warning if length ≈ 0)
- Rotation occurs around midpoint: ((start_x+end_x)/2, (start_y+end_y)/2)

## Decorative Elements

### Using a Decorative Element

```yaml
type: decorative_element  # Required: Discriminator (not "type: geometric_tree")
name: geometric_tree      # Required: Name from decorative element library
x: 4.25                   # Required: Anchor X position in inches (≥ 0.0)
y: 3.0                    # Required: Anchor Y position in inches (≥ 0.0)

# Optional transforms
scale: 1.2                # Proportional scale (default: 1.0, > 0.0)
rotation: 0               # Degrees (default: 0.0)

# Optional color overrides
color_palette:
  tree_primary: "#A8B5A0"  # Sage green (overrides default)
  tree_accent: "#B85C50"   # Burgundy (overrides default)
  ornament: "#D4AF37"      # Gold (overrides default)
  star: "#FFD700"          # Bright gold (overrides default)
```

**Notes**:
- `name` must match a decorative element definition in the library
- Missing `color_palette` uses default colors from definition
- Partial `color_palette` overrides only specified roles, others use defaults
- Scale multiplies all dimensions and positions proportionally
- Rotation rotates entire composition around anchor point (x, y)

### Available Decorative Elements

| Name | Occasion | Description |
|------|----------|-------------|
| `geometric_tree` | Christmas | Overlapping triangle Christmas tree |
| `traditional_tree` | Christmas | Classic Christmas tree silhouette |
| `ornament_bauble` | Christmas | Circular ornament with highlight |
| `ornament_star` | Christmas | Star ornament |
| `gift_box` | Generic | Gift box with ribbon |
| `wreath` | Christmas | Circular wreath |
| `star_topper` | Christmas | Star for tree top |
| `snowflake` | Christmas | Geometric snowflake |
| `menorah` | Hanukkah | Nine-branched candelabra |
| `dreidel` | Hanukkah | Spinning top |

(Full catalog defined in `decorative_elements/` directory)

## Layering with Z-Index

All elements (shapes, text, images) can have a `z_index` property:

```yaml
shape_elements:
  - type: rectangle
    x: 1.0
    y: 1.0
    width: 4.0
    height: 3.0
    fill_color: "#EEEEEE"
    z_index: 1             # Background layer

  - type: circle
    center_x: 3.0
    center_y: 2.5
    radius: 1.0
    fill_color: "#FF0000"
    opacity: 0.5
    z_index: 3             # Foreground layer

text_elements:
  - content: "Hello"
    x: 2.0
    y: 2.0
    font_size: 24
    z_index: 5             # Above shapes
```

**Rendering Order**:
1. All elements sorted by `z_index` (lowest first)
2. Elements with same `z_index` render in definition order
3. Default `z_index` is 0 for shapes, infinity for text/images (text on top)

## Complete Example: Geometric Christmas Card

```yaml
id: geometric-christmas
name: "Geometric Christmas Tree Card"
occasion: christmas
fold_type: half_fold

panels:
  # Front panel
  - position: front
    x: 0.0
    y: 5.5
    width: 8.5
    height: 5.5
    background_color: "#F5F5DC"  # Cream

    shape_elements:
      # Decorative tree composition
      - type: decorative_element
        name: geometric_tree
        x: 4.25               # Centered horizontally
        y: 2.0                # Bottom of panel
        scale: 1.0
        color_palette:
          tree_primary: "#A8B5A0"
          tree_accent: "#B85C50"
          ornament: "#D4AF37"
          star: "#FFD700"

      # Gift box at base
      - type: decorative_element
        name: gift_box
        x: 4.0
        y: 0.8
        scale: 0.5
        color_palette:
          box: "#B85C50"
          ribbon: "#D4AF37"

    text_elements:
      # Greeting above tree
      - content: "Season's Greetings"
        x: 4.25
        y: 0.5
        font_size: 28
        font_style: bold
        alignment: center
        color: "#2E5339"      # Dark green
        z_index: 100          # Above all shapes

  # Inside left panel
  - position: inside_left
    x: 0.0
    y: 0.0
    width: 4.25
    height: 5.5

    text_elements:
      - content: "Wishing you joy and peace this holiday season!"
        x: 2.125
        y: 2.75
        font_size: 16
        alignment: center
        max_lines: 3

  # Inside right panel
  - position: inside_right
    x: 4.25
    y: 0.0
    width: 4.25
    height: 5.5

    shape_elements:
      # Small decorative stars
      - type: star
        center_x: 1.0
        center_y: 4.5
        outer_radius: 0.2
        inner_radius: 0.1
        points: 5
        fill_color: "#D4AF37"
        z_index: 1

      - type: star
        center_x: 3.25
        center_y: 4.5
        outer_radius: 0.2
        inner_radius: 0.1
        points: 5
        fill_color: "#D4AF37"
        z_index: 1

    text_elements:
      - content: "From our family to yours"
        x: 2.125
        y: 2.75
        font_size: 14
        alignment: center
        font_style: italic
```

## Validation Rules

### Required Fields

All shapes must have:
- `type` field (discriminator)
- Position/dimension fields specific to shape type

### Value Constraints

- All positions and dimensions: ≥ 0.0
- All dimensions (width, height, radius): > 0.0
- `stroke_width`: ≥ 0.0
- `opacity`: 0.0 to 1.0
- `rotation`: 0.0 to 360.0 (exclusive upper bound)
- `z_index`: Any integer (including negative)
- `points` (star): 3 to 20
- Hex colors: Match pattern `#[0-9A-Fa-f]{6}`

### Cross-Field Constraints

- Star: `inner_radius` < `outer_radius`
- Triangle: Vertices not collinear (area > 0)
- Line: Start ≠ End (length > 0)
- Shape: At least one of `fill_color` or `stroke_color` set

### Decorative Elements

- `name` must exist in decorative element library
- `color_palette` keys must match color roles in definition
- `scale` > 0.0
- No nesting (decorative elements cannot contain other decorative elements)

## Error Messages

### Invalid Shape Type

```yaml
shape_elements:
  - type: pentagon  # Invalid
```

**Error**: `Validation error: Invalid discriminator value 'pentagon'. Expected one of: rectangle, circle, triangle, star, line, decorative_element`

### Missing Required Field

```yaml
shape_elements:
  - type: circle
    center_x: 3.0
    # Missing center_y and radius
```

**Error**: `Validation error for Circle: Field 'center_y' is required`

### Out of Range Value

```yaml
shape_elements:
  - type: rectangle
    x: 1.0
    y: 2.0
    width: 3.0
    height: 1.5
    opacity: 1.5  # Invalid: > 1.0
```

**Error**: `Validation error for Rectangle.opacity: Value must be ≤ 1.0 (got 1.5)`

### Invalid Hex Color

```yaml
shape_elements:
  - type: circle
    center_x: 3.0
    center_y: 3.0
    radius: 1.0
    fill_color: "blue"  # Invalid: not hex format
```

**Error**: `Validation error for Circle.fill_color: Value must match hex color format #RRGGBB (got 'blue')`

### Unknown Decorative Element

```yaml
shape_elements:
  - type: decorative_element
    name: unicorn  # Not in library
    x: 3.0
    y: 3.0
```

**Error**: `Decorative element 'unicorn' not found in library. Available: geometric_tree, traditional_tree, ornament_bauble, ...`

### Invalid Color Palette Role

```yaml
shape_elements:
  - type: decorative_element
    name: geometric_tree
    x: 3.0
    y: 3.0
    color_palette:
      invalid_role: "#FF0000"  # Not a valid role
```

**Warning**: `Color role 'invalid_role' not used in geometric_tree. Valid roles: tree_primary, tree_accent, ornament, star`

## Backward Compatibility

Templates without `shape_elements` work unchanged:

```yaml
# Existing template (no shapes)
panels:
  - position: front
    x: 0.0
    y: 5.5
    width: 8.5
    height: 5.5

    text_elements:
      - content: "Hello"
        x: 4.25
        y: 2.75

    # shape_elements defaults to [] (empty list)
```

**Result**: Card generates exactly as before, no breaking changes.

## Future Extensions

These features are planned but not yet implemented:

### Ellipse (not implemented)
```yaml
type: ellipse
center_x: 3.0
center_y: 3.0
width: 2.0   # Horizontal diameter
height: 1.0  # Vertical diameter
```

### Gradient Fill (not implemented)
```yaml
fill_gradient:
  type: linear
  start_color: "#FF0000"
  end_color: "#0000FF"
  angle: 45
```

### Pattern Fill (not implemented)
```yaml
fill_pattern:
  type: dots
  spacing: 0.1
  color: "#000000"
```

### Bezier Path (not implemented)
```yaml
type: bezier_path
points:
  - {x: 1, y: 1, control1_x: 2, control1_y: 2, control2_x: 3, control2_y: 1}
```

## References

- Data Model: [data-model.md](../data-model.md)
- Quickstart Guide: [quickstart.md](../quickstart.md)
- Implementation Plan: [plan.md](../plan.md)
