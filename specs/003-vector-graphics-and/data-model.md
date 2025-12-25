# Data Model: Vector Graphics and Decorative Elements

**Feature**: Vector Graphics and Decorative Elements System
**Date**: 2025-12-25
**Status**: Design

## Overview

This document defines the entity models for vector graphics support in the holiday card generator. All entities are implemented as Pydantic models for YAML serialization and validation.

## Entity Relationship Diagram

```
Template
  └─ Panel (1..n)
       ├─ TextElement (0..n)         [existing]
       ├─ ImageElement (0..n)        [existing]
       └─ ShapeElement (0..n)        [NEW]
            ├─ Rectangle
            ├─ Circle
            ├─ Triangle
            ├─ Star
            ├─ Line
            └─ DecorativeElement
                 └─ Shape (1..n)  [composition]

DecorativeElementLibrary
  └─ DecorativeElementDefinition (1..n)
       └─ Shape (1..n)
```

## Core Entities

### ShapeType (Enum)

**Purpose**: Discriminator for shape type polymorphism in Pydantic unions.

**Values**:
- `rectangle` - Four-sided rectangle/square
- `circle` - Circle or ellipse
- `triangle` - Three-sided polygon
- `star` - Multi-pointed star shape
- `line` - Straight line segment

**Usage**: Required field in all shape models for discriminated union parsing.

---

### BaseShape (Abstract Model)

**Purpose**: Common properties shared by all shape types.

**Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `id` | `str` | No | UUID | Unique shape identifier |
| `type` | `ShapeType` | Yes | - | Shape discriminator (rectangle, circle, etc.) |
| `z_index` | `int` | No | 0 | Rendering layer (higher = on top) |
| `fill_color` | `str | None` | No | None | Fill color as hex string (e.g., "#A8B5A0") |
| `stroke_color` | `str | None` | No | None | Stroke color as hex string |
| `stroke_width` | `float` | No | 0.0 | Stroke width in points (0 = no stroke) |
| `opacity` | `float` | No | 1.0 | Opacity 0.0-1.0 (0 = transparent, 1 = opaque) |
| `rotation` | `float` | No | 0.0 | Rotation in degrees (0-360) |

**Validation Rules**:
- `stroke_width` ≥ 0.0
- `opacity` in range [0.0, 1.0]
- `rotation` in range [0.0, 360.0)
- `fill_color` and `stroke_color` must match hex format `#[0-9A-Fa-f]{6}` or be None
- At least one of `fill_color` or `stroke_color` must be set (warn if both None)

**Constraints**:
- Cannot be instantiated directly (use concrete shape types)
- All measurements in inches except `stroke_width` (points)

---

### Rectangle (Shape)

**Purpose**: Rectangular shape with position and dimensions.

**Inherits**: BaseShape

**Additional Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `Literal["rectangle"]` | Yes | "rectangle" | Discriminator |
| `x` | `float` | Yes | - | X position in inches from panel left |
| `y` | `float` | Yes | - | Y position in inches from panel bottom |
| `width` | `float` | Yes | - | Width in inches |
| `height` | `float` | Yes | - | Height in inches |

**Validation Rules**:
- `x` ≥ 0.0
- `y` ≥ 0.0
- `width` > 0.0
- `height` > 0.0

**Rendering Notes**:
- Position (x, y) is bottom-left corner
- Rotation occurs around center point: (x + width/2, y + height/2)
- Respects panel boundaries (clips if extends beyond)

**YAML Example**:
```yaml
type: rectangle
x: 1.0
y: 2.0
width: 3.0
height: 1.5
fill_color: "#A8B5A0"
stroke_color: "#333333"
stroke_width: 2
opacity: 0.8
rotation: 15
z_index: 1
```

---

### Circle (Shape)

**Purpose**: Circular shape with center and radius.

**Inherits**: BaseShape

**Additional Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `Literal["circle"]` | Yes | "circle" | Discriminator |
| `center_x` | `float` | Yes | - | Center X position in inches |
| `center_y` | `float` | Yes | - | Center Y position in inches |
| `radius` | `float` | Yes | - | Radius in inches |

**Validation Rules**:
- `center_x` ≥ 0.0
- `center_y` ≥ 0.0
- `radius` > 0.0

