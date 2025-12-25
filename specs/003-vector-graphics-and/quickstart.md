# Quickstart Guide: Vector Graphics and Decorative Elements

**Feature**: Vector Graphics and Decorative Elements System
**Date**: 2025-12-25
**Audience**: Template designers and card creators

## Overview

This guide shows you how to use vector graphics and decorative elements to create sophisticated holiday card designs. You'll learn to add shapes, layer them for depth, and use pre-built decorative elements like Christmas trees and ornaments.

## Prerequisites

- Holiday card generator installed and working
- Familiarity with YAML template format
- Basic understanding of coordinate systems (x/y positioning)

## Your First Shape: A Simple Rectangle

Let's add a colored rectangle to a card template.

**Create**: `templates/christmas/my_first_shape.yaml`

```yaml
id: my-first-shape
name: "My First Shape"
occasion: christmas
fold_type: half_fold

panels:
  - position: front
    x: 0.0
    y: 5.5
    width: 8.5
    height: 5.5
    background_color: "#FFFFFF"

    shape_elements:
      - type: rectangle
        x: 2.0          # 2 inches from left
        y: 2.0          # 2 inches from bottom
        width: 4.5      # 4.5 inches wide
        height: 1.5     # 1.5 inches tall
        fill_color: "#A8B5A0"  # Sage green
        stroke_color: "#2E5339"  # Dark green outline
        stroke_width: 2         # 2-point border

    text_elements:
      - content: "Hello, Shapes!"
        x: 4.25
        y: 2.75
        font_size: 24
        alignment: center
```

**Generate the card**:
```bash
holiday-card generate --template templates/christmas/my_first_shape.yaml --output my_first_shape.pdf
```

**Result**: A card with a sage green rectangle with a dark green border containing centered text.

## Adding Multiple Shapes

Let's create a simple tree using triangles:

```yaml
panels:
  - position: front
    x: 0.0
    y: 5.5
    width: 8.5
    height: 5.5
    background_color: "#F5F5DC"  # Cream

    shape_elements:
      # Tree trunk (rectangle)
      - type: rectangle
        x: 3.9
        y: 1.0
        width: 0.7
        height: 1.0
        fill_color: "#8B4513"  # Saddle brown

      # Bottom triangle
      - type: triangle
        x1: 2.5
        y1: 2.0
        x2: 6.0
        y2: 2.0
        x3: 4.25
        y3: 3.5
        fill_color: "#228B22"  # Forest green

      # Middle triangle
      - type: triangle
        x1: 2.8
        y1: 3.0
        x2: 5.7
        y2: 3.0
        x3: 4.25
        y3: 4.5
        fill_color: "#228B22"

      # Top triangle
      - type: triangle
        x1: 3.1
        y1: 4.0
        x2: 5.4
        y2: 4.0
        x3: 4.25
        y3: 5.2
        fill_color: "#228B22"
```

**Result**: A simple Christmas tree made of three stacked triangles on a brown trunk.

## Layering with Z-Index

Z-index controls which shapes appear on top. Higher values = on top.

```yaml
shape_elements:
  # Background rectangle (bottom layer)
  - type: rectangle
    x: 1.0
    y: 1.0
    width: 6.5
    height: 4.0
    fill_color: "#E6F3FF"  # Light blue
    z_index: 1

  # Circle in middle layer
  - type: circle
    center_x: 4.25
    center_y: 3.0
    radius: 1.5
    fill_color: "#FFEB3B"  # Yellow
    opacity: 0.7
    z_index: 2

  # Star on top layer
  - type: star
    center_x: 4.25
    center_y: 3.0
    outer_radius: 0.8
    inner_radius: 0.4
    points: 5
    fill_color: "#FF5722"  # Deep orange
    z_index: 3

  # Text above all shapes
text_elements:
  - content: "Layered!"
    x: 4.25
    y: 3.0
    font_size: 32
    alignment: center
    z_index: 10  # On top of everything
```

**Rendering order** (bottom to top):
1. Blue rectangle (z_index=1)
2. Yellow circle (z_index=2)
3. Orange star (z_index=3)
4. Text "Layered!" (z_index=10)

## Opacity and Semi-Transparency

Create depth with semi-transparent overlapping shapes:

```yaml
shape_elements:
  # Three overlapping circles
  - type: circle
    center_x: 3.0
    center_y: 3.0
    radius: 1.0
    fill_color: "#FF0000"  # Red
    opacity: 0.5
    z_index: 1

  - type: circle
    center_x: 4.0
    center_y: 3.0
    radius: 1.0
    fill_color: "#00FF00"  # Green
    opacity: 0.5
    z_index: 2

  - type: circle
    center_x: 3.5
    center_y: 4.0
    radius: 1.0
    fill_color: "#0000FF"  # Blue
    opacity: 0.5
    z_index: 3
```

**Result**: Overlapping areas show color blending (red+green=yellow, etc.)

## Rotation

Rotate shapes to create dynamic designs:

```yaml
shape_elements:
  # Rotated rectangles forming a pattern
  - type: rectangle
    x: 3.625
    y: 2.25
    width: 1.25
    height: 1.25
    fill_color: "#D4AF37"  # Gold
    rotation: 0
    z_index: 1

  - type: rectangle
    x: 3.625
    y: 2.25
    width: 1.25
    height: 1.25
    fill_color: "#B8860B"  # Dark goldenrod
    rotation: 45  # Rotated 45 degrees
    opacity: 0.7
    z_index: 2
```

**Result**: Two squares, one rotated 45 degrees to create a star pattern.

## Using Decorative Elements

Instead of creating complex shapes manually, use pre-built decorative elements:

```yaml
panels:
  - position: front
    x: 0.0
    y: 5.5
    width: 8.5
    height: 5.5
    background_color: "#F5F5DC"

    shape_elements:
      # Pre-built geometric Christmas tree
      - type: decorative_element
        name: geometric_tree
        x: 4.25          # Centered horizontally
        y: 1.5           # Position from bottom
        scale: 1.0       # Original size

      # Gift box at base
      - type: decorative_element
        name: gift_box
        x: 4.0
        y: 0.8
        scale: 0.5       # Half size
```

**Result**: A professional geometric Christmas tree and gift box, composed of dozens of shapes, placed with just a few lines of YAML.

## Customizing Decorative Element Colors

Override default colors with a custom palette:

```yaml
shape_elements:
  - type: decorative_element
    name: geometric_tree
    x: 4.25
    y: 1.5
    scale: 1.0

    # Custom color palette
    color_palette:
      tree_primary: "#8B0000"    # Dark red instead of sage
      tree_accent: "#FFD700"     # Gold instead of burgundy
      ornament: "#FFFFFF"        # White ornaments
      star: "#FF4500"            # Orange-red star
```

**Result**: Same geometric tree structure, completely different color scheme.

## Scaling Decorative Elements

Make elements larger or smaller while maintaining proportions:

```yaml
shape_elements:
  # Large tree
  - type: decorative_element
    name: geometric_tree
    x: 2.0
    y: 1.0
    scale: 1.5        # 50% larger

  # Small tree
  - type: decorative_element
    name: geometric_tree
    x: 6.5
    y: 1.0
    scale: 0.5        # 50% smaller
```

**Result**: Two trees, one large and one small, perfectly proportional.

## Rotating Decorative Elements

Rotate entire compositions:

```yaml
shape_elements:
  - type: decorative_element
    name: ornament_star
    x: 2.0
    y: 4.0
    rotation: 0

  - type: decorative_element
    name: ornament_star
    x: 4.25
    y: 4.0
    rotation: 45  # Tilted

  - type: decorative_element
    name: ornament_star
    x: 6.5
    y: 4.0
    rotation: 90  # Sideways
```

**Result**: Three star ornaments at different rotation angles.

## Complete Example: Geometric Christmas Card

Here's a complete, sophisticated template using all the features:

```yaml
id: geometric-christmas-complete
name: "Geometric Christmas - Complete Example"
occasion: christmas
fold_type: half_fold

panels:
  # Front panel - Main design
  - position: front
    x: 0.0
    y: 5.5
    width: 8.5
    height: 5.5
    background_color: "#F5F5DC"  # Cream

    shape_elements:
      # Background decorative elements
      - type: circle
        center_x: 1.5
        center_y: 1.0
        radius: 0.4
        fill_color: "#A8B5A0"
        opacity: 0.3
        z_index: 1

      - type: circle
        center_x: 7.0
        center_y: 4.5
        radius: 0.3
        fill_color: "#B85C50"
        opacity: 0.3
        z_index: 1

      # Main geometric tree
      - type: decorative_element
        name: geometric_tree
        x: 4.25
        y: 1.5
        scale: 1.0
        z_index: 5
        color_palette:
          tree_primary: "#A8B5A0"
          tree_accent: "#B85C50"
          ornament: "#D4AF37"
          star: "#FFD700"

      # Gift boxes at base
      - type: decorative_element
        name: gift_box
        x: 2.5
        y: 0.8
        scale: 0.4
        z_index: 6
        color_palette:
          box: "#B85C50"
          ribbon: "#D4AF37"

      - type: decorative_element
        name: gift_box
        x: 5.8
        y: 0.8
        scale: 0.35
        rotation: 15
        z_index: 6
        color_palette:
          box: "#A8B5A0"
          ribbon: "#B85C50"

    text_elements:
      # Main greeting
      - content: "Season's Greetings"
        x: 4.25
        y: 0.5
        font_size: 28
        font_style: bold
        alignment: center
        color: "#2E5339"
        z_index: 100

  # Inside left - Personal message
  - position: inside_left
    x: 0.0
    y: 0.0
    width: 4.25
    height: 5.5

    shape_elements:
      # Decorative corner stars
      - type: star
        center_x: 0.5
        center_y: 5.0
        outer_radius: 0.15
        inner_radius: 0.08
        points: 5
        fill_color: "#D4AF37"

      - type: star
        center_x: 3.75
        center_y: 0.5
        outer_radius: 0.15
        inner_radius: 0.08
        points: 5
        fill_color: "#D4AF37"

    text_elements:
      - content: "Wishing you joy, peace, and happiness this holiday season and throughout the new year!"
        x: 2.125
        y: 2.75
        width: 3.5
        font_size: 14
        alignment: center
        max_lines: 5

  # Inside right - Signature
  - position: inside_right
    x: 4.25
    y: 0.0
    width: 4.25
    height: 5.5

    shape_elements:
      # Small decorative tree
      - type: decorative_element
        name: geometric_tree
        x: 2.125
        y: 3.5
        scale: 0.4
        color_palette:
          tree_primary: "#A8B5A0"
          tree_accent: "#B85C50"
          ornament: "#D4AF37"
          star: "#FFD700"

    text_elements:
      - content: "From our family to yours,"
        x: 2.125
        y: 2.0
        font_size: 14
        alignment: center
        font_style: italic

      - content: "The Smiths"
        x: 2.125
        y: 1.5
        font_size: 16
        alignment: center
        font_style: bold

  # Back panel - Simple design
  - position: back
    x: 0.0
    y: 0.0
    width: 8.5
    height: 5.5
    background_color: "#A8B5A0"

    shape_elements:
      # Small star pattern
      - type: star
        center_x: 4.25
        center_y: 2.75
        outer_radius: 0.3
        inner_radius: 0.15
        points: 5
        fill_color: "#FFD700"
        opacity: 0.5
```

