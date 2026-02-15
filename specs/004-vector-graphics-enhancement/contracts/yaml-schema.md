# YAML Schema: Vector Graphics Enhancement

**Feature**: 004-vector-graphics-enhancement
**Date**: 2025-12-25

## Overview

This document defines the extended YAML template schema for SVG paths, gradient fills, pattern fills, and image clipping masks. All extensions maintain backward compatibility with existing templates.

---

## SVG Path Shape

### Schema

```yaml
shapes:
  - type: svg_path              # Required: Shape type discriminator
    path_data: string           # Required: SVG path commands (1-10000 chars)
    scale: float                # Optional: Scale multiplier (default: 1.0, range: 0.0-10.0)

    # Optional styling (inherited from BaseShape)
    fill_color: string          # Legacy: Solid fill color #RRGGBB
    fill: FillStyle             # Modern: Solid, gradient, or pattern fill
    stroke_color: string        # Stroke color #RRGGBB
    stroke_width: float         # Stroke width in points (default: 0.0)
    opacity: float              # Opacity 0.0-1.0 (default: 1.0)
    rotation: float             # Rotation in degrees 0-360 (default: 0.0)
    z_index: integer            # Rendering layer (default: 0)
```

### Example: Holly Leaf

```yaml
shapes:
  - type: svg_path
    path_data: "M 50 10 Q 30 20 20 40 Q 10 30 5 25 Q 15 20 20 40 Q 25 50 50 60 Q 75 50 80 40 Q 85 20 95 25 Q 90 30 80 40 Q 70 20 50 10 Z"
    fill_color: "#2D5016"  # Dark green
    stroke_color: "#1A3009"
    stroke_width: 1.5
    scale: 1.0
    z_index: 2
```

### Validation Rules

- `path_data`: Must start with M or m (moveTo command)
- `path_data`: Length 1-10,000 characters
- `scale`: Must be > 0.0 and <= 10.0
- All BaseShape validation rules apply

---

## Gradient Fills

### Linear Gradient Schema

```yaml
fill:
  type: linear_gradient        # Required: Fill type discriminator
  angle: float                 # Required: Gradient angle in degrees (0-360)
  stops:                       # Required: 2-20 color stops
    - position: float          # Required: Position 0.0-1.0
      color: string            # Required: Hex color #RRGGBB
    - position: float
      color: string
    # ... additional stops
```

### Linear Gradient Example: Sunset Sky

```yaml
shapes:
  - type: rectangle
    x: 0.0
    y: 3.0
    width: 4.25
    height: 2.5
    fill:
      type: linear_gradient
      angle: 90  # Bottom-to-top
      stops:
        - position: 0.0
          color: "#FF6B35"  # Orange at bottom
        - position: 0.5
          color: "#F7C59F"  # Peach in middle
        - position: 1.0
          color: "#004E89"  # Blue at top
    stroke_width: 0
```

### Radial Gradient Schema

```yaml
fill:
  type: radial_gradient        # Required: Fill type discriminator
  center_x: float              # Required: Center X in inches (relative to shape)
  center_y: float              # Required: Center Y in inches (relative to shape)
  radius: float                # Required: Gradient radius in inches (> 0)
  stops:                       # Required: 2-20 color stops
    - position: float          # Required: Position 0.0-1.0
      color: string            # Required: Hex color #RRGGBB
    - position: float
      color: string
```

### Radial Gradient Example: Ornament Highlight

```yaml
shapes:
  - type: circle
    center_x: 2.0
    center_y: 3.0
    radius: 0.75
    fill:
      type: radial_gradient
      center_x: 2.0   # Same as circle center
      center_y: 3.0
      radius: 0.75
      stops:
        - position: 0.0
          color: "#FFD700"  # Gold center
        - position: 0.7
          color: "#DAA520"  # Dark gold
        - position: 1.0
          color: "#8B6914"  # Bronze edge
    stroke_color: "#654321"
    stroke_width: 2.0
```

### Gradient Validation Rules

- `stops`: Minimum 2, maximum 20 color stops
- `stops[].position`: Must be in range 0.0-1.0
- `stops`: Positions must be in ascending order
- `stops[].color`: Must match pattern `^#[0-9A-Fa-f]{6}$`
- Linear `angle`: Must be in range 0.0-360.0
- Radial `radius`: Must be > 0.0

