# Quickstart Guide: Vector Graphics Enhancement

**Feature**: 004-vector-graphics-enhancement
**Date**: 2025-12-25
**Audience**: Template designers, feature implementers, integration testers

## Overview

This guide provides practical integration scenarios for using SVG paths, gradients, patterns, and clipping masks in holiday card templates. Each scenario includes YAML template code, expected output description, and common pitfalls.

---

## Scenario 1: Adding SVG Decorative Elements

**Use Case**: Import a holly leaf SVG decoration to create a festive border.

### Step 1: Obtain SVG Path Data

From an SVG file or design tool (Inkscape, Illustrator), extract the `d` attribute from a `<path>` element:

```xml
<!-- holly_leaf.svg -->
<path d="M 50 10 Q 30 20 20 40 Q 10 30 5 25 Q 15 20 20 40 Q 25 50 50 60 Q 75 50 80 40 Q 85 20 95 25 Q 90 30 80 40 Q 70 20 50 10 Z" />
```

Copy the path data: `M 50 10 Q 30 20 20 40 Q 10 30 5 25 Q 15 20 20 40 Q 25 50 50 60 Q 75 50 80 40 Q 85 20 95 25 Q 90 30 80 40 Q 70 20 50 10 Z`

### Step 2: Add to YAML Template

```yaml
# templates/christmas/holly_border.yaml
name: "Holly Border Card"
occasion: christmas
fold_type: half_fold

panels:
  front:
    background_color: "#FFFFFF"
    shapes:
      # Holly leaf (top-left corner)
      - type: svg_path
        path_data: "M 50 10 Q 30 20 20 40 Q 10 30 5 25 Q 15 20 20 40 Q 25 50 50 60 Q 75 50 80 40 Q 85 20 95 25 Q 90 30 80 40 Q 70 20 50 10 Z"
        fill_color: "#2D5016"  # Dark green
        stroke_color: "#1A3009"  # Very dark green
        stroke_width: 1.5
        scale: 0.015  # Scale down from SVG units to inches
        z_index: 2

    text_elements:
      - text: "Season's Greetings"
        x: 2.25
        y: 3.0
        font_size: 32
        alignment: center
        color: "#8B0000"
```

### Step 3: Generate Card

```bash
holiday-card generate --template templates/christmas/holly_border.yaml --output holly_border.pdf
```

### Expected Output

- PDF with holly leaf in top-left corner
- Leaf scaled to approximately 1.5" x 1.5"
- Dark green fill with darker stroke outline
- "Season's Greetings" text centered

### Common Pitfalls

❌ **Path coordinates too large**: SVG editors often use pixel units (e.g., 0-500). Use `scale` to convert to inches.
  - **Solution**: Start with `scale: 0.01` and adjust based on preview

❌ **Path not visible**: Z-index conflicts with background or other elements.
  - **Solution**: Set `z_index: 2` or higher to ensure path renders on top

❌ **Unclosed path**: Path doesn't end with `Z`, causing fill issues.
  - **Solution**: Add `Z` to end of `path_data` to close the path

---

## Scenario 2: Creating Gradient Backgrounds

**Use Case**: Design a sunset sky background using a linear gradient.

### YAML Template

```yaml
# templates/christmas/sunset_sky.yaml
name: "Sunset Sky Card"
occasion: christmas
fold_type: half_fold

panels:
  front:
    shapes:
      # Gradient sky background (full panel)
      - type: rectangle
        x: 0.25  # Account for safe margin
        y: 0.25
        width: 4.0  # 4.5" - 0.5" margins
        height: 5.5  # 6.0" - 0.5" margins
        fill:
          type: linear_gradient
          angle: 90  # Bottom-to-top (0° = left-to-right, 90° = bottom-to-top)
          stops:
            - position: 0.0
              color: "#FF6B35"  # Orange at horizon
            - position: 0.4
              color: "#F7C59F"  # Peach in middle
            - position: 0.7
              color: "#B392AC"  # Purple
            - position: 1.0
              color: "#004E89"  # Dark blue at top
        stroke_width: 0  # No border
        z_index: 0

      # Snow ground (solid white)
      - type: rectangle
        x: 0.25
        y: 0.25
        width: 4.0
        height: 1.5
        fill_color: "#FFFFFF"
        z_index: 1

    text_elements:
      - text: "Wishing You Joy"
        x: 2.25
        y: 4.5
        font_size: 28
        alignment: center
        color: "#FFFFFF"  # White text on dark gradient
```

### Expected Output