**Generate the card**:
```bash
holiday-card generate --template templates/christmas/geometric-christmas-complete.yaml --output geometric_christmas.pdf
```

## Available Decorative Elements

| Element Name | Description | Color Roles |
|--------------|-------------|-------------|
| `geometric_tree` | Overlapping triangle tree | tree_primary, tree_accent, ornament, star |
| `traditional_tree` | Classic tree silhouette | tree, trunk |
| `ornament_bauble` | Round ornament with highlight | bauble, highlight, hanger |
| `ornament_star` | Star ornament | star, outline |
| `gift_box` | Gift with ribbon | box, ribbon, bow |
| `wreath` | Circular wreath | wreath, berries, bow |
| `star_topper` | Tree topper star | star, glow |
| `snowflake` | Geometric snowflake | snowflake |
| `menorah` | Nine-branched candelabra | candelabra, flames |
| `dreidel` | Spinning top | body, letter |

## Tips and Best Practices

### 1. Start Simple
Begin with basic shapes, then progress to decorative elements once comfortable.

### 2. Use Z-Index Strategically
- Background decorations: z_index 1-10
- Main design elements: z_index 10-50
- Foreground accents: z_index 50-90
- Text: z_index 100+

### 3. Respect Safe Margins
Keep shapes at least 0.25" from panel edges to ensure they print correctly:
- Minimum x: 0.25"
- Maximum x: panel_width - 0.25"
- Same for y coordinates

### 4. Test Opacity Carefully
- Start with opacity 0.7-0.9 for subtle transparency
- Use opacity < 0.5 for background watermark effects
- Remember overlapping opaque shapes don't blend

### 5. Scale Decorative Elements Appropriately
- scale 0.5-2.0 for most use cases
- Very small (< 0.3) may lose detail
- Very large (> 2.5) may extend beyond panel

### 6. Limit Shape Count
- < 50 shapes per card for fast generation
- > 100 shapes may slow rendering significantly

### 7. Use Descriptive Comments
```yaml
shape_elements:
  # Background sky gradient simulation
  - type: rectangle
    # ... properties

  # Main Christmas tree
  - type: decorative_element
    # ... properties
```

## Troubleshooting

### Shapes Not Appearing

**Problem**: Shapes defined but not visible in PDF.

**Solutions**:
- Check z_index: Low values may be behind background
- Verify fill_color or stroke_color is set (at least one required)
- Ensure opacity > 0.0
- Confirm coordinates are within panel boundaries

### Colors Look Wrong

**Problem**: Colors appear different than expected.

**Solutions**:
- Verify hex color format: `#RRGGBB` (6 hex digits)
- Check opacity: Low opacity lightens colors
- Test on actual printer: Screen colors differ from print

### Decorative Element Not Found

**Problem**: Error message "Decorative element 'X' not found"

**Solutions**:
- Check spelling of element name
- Verify element exists in library (see available elements above)
- Check that decorative elements are loaded (library path)

### Shapes Clipped or Cut Off

**Problem**: Shapes appear incomplete at panel edges.

**Solutions**:
- Respect safe margins (0.25" from edges)
- Reduce size or reposition shapes
- Check that shape coordinates + dimensions stay within panel

## Next Steps

- Explore the full [YAML schema reference](contracts/shape-yaml-schema.md)
- Review the [data model documentation](data-model.md)
- Study existing templates in `templates/` directory
- Create your own decorative elements (advanced)

## Support

For issues or questions:
- Check [data-model.md](data-model.md) for entity definitions
- Review [contracts/shape-yaml-schema.md](contracts/shape-yaml-schema.md) for YAML syntax
- See [research.md](research.md) for technical details