**Rendering Notes**:
- Rotation around center (center_x, center_y)
- For ellipse: Use `width` and `height` instead of `radius` (future enhancement)

**YAML Example**:
```yaml
type: circle
center_x: 4.0
center_y: 5.0
radius: 0.5
fill_color: "#B85C50"
opacity: 0.9
z_index: 2
```

---

### Triangle (Shape)

**Purpose**: Three-sided polygon defined by three vertices.

**Inherits**: BaseShape

**Additional Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `Literal["triangle"]` | Yes | "triangle" | Discriminator |
| `x1` | `float` | Yes | - | Vertex 1 X position in inches |
| `y1` | `float` | Yes | - | Vertex 1 Y position in inches |
| `x2` | `float` | Yes | - | Vertex 2 X position in inches |
| `y2` | `float` | Yes | - | Vertex 2 Y position in inches |
| `x3` | `float` | Yes | - | Vertex 3 X position in inches |
| `y3` | `float` | Yes | - | Vertex 3 Y position in inches |

**Validation Rules**:
- All coordinates ≥ 0.0
- Vertices must not be collinear (warn if area ≈ 0)

**Rendering Notes**:
- Rotation around geometric center: ((x1+x2+x3)/3, (y1+y2+y3)/3)
- Rendered as closed polygon path

**YAML Example**:
```yaml
type: triangle
x1: 2.0
y1: 3.0
x2: 3.0
y2: 3.0
x3: 2.5
y3: 4.0
fill_color: "#D4AF37"
rotation: 10
z_index: 3
```

---

### Star (Shape)

**Purpose**: Multi-pointed star shape with configurable points.

**Inherits**: BaseShape

**Additional Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `Literal["star"]` | Yes | "star" | Discriminator |
| `center_x` | `float` | Yes | - | Center X position in inches |
| `center_y` | `float` | Yes | - | Center Y position in inches |
| `outer_radius` | `float` | Yes | - | Outer point radius in inches |
| `inner_radius` | `float` | Yes | - | Inner point radius in inches |
| `points` | `int` | No | 5 | Number of star points |

**Validation Rules**:
- `center_x` ≥ 0.0
- `center_y` ≥ 0.0
- `outer_radius` > 0.0
- `inner_radius` > 0.0
- `inner_radius` < `outer_radius` (inner must be smaller)
- `points` in range [3, 20]

**Rendering Notes**:
- First point starts at top (270 degrees)
- Alternates between outer and inner radius
- Rotation around center (center_x, center_y)
- Total vertices = points * 2

**YAML Example**:
```yaml
type: star
center_x: 4.25
center_y: 7.5
outer_radius: 0.4
inner_radius: 0.2
points: 5
fill_color: "#FFD700"
z_index: 10
```

---

### Line (Shape)

**Purpose**: Straight line segment between two points.

**Inherits**: BaseShape

**Additional Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `type` | `Literal["line"]` | Yes | "line" | Discriminator |
| `start_x` | `float` | Yes | - | Start X position in inches |
| `start_y` | `float` | Yes | - | Start Y position in inches |
| `end_x` | `float` | Yes | - | End X position in inches |
| `end_y` | `float` | Yes | - | End Y position in inches |

**Validation Rules**:
- All coordinates ≥ 0.0
- Start and end must differ (warn if length ≈ 0)

**Rendering Notes**:
- Lines ignore `fill_color` (lines have no fill)
- `stroke_color` and `stroke_width` are required (default stroke if not set)
- Rotation around midpoint: ((start_x+end_x)/2, (start_y+end_y)/2)

**YAML Example**:
```yaml
type: line
start_x: 1.0
start_y: 2.0
end_x: 4.0
end_y: 2.0
stroke_color: "#000000"
stroke_width: 3
z_index: 0
```

---

### DecorativeElement (Composite Shape)

**Purpose**: Reusable composition of multiple shapes forming a cohesive design unit (e.g., Christmas tree, ornament).

**Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `id` | `str` | No | UUID | Unique element identifier |
| `name` | `str` | Yes | - | Decorative element name (e.g., "geometric_tree") |
| `x` | `float` | Yes | - | Position X in inches (placement anchor) |
| `y` | `float` | Yes | - | Position Y in inches (placement anchor) |
| `scale` | `float` | No | 1.0 | Proportional scale multiplier |
| `rotation` | `float` | No | 0.0 | Rotation in degrees (rotates entire composition) |
| `color_palette` | `dict[str, str] | None` | No | None | Color role overrides (role → hex color) |
| `shapes` | `list[Shape]` | Yes | - | Internal shape composition |