---

## Pattern Fills

### Schema

```yaml
fill:
  type: pattern                # Required: Fill type discriminator
  pattern_type: enum           # Required: stripes|dots|grid|checkerboard
  spacing: float               # Required: Pattern element spacing in inches (0-2)
  angle: float                 # Optional: Pattern rotation in degrees (default: 0.0)
  scale: float                 # Optional: Pattern scale multiplier (default: 1.0, range: 0-5)
  colors:                      # Required: 1-2 hex colors
    - string                   # Primary color #RRGGBB
    - string                   # Secondary color #RRGGBB (for alternating patterns)
```

### Example: Diagonal Stripes

```yaml
shapes:
  - type: rectangle
    x: 0.25
    y: 0.25
    width: 4.0
    height: 5.5
    fill:
      type: pattern
      pattern_type: stripes
      spacing: 0.25  # 1/4 inch stripes
      angle: 45      # Diagonal
      colors:
        - "#DC143C"  # Crimson
        - "#FFFFFF"  # White
```

### Example: Polka Dots

```yaml
shapes:
  - type: rectangle
    x: 0.25
    y: 0.25
    width: 4.0
    height: 5.5
    fill:
      type: pattern
      pattern_type: dots
      spacing: 0.5  # Dots every 1/2 inch
      scale: 1.0
      colors:
        - "#FFD700"  # Gold dots
```

### Example: Checkerboard

```yaml
shapes:
  - type: rectangle
    x: 0.0
    y: 0.0
    width: 4.25
    height: 5.5
    fill:
      type: pattern
      pattern_type: checkerboard
      spacing: 0.5  # 1/2 inch squares
      colors:
        - "#8B0000"  # Dark red
        - "#FFFFFF"  # White
```

### Pattern Validation Rules

- `pattern_type`: Must be one of `stripes`, `dots`, `grid`, `checkerboard`
- `spacing`: Must be > 0.0 and <= 2.0 inches
- `angle`: Must be in range 0.0-360.0
- `scale`: Must be > 0.0 and <= 5.0
- `colors`: Minimum 1, maximum 2 hex colors
- `colors[]`: Must match pattern `^#[0-9A-Fa-f]{6}$`

---

## Image Clipping Masks

### Circle Clip Mask Schema

```yaml
images:
  - source_path: string
    x: float
    y: float
    width: float
    height: float
    clip_mask:
      type: circle             # Required: Mask type discriminator
      center_x: float          # Required: Circle center X in inches
      center_y: float          # Required: Circle center Y in inches
      radius: float            # Required: Circle radius in inches (> 0)
```

### Circle Clip Example: Circular Photo Frame

```yaml
images:
  - source_path: "family_photo.jpg"
    x: 0.5
    y: 1.0
    width: 3.25
    height: 3.25
    clip_mask:
      type: circle
      center_x: 2.125  # Center of 3.25" image (0.5 + 3.25/2)
      center_y: 2.625  # Center of 3.25" image (1.0 + 3.25/2)
      radius: 1.5      # 3" diameter circle
```

### Rectangle Clip Mask Schema

```yaml
clip_mask:
  type: rectangle              # Required: Mask type discriminator
  x: float                     # Required: Rectangle X in inches
  y: float                     # Required: Rectangle Y in inches
  width: float                 # Required: Rectangle width in inches (> 0)
  height: float                # Required: Rectangle height in inches (> 0)
```

### Ellipse Clip Mask Schema

```yaml
clip_mask:
  type: ellipse                # Required: Mask type discriminator
  center_x: float              # Required: Ellipse center X in inches
  center_y: float              # Required: Ellipse center Y in inches
  radius_x: float              # Required: Horizontal radius in inches (> 0)
  radius_y: float              # Required: Vertical radius in inches (> 0)
```

### Star Clip Mask Schema

```yaml
clip_mask:
  type: star                   # Required: Mask type discriminator
  center_x: float              # Required: Star center X in inches
  center_y: float              # Required: Star center Y in inches
  outer_radius: float          # Required: Outer point radius in inches (> 0)
  inner_radius: float          # Required: Inner point radius in inches (> 0, < outer)
  points: integer              # Optional: Number of points (default: 5, range: 3-20)
```