- Smooth color transition from orange (bottom) → peach → purple → blue (top)
- White snow ground in lower portion
- White text legible against dark blue gradient

### Common Pitfalls

❌ **Color banding**: Too few color stops causes visible bands.
  - **Solution**: Use 3-5 color stops for smooth transitions

❌ **Wrong angle**: Gradient goes left-to-right instead of bottom-to-top.
  - **Solution**: Use `angle: 90` for vertical, `angle: 0` for horizontal

❌ **Stops out of order**: Validation error on positions not ascending.
  - **Solution**: Ensure positions are 0.0, 0.4, 0.7, 1.0 (ascending order)

---

## Scenario 3: Radial Gradient for Ornaments

**Use Case**: Create metallic-looking Christmas ornament with radial gradient highlight.

### YAML Template

```yaml
# templates/christmas/metallic_ornaments.yaml
name: "Metallic Ornaments"
occasion: christmas
fold_type: half_fold

panels:
  front:
    background_color: "#004E89"  # Dark blue
    shapes:
      # Gold ornament with radial gradient
      - type: circle
        center_x: 1.5
        center_y: 3.0
        radius: 0.75
        fill:
          type: radial_gradient
          center_x: 1.5
          center_y: 3.0
          radius: 0.75
          stops:
            - position: 0.0
              color: "#FFD700"  # Bright gold center (highlight)
            - position: 0.5
              color: "#DAA520"  # Medium gold
            - position: 1.0
              color: "#8B6914"  # Dark gold edge (shadow)
        stroke_color: "#654321"  # Brown cap
        stroke_width: 2.0

      # Silver ornament with radial gradient
      - type: circle
        center_x: 3.0
        center_y: 3.0
        radius: 0.75
        fill:
          type: radial_gradient
          center_x: 3.0
          center_y: 3.0
          radius: 0.75
          stops:
            - position: 0.0
              color: "#F5F5F5"  # Bright silver center
            - position: 0.5
              color: "#C0C0C0"  # Medium silver
            - position: 1.0
              color: "#808080"  # Dark silver edge
        stroke_color: "#654321"
        stroke_width: 2.0
```

### Expected Output

- Two circular ornaments with 3D metallic appearance
- Gold ornament: bright center fading to dark edges
- Silver ornament: same lighting effect in grayscale
- Brown stroke simulates ornament cap

### Common Pitfalls

❌ **Gradient center doesn't match shape center**: Off-center highlight looks unnatural.
  - **Solution**: Use same `center_x`, `center_y`, `radius` for both gradient and circle

❌ **Too few stops**: Only 2 stops creates flat look, not 3D.
  - **Solution**: Use at least 3 stops (highlight, mid-tone, shadow)

---

## Scenario 4: Pattern Fills for Festive Backgrounds

**Use Case**: Create wrapping paper effect with striped or polka dot patterns.

### Diagonal Stripes Template

```yaml
# templates/christmas/festive_stripes.yaml
name: "Festive Stripes"
occasion: christmas
fold_type: half_fold

panels:
  front:
    shapes:
      # Diagonal red and white stripes (full panel)
      - type: rectangle
        x: 0.25
        y: 0.25
        width: 4.0
        height: 5.5
        fill:
          type: pattern
          pattern_type: stripes
          spacing: 0.25  # 1/4" stripe width
          angle: 45      # Diagonal (45°)
          colors:
            - "#DC143C"  # Crimson
            - "#FFFFFF"  # White
        z_index: 0

    text_elements:
      - text: "Happy Holidays!"
        x: 2.25
        y: 3.0
        font_size: 36
        alignment: center
        color: "#FFD700"  # Gold text
        font_style: bold
```

### Polka Dots Template

```yaml
# templates/christmas/polka_dots.yaml
name: "Polka Dot Cheer"
occasion: christmas
fold_type: half_fold

panels:
  front:
    shapes:
      # Red background with gold dots
      - type: rectangle
        x: 0.25
        y: 0.25
        width: 4.0
        height: 5.5
        fill_color: "#8B0000"  # Dark red background
        z_index: 0

      - type: rectangle
        x: 0.25
        y: 0.25
        width: 4.0
        height: 5.5
        fill:
          type: pattern
          pattern_type: dots
          spacing: 0.5   # Dots every 1/2 inch
          scale: 1.0     # Normal size
          colors:
            - "#FFD700"  # Gold dots
        z_index: 1
```

### Expected Output

**Stripes**:
- Alternating crimson and white diagonal stripes
- 1/4" stripe width at 45° angle
- Gold text legible over pattern