**Validation Rules**:
- `x` ≥ 0.0
- `y` ≥ 0.0
- `scale` > 0.0
- `rotation` in range [0.0, 360.0)
- `shapes` must contain at least 1 shape
- `shapes` cannot contain other DecorativeElements (no nesting)
- `color_palette` keys must match color roles used in shapes

**Rendering Notes**:
- All internal shapes use relative coordinates (0, 0) = element anchor (x, y)
- Scale applies to all shape dimensions and positions
- Rotation rotates entire composition around anchor (x, y)
- Color palette substitutes `{role}` placeholders in shape fill/stroke colors

**Color Palette**:
- Shape colors can use template syntax: `fill_color: "{tree_primary}"`
- At render time, `{tree_primary}` is replaced with value from `color_palette`
- If `color_palette` is None, uses default colors from decorative element definition
- Missing roles in palette use definition defaults (no error)

**YAML Example (Instance)**:
```yaml
type: decorative_element
name: geometric_tree
x: 4.25
y: 3.0
scale: 1.2
rotation: 0
color_palette:
  tree_primary: "#A8B5A0"
  tree_accent: "#B85C50"
  ornament: "#D4AF37"
  star: "#FFD700"
```

---

### DecorativeElementDefinition (Library Entry)

**Purpose**: Template definition for reusable decorative elements stored in library.

**Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `name` | `str` | Yes | - | Unique identifier (e.g., "geometric_tree") |
| `description` | `str` | No | None | Human-readable description |
| `default_width` | `float` | Yes | - | Default width in inches (for scale reference) |
| `default_height` | `float` | Yes | - | Default height in inches |
| `color_roles` | `dict[str, str]` | Yes | - | Default color palette (role → hex color) |
| `shapes` | `list[Shape]` | Yes | - | Internal shape composition (relative coords) |

**Validation Rules**:
- `name` must be unique in library
- `default_width` > 0.0
- `default_height` > 0.0
- `shapes` must contain at least 1 shape
- All shape colors must use `{role}` syntax referencing `color_roles` keys

**Storage**:
- YAML files in `decorative_elements/` directory
- Organized by occasion: `christmas/`, `hanukkah/`, `generic/`, etc.
- Filename convention: `{name}.yaml`

**YAML Example (Definition)**:
```yaml
name: geometric_tree
description: "Geometric Christmas tree with overlapping triangles"
default_width: 3.0
default_height: 4.0

color_roles:
  tree_primary: "#A8B5A0"
  tree_accent: "#B85C50"
  ornament: "#D4AF37"
  star: "#FFD700"

shapes:
  - type: triangle
    x1: 0.0
    y1: 0.0
    x2: 3.0
    y2: 0.0
    x3: 1.5
    y3: 1.5
    fill_color: "{tree_primary}"
    z_index: 1

  - type: triangle
    x1: 0.5
    y1: 1.0
    x2: 2.5
    y2: 1.0
    x3: 1.5
    y3: 2.5
    fill_color: "{tree_accent}"
    opacity: 0.9
    z_index: 2

  - type: star
    center_x: 1.5
    center_y: 3.8
    outer_radius: 0.3
    inner_radius: 0.15
    points: 5
    fill_color: "{star}"
    z_index: 10
```

---

### ShapeElement (Union Type)

**Purpose**: Polymorphic union type for all renderable shapes in a panel.

**Definition**:
```python
ShapeElement = Annotated[
    Rectangle | Circle | Triangle | Star | Line | DecorativeElement,
    Field(discriminator='type')
]
```

**Usage**: `Panel.shape_elements: list[ShapeElement]`

**Rendering Order**: All ShapeElements are sorted by z_index before rendering, allowing interleaved shapes, text, and images.

---

## Extended Entities

### Panel (Extended)

**Purpose**: Card panel extended to support vector graphics.

**New Properties**:

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `shape_elements` | `list[ShapeElement]` | No | [] | Vector shapes and decorative elements |