### Star Clip Example: Star-Shaped Photo

```yaml
images:
  - source_path: "holiday_moment.jpg"
    x: 0.75
    y: 1.5
    width: 2.75
    height: 2.75
    clip_mask:
      type: star
      center_x: 2.125
      center_y: 2.875
      outer_radius: 1.25
      inner_radius: 0.6
      points: 5
```

### SVG Path Clip Mask Schema

```yaml
clip_mask:
  type: svg_path               # Required: Mask type discriminator
  path_data: string            # Required: SVG path commands (closed path, 1-5000 chars)
  scale: float                 # Optional: Scale multiplier (default: 1.0, range: 0-10)
```

### SVG Path Clip Example: Heart-Shaped Photo

```yaml
images:
  - source_path: "loved_one.jpg"
    x: 1.0
    y: 2.0
    width: 2.5
    height: 2.5
    clip_mask:
      type: svg_path
      path_data: "M 125 75 Q 125 50 100 50 Q 75 50 75 75 Q 75 100 125 150 Q 175 100 175 75 Q 175 50 150 50 Q 125 50 125 75 Z"
      scale: 0.01  # Scale down to fit 2.5" image
```

### Clipping Mask Validation Rules

- All mask types: Coordinates must be >= 0.0
- Circle: `radius` must be > 0.0
- Rectangle: `width` and `height` must be > 0.0
- Ellipse: `radius_x` and `radius_y` must be > 0.0
- Star: `inner_radius` must be > 0.0 and < `outer_radius`
- Star: `points` must be in range 3-20
- SVG Path: `path_data` must start with M/m and end with Z/z (closed path)
- SVG Path: `path_data` length 1-5,000 characters

---

## Backward Compatibility

### Legacy Fill Color (Deprecated but Supported)

**Old Style** (still works):
```yaml
shapes:
  - type: rectangle
    x: 1.0
    y: 1.0
    width: 2.0
    height: 3.0
    fill_color: "#FF0000"  # Red solid fill
```

**New Style** (recommended):
```yaml
shapes:
  - type: rectangle
    x: 1.0
    y: 1.0
    width: 2.0
    height: 3.0
    fill:
      type: solid
      color: "#FF0000"  # Red solid fill
```

**Parser Behavior**:
- If `fill_color` present and `fill` absent → convert to `SolidFill`
- If `fill` present and `fill_color` absent → use `fill` directly
- If both present → validation error (cannot specify both)

### Images Without Clipping (Default Behavior)

**Without Clipping** (existing templates):
```yaml
images:
  - source_path: "photo.jpg"
    x: 1.0
    y: 1.0
    width: 3.0
    height: 3.0
    # No clip_mask → image renders normally (full rectangle)
```

**With Clipping** (new templates):
```yaml
images:
  - source_path: "photo.jpg"
    x: 1.0
    y: 1.0
    width: 3.0
    height: 3.0
    clip_mask:
      type: circle
      center_x: 2.5
      center_y: 2.5
      radius: 1.4
```

---

## Complete Example Template

### Holly Wreath Card with All New Features