**Polka Dots**:
- Dark red background with evenly-spaced gold dots
- Dots appear every 1/2" in grid layout

### Common Pitfalls

❌ **Pattern too dense**: Small spacing makes pattern overwhelming.
  - **Solution**: Use spacing >= 0.25" for print legibility

❌ **Pattern not visible on small shapes**: Pattern elements larger than shape.
  - **Solution**: Reduce `spacing` or increase `scale` for small shapes

❌ **Single color pattern**: Only one color provided for alternating pattern.
  - **Solution**: Provide 2 colors for stripes/checkerboard (1 color OK for dots/grid)

---

## Scenario 5: Clipping Images to Shapes

**Use Case**: Create a circular photo frame for family holiday photo.

### Circular Clip Template

```yaml
# templates/christmas/photo_ornament.yaml
name: "Photo Ornament Card"
occasion: christmas
fold_type: half_fold

panels:
  front:
    background_color: "#004E89"  # Dark blue

    images:
      # Family photo clipped to circle
      - source_path: "family_photo.jpg"
        x: 0.875   # Center on 4.5" panel: (4.5 - 2.75) / 2 = 0.875
        y: 1.5
        width: 2.75
        height: 2.75
        clip_mask:
          type: circle
          center_x: 2.25  # x + width/2 = 0.875 + 1.375 = 2.25
          center_y: 2.875 # y + height/2 = 1.5 + 1.375 = 2.875
          radius: 1.25    # Slightly smaller than image (2.75/2 = 1.375)

    shapes:
      # Gold ornament cap
      - type: rectangle
        x: 2.0
        y: 4.25
        width: 0.5
        height: 0.3
        fill_color: "#DAA520"
        z_index: 2

      # Ornament hanger
      - type: line
        start_x: 2.25
        start_y: 4.55
        end_x: 2.25
        end_y: 5.0
        stroke_color: "#C0C0C0"
        stroke_width: 2.0
        z_index: 2

    text_elements:
      - text: "Merry Christmas!"
        x: 2.25
        y: 0.75
        font_size: 28
        alignment: center
        color: "#FFFFFF"
```

### Star-Shaped Clip Template

```yaml
# templates/christmas/star_photo.yaml
panels:
  front:
    background_color: "#8B0000"  # Dark red

    images:
      - source_path: "holiday_moment.jpg"
        x: 0.75
        y: 1.5
        width: 3.0
        height: 3.0
        clip_mask:
          type: star
          center_x: 2.25  # x + width/2
          center_y: 3.0   # y + height/2
          outer_radius: 1.4
          inner_radius: 0.65
          points: 5
```

### Expected Output

**Circular Clip**:
- Family photo visible only within 2.5" diameter circle
- Gold rectangle and silver line simulate ornament cap and hanger
- Photo appears as ornament decoration

**Star Clip**:
- Holiday photo clipped to 5-pointed star shape
- Star positioned centrally on dark red background

### Common Pitfalls

❌ **Mask center doesn't match image center**: Photo appears off-center in mask.
  - **Solution**: Calculate mask center as `image_x + image_width/2`, `image_y + image_height/2`

❌ **Mask larger than image**: No clipping occurs, full image visible.
  - **Solution**: Ensure mask radius/dimensions smaller than image bounds

❌ **Important photo content clipped**: Key faces/objects cut off by mask.
  - **Solution**: Test with actual photo, adjust mask size/position to preserve content

---

## Scenario 6: Combining All Features

**Use Case**: Create a sophisticated card using SVG paths, gradients, patterns, and clipped images together.

### Complex Template