**Rendering Order**:
1. Collect all renderable elements: shape_elements + text_elements + image_elements
2. Each element type can have z_index (shapes have it, text/images may need extension)
3. Sort all elements by z_index (lowest first)
4. Render in sorted order (lowest z_index appears at bottom)

**Backward Compatibility**:
- `shape_elements` defaults to empty list
- Existing templates without shape_elements work unchanged
- If no z_index on text/images, they render after shapes (z_index = infinity)

---

### Template (Extended)

**Purpose**: Card template extended to include default vector graphics.

**Changes**: No direct changes needed. Templates define Panels, which now support `shape_elements`.

**Example**:
```yaml
id: geometric-christmas
name: "Geometric Christmas Tree"
occasion: christmas
fold_type: half_fold

panels:
  - position: front
    x: 0.0
    y: 5.5
    width: 8.5
    height: 5.5
    background_color: "#F5F5DC"  # Cream

    shape_elements:
      - type: decorative_element
        name: geometric_tree
        x: 4.25
        y: 2.75
        scale: 1.0

    text_elements:
      - content: "Season's Greetings"
        x: 4.25
        y: 0.5
        font_size: 24
        alignment: center
        z_index: 100  # Above all shapes
```

---

## Relationships

### Panel → ShapeElement (1 to many)
- Panel contains 0 or more ShapeElements
- ShapeElements are positioned relative to panel coordinates
- ShapeElements respect panel boundaries (clipping)

### DecorativeElement → Shape (1 to many)
- DecorativeElement composes 1 or more basic Shapes
- Shapes use relative coordinates within decorative element
- Shapes inherit scale and rotation from parent DecorativeElement

### DecorativeElement → DecorativeElementDefinition (instance to template)
- DecorativeElement instances reference definitions by `name`
- Definitions loaded from decorative element library on startup
- Missing definition causes validation error

---

## Measurement Units

| Measurement | Unit | Notes |
|-------------|------|-------|
| Position (x, y, center_x, center_y) | Inches | Primary unit per constitution |
| Dimensions (width, height, radius) | Inches | Consistent with positions |
| Stroke width | Points | ReportLab convention (72 pts/inch) |
| Rotation | Degrees | 0-360, counter-clockwise |
| Opacity | Float | 0.0-1.0 (0 = transparent, 1 = opaque) |

**Conversion**: Renderer converts inches to PDF points (× 72) at render time.

---

## Validation Rules Summary

### Cross-Field Validation
- Star: `inner_radius` < `outer_radius`
- Shape: At least one of `fill_color` or `stroke_color` must be set
- Triangle: Vertices not collinear (area > 0)
- Line: Start ≠ End (length > 0)

### Boundary Validation
- All positions ≥ 0.0 (no negative coordinates)
- All dimensions > 0.0 (positive sizes)
- Shapes should stay within panel safe margins (warn if outside)

### Type Validation
- Discriminated union uses `type` field for polymorphism
- Hex colors match `#[0-9A-Fa-f]{6}` pattern
- Z-index is integer (can be negative)

---

## Future Extensions (Out of Scope)

### Gradient (Not Implemented)
```yaml
fill_gradient:
  type: linear
  start_color: "#FF0000"
  end_color: "#0000FF"
  angle: 45
```

### Pattern Fill (Not Implemented)
```yaml
fill_pattern:
  type: dots
  spacing: 0.1
  color: "#000000"
```

### Curved Path (Not Implemented)
```yaml
type: bezier_path
points:
  - {x: 1, y: 1, control1_x: 2, control1_y: 2}
```

---

## Implementation Notes

### Pydantic Models

All entities implemented as Pydantic `BaseModel` subclasses for:
- YAML serialization/deserialization
- Automatic validation
- Type safety
- JSON schema generation

### Discriminated Unions

Shape polymorphism uses Pydantic's discriminated union feature:
```python
Shape = Annotated[
    Rectangle | Circle | Triangle | Star | Line,
    Field(discriminator='type')
]
```

This enables type-safe parsing from YAML based on the `type` field.

### Color Palette Resolution

Decorative elements use lazy resolution:
1. Load definition from library (with `{role}` placeholders)
2. At instantiation, substitute `color_palette` values
3. Fallback to definition defaults for missing roles
4. Validate all colors are valid hex after substitution