```yaml
# templates/christmas/holly_wreath_gradient.yaml
name: "Holly Wreath with Gradient Sky"
occasion: christmas
fold_type: half_fold

panels:
  front:
    background_color: "#FFFFFF"

    shapes:
      # Gradient sky background
      - type: rectangle
        x: 0.25
        y: 3.0
        width: 4.0
        height: 2.25
        fill:
          type: linear_gradient
          angle: 90
          stops:
            - position: 0.0
              color: "#E8F4F8"  # Light blue
            - position: 1.0
              color: "#004E89"  # Dark blue
        z_index: 0

      # Striped ribbon background
      - type: rectangle
        x: 0.25
        y: 2.0
        width: 4.0
        height: 0.75
        fill:
          type: pattern
          pattern_type: stripes
          spacing: 0.15
          angle: 45
          colors:
            - "#DC143C"
            - "#FFFFFF"
        z_index: 1

      # SVG holly leaf (left)
      - type: svg_path
        path_data: "M 50 10 Q 30 20 20 40 Q 10 30 5 25 Q 15 20 20 40 Q 25 50 50 60 Q 75 50 80 40 Q 85 20 95 25 Q 90 30 80 40 Q 70 20 50 10 Z"
        fill_color: "#2D5016"
        stroke_color: "#1A3009"
        stroke_width: 1.5
        scale: 0.02
        z_index: 3

      # SVG holly leaf (right) - mirrored
      - type: svg_path
        path_data: "M 50 10 Q 70 20 80 40 Q 90 30 95 25 Q 85 20 80 40 Q 75 50 50 60 Q 25 50 20 40 Q 15 20 5 25 Q 10 30 20 40 Q 30 20 50 10 Z"
        fill_color: "#2D5016"
        stroke_color: "#1A3009"
        stroke_width: 1.5
        scale: 0.02
        z_index: 3

      # Gradient ornament (center)
      - type: circle
        center_x: 2.25
        center_y: 2.375
        radius: 0.5
        fill:
          type: radial_gradient
          center_x: 2.25
          center_y: 2.375
          radius: 0.5
          stops:
            - position: 0.0
              color: "#FFD700"
            - position: 0.7
              color: "#DAA520"
            - position: 1.0
              color: "#8B6914"
        stroke_color: "#654321"
        stroke_width: 2.0
        z_index: 4

    images:
      # Circular family photo
      - source_path: "family_photo.jpg"
        x: 0.875
        y: 0.25
        width: 2.75
        height: 2.75
        clip_mask:
          type: circle
          center_x: 2.25
          center_y: 1.625
          radius: 1.25

    text_elements:
      - text: "Happy Holidays!"
        x: 2.25
        y: 5.5
        font_size: 36
        font_style: bold
        color: "#8B0000"
        alignment: center
```

---

## Schema Validation Checklist

When creating templates with new features:

### SVG Paths
- [ ] Path data starts with M or m command
- [ ] Path data length < 10,000 characters
- [ ] Scale value between 0.0 and 10.0
- [ ] Closed paths end with Z or z

### Gradients
- [ ] Minimum 2 color stops defined
- [ ] Maximum 20 color stops
- [ ] Stop positions in range 0.0-1.0
- [ ] Stop positions in ascending order
- [ ] All colors in #RRGGBB format
- [ ] Linear gradient angle 0-360
- [ ] Radial gradient radius > 0

### Patterns
- [ ] Pattern type is valid enum (stripes/dots/grid/checkerboard)
- [ ] Spacing 0.0 < spacing <= 2.0
- [ ] Angle 0-360 degrees
- [ ] Scale 0.0 < scale <= 5.0
- [ ] 1-2 colors defined in #RRGGBB format

### Clipping Masks
- [ ] All coordinates >= 0.0
- [ ] Circle/ellipse radii > 0.0
- [ ] Rectangle width/height > 0.0
- [ ] Star inner_radius < outer_radius
- [ ] Star points 3-20
- [ ] SVG path closed (ends with Z/z)
- [ ] SVG path length < 5,000 characters

---

## Error Messages

### SVG Path Errors

```
ValidationError: SVG path must start with M (moveTo) command
  → path_data: "L 10 10 ..."

ValidationError: SVG path data length exceeds maximum (10000 characters)
  → path_data: "M 0 0 L 1 1 L 2 2 ..." (12543 characters)
```

### Gradient Errors

```
ValidationError: Color stop positions must be in ascending order
  → stops: [{position: 0.5, color: "#FF0000"}, {position: 0.3, color: "#0000FF"}]

ValidationError: Gradients require at least 2 color stops
  → stops: [{position: 0.0, color: "#FF0000"}]
```

### Pattern Errors

```
ValidationError: Pattern spacing must be between 0.0 and 2.0 inches
  → spacing: 3.5

ValidationError: Invalid pattern type 'plaid'. Must be one of: stripes, dots, grid, checkerboard
  → pattern_type: "plaid"
```

### Clipping Mask Errors

```
ValidationError: Clipping path must be closed (end with Z)
  → path_data: "M 10 10 L 20 20 L 30 10"

ValidationError: Star inner_radius (0.8) must be less than outer_radius (0.5)
  → inner_radius: 0.8, outer_radius: 0.5
```

---

## Next Steps

1. Update `src/holiday_card/core/templates.py` with YAML parsing for new types
2. Create example templates in `templates/christmas/`
3. Generate quickstart integration examples