```yaml
# templates/christmas/masterpiece.yaml
name: "Holiday Masterpiece"
occasion: christmas
fold_type: half_fold

panels:
  front:
    shapes:
      # Layer 1: Gradient sky
      - type: rectangle
        x: 0.25
        y: 2.75
        width: 4.0
        height: 3.0
        fill:
          type: linear_gradient
          angle: 90
          stops:
            - position: 0.0
              color: "#87CEEB"  # Sky blue
            - position: 1.0
              color: "#000080"  # Navy
        z_index: 0

      # Layer 2: Striped ground
      - type: rectangle
        x: 0.25
        y: 0.25
        width: 4.0
        height: 2.5
        fill:
          type: pattern
          pattern_type: stripes
          spacing: 0.2
          angle: 0  # Horizontal
          colors:
            - "#FFFFFF"  # Snow white
            - "#F0F8FF"  # Alice blue (subtle)
        z_index: 1

      # Layer 3: SVG tree
      - type: svg_path
        path_data: "M 50 0 L 75 50 L 65 50 L 85 90 L 70 90 L 95 140 L 5 140 L 30 90 L 15 90 L 35 50 L 25 50 Z"
        fill:
          type: linear_gradient
          angle: 180  # Top-to-bottom
          stops:
            - position: 0.0
              color: "#0F4D0F"  # Dark green top
            - position: 1.0
              color: "#2D5016"  # Lighter green bottom
        stroke_color: "#0A3A0A"
        stroke_width: 1.0
        scale: 0.02
        z_index: 2

    images:
      # Circular star ornament photo
      - source_path: "ornament_photo.jpg"
        x: 1.5
        y: 3.5
        width: 1.5
        height: 1.5
        clip_mask:
          type: circle
          center_x: 2.25
          center_y: 4.25
          radius: 0.65
        z_index: 3

    text_elements:
      - text: "Joy to the World"
        x: 2.25
        y: 1.0
        font_size: 32
        alignment: center
        color: "#8B0000"
        font_style: bold
```

### Expected Output

- Gradient sky transitions from light blue to navy
- Subtle striped snow ground
- Christmas tree with gradient fill (dark to light green)
- Circular photo clipped and positioned as tree ornament
- Bold red text at bottom

### Integration Notes

- **Z-index layering**: 0 (sky) → 1 (ground) → 2 (tree) → 3 (ornament)
- **Gradient on SVG**: fill field accepts gradient, not just fill_color
- **Multiple patterns/gradients**: No limit, each shape can have different fills
- **Clipping with layers**: Clipped image renders in correct z-order

---

## Testing Checklist

When integrating new vector graphics features:

### Pre-Generation Validation
- [ ] YAML passes Pydantic validation (no schema errors)
- [ ] SVG path data starts with M/m
- [ ] Gradient stops in ascending order (0.0 to 1.0)
- [ ] Clipping mask coordinates within image bounds
- [ ] Pattern spacing appropriate for print (>= 0.1")

### Visual Verification
- [ ] Preview PDF at 100% zoom (actual size)
- [ ] Check gradient smoothness (no color banding)
- [ ] Verify SVG path shapes match expected design
- [ ] Confirm clipped images show correct content
- [ ] Test pattern repetition (no visible seams)

### Print Testing
- [ ] Print test page on target printer (color laser)
- [ ] Measure dimensions with ruler (verify 0.25" margins)
- [ ] Check gradient color accuracy vs. screen preview
- [ ] Verify pattern elements visible at print resolution
- [ ] Ensure clipping masks have clean edges (no jagged lines)

### Performance
- [ ] Card generation completes within 2x baseline time
- [ ] PDF file size reasonable (< 5MB for typical card)
- [ ] No warnings in console output

---

## Common Integration Patterns

### Pattern 1: Decorative Border

```yaml
# Use SVG paths to create repeating border elements
shapes:
  - type: svg_path  # Top-left corner
    path_data: "..."
    x: 0.25
    y: 5.25
  - type: svg_path  # Top-right corner
    path_data: "..."
    x: 3.75
    y: 5.25
  # ... repeat for all corners
```

### Pattern 2: Gradient Background + Pattern Overlay

```yaml
shapes:
  - type: rectangle  # Base gradient
    fill: {type: linear_gradient, ...}
    z_index: 0
  - type: rectangle  # Pattern overlay (semi-transparent)
    fill: {type: pattern, ...}
    opacity: 0.3
    z_index: 1
```

### Pattern 3: Photo Collage with Mixed Masks

```yaml
images:
  - source_path: "photo1.jpg"
    clip_mask: {type: circle, ...}
  - source_path: "photo2.jpg"
    clip_mask: {type: star, ...}
  - source_path: "photo3.jpg"
    clip_mask: {type: ellipse, ...}
```

---

## Next Steps

1. Implement Pydantic models from data-model.md
2. Extend YAML parsing in `src/holiday_card/core/templates.py`
3. Implement renderers (SVG parser, gradient, pattern, clipping)
4. Create unit tests for each integration scenario
5. Generate visual regression baselines
6. Update user documentation with examples

---

## Support Resources

- **YAML Schema**: See `contracts/yaml-schema.md` for complete field reference
- **Data Model**: See `data-model.md` for entity relationships
- **Research**: See `research.md` for technical implementation details
- **Specification**: See `spec.md` for user stories and requirements

**Questions?** Refer to edge cases in spec.md or open questions in research.md.
