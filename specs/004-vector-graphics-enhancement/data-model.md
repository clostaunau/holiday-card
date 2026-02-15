# Data Model: Vector Graphics Enhancement

**Feature**: 004-vector-graphics-enhancement
**Date**: 2025-12-25

## Overview

This document defines all data entities (Pydantic models) for SVG paths, gradients, patterns, and clipping masks. Models extend the existing `BaseShape` hierarchy and integrate with the YAML template system.

---

## Entity Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        BaseShape                             │
│  - id: str                                                   │
│  - type: ShapeType (discriminator)                           │
│  - z_index: int                                              │
│  - fill_color: Optional[str] OR fill: Optional[FillStyle]   │
│  - stroke_color: Optional[str]                               │
│  - stroke_width: float                                       │
│  - opacity: float                                            │
│  - rotation: float                                           │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
      ┌───────────────────────┴───────────────────────┐
      │                                               │
┌─────────────────┐                            ┌─────────────────┐
│  SVGPath        │                            │  Existing Shapes │
│  - path_data    │                            │  - Rectangle    │
│  - scale        │                            │  - Circle       │
└─────────────────┘                            │  - Triangle     │
                                               │  - Star         │
                                               │  - Line         │
                                               └─────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        FillStyle                             │
│  (Discriminated Union - type field)                          │
├─────────────────────────────────────────────────────────────┤
│  - SolidFill (type: solid, color: str)                      │
│  - LinearGradientFill (type: linear_gradient, ...)          │
│  - RadialGradientFill (type: radial_gradient, ...)          │
│  - PatternFill (type: pattern, ...)                         │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
                              │ uses
                              │
┌─────────────────────────────────────────────────────────────┐
│                       ColorStop                              │
│  - position: float (0.0-1.0)                                │
│  - color: str (#RRGGBB)                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      ImageElement                            │
│  - source_path: str                                          │
│  - x, y, width, height: float                               │
│  - clip_mask: Optional[ClipMask]  ← NEW                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ has-one
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        ClipMask                              │
│  (Discriminated Union - type field)                          │
├─────────────────────────────────────────────────────────────┤
│  - CircleClipMask (type: circle, center_x, center_y, r)    │
│  - RectangleClipMask (type: rectangle, x, y, w, h)         │
│  - EllipseClipMask (type: ellipse, cx, cy, rx, ry)         │
│  - StarClipMask (type: star, cx, cy, outer_r, inner_r, pts)│
│  - SVGPathClipMask (type: svg_path, path_data)             │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Entities

### 1. SVGPath

**Purpose**: Represents a vector shape defined by SVG path data string.

**Fields**:
```python
class SVGPath(BaseShape):
    """Vector shape defined by SVG path commands.

    Supports basic SVG path commands: M/m, L/l, H/h, V/v, C/c, S/s, Q/q, T/t, A/a, Z/z.
    Unsupported commands are logged as warnings and skipped during rendering.
    """

    type: Literal[ShapeType.SVG_PATH] = ShapeType.SVG_PATH
    path_data: str = Field(
        min_length=1,
        max_length=10000,
        description="SVG path data string (e.g., 'M 10 10 L 20 20 Z')"
    )
    scale: float = Field(
        default=1.0,
        gt=0.0,
        le=10.0,
        description="Scale multiplier applied to all path coordinates"
    )

    @field_validator("path_data")
    @classmethod
    def validate_path_syntax(cls, v: str) -> str:
        """Basic validation: ensure path starts with M/m command."""
        trimmed = v.strip()
        if not (trimmed.startswith('M') or trimmed.startswith('m')):
            raise ValueError("SVG path must start with M (moveTo) command")
        return trimmed
```

**Relationships**:
- Inherits from `BaseShape` (fill, stroke, opacity, rotation, z_index)
- Can use `fill` field with FillStyle union (solid, gradient, pattern)

**Validation Rules**:
- Path data must start with M/m (moveTo)
- Path data length: 1-10,000 characters (prevent malicious input)
- Scale: 0.0 < scale <= 10.0
- All BaseShape validations apply (opacity 0-1, rotation 0-360)

**Path Length Rationale**:
- **SVGPath max_length=10000**: Decorative elements (holly leaves, snowflakes, ornate wreaths) often contain complex Bezier curves, multiple sub-paths, and fine detail requiring longer path definitions. Commercial SVG decorations can easily exceed 5,000 characters when unminified.
- **SVGPathClipMask max_length=5000**: Clipping masks should define simple, closed boundaries for performance. Complex clipping paths significantly impact rendering performance, so the stricter limit encourages simpler mask shapes. Users can achieve complex clipping effects using compound basic shapes (circle + star) rather than elaborate SVG paths.

**State Transitions**: N/A (immutable once created)

---

### 2. ColorStop

**Purpose**: Defines a color at a specific position within a gradient.

**Fields**:
```python
class ColorStop(BaseModel):
    """Color at a specific position in a gradient (0.0 = start, 1.0 = end)."""

    position: float = Field(
        ge=0.0,
        le=1.0,
        description="Position in gradient (0.0-1.0)"
    )
    color: str = Field(
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Color as hex string (#RRGGBB)"
    )

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Ensure valid hex color format."""
        if not v.startswith('#'):
            v = f"#{v}"
        if len(v) != 7:
            raise ValueError(f"Hex color must be 6 digits: {v}")
        return v.upper()
```

**Relationships**:
- Used by LinearGradientFill and RadialGradientFill (composition)
- No parent relationship (value object)

**Validation Rules**:
- Position: 0.0 <= position <= 1.0
- Color: Valid hex format #RRGGBB (case-insensitive, auto-uppercase)

---

### 3. FillStyle (Discriminated Union)

**Purpose**: Represents different fill types: solid color, linear gradient, radial gradient, or pattern.

#### 3a. SolidFill

```python
class SolidFill(BaseModel):
    """Solid color fill."""

    type: Literal["solid"] = "solid"
    color: str = Field(
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Fill color (#RRGGBB)"
    )
```

#### 3b. LinearGradientFill

```python
class LinearGradientFill(BaseModel):
    """Linear gradient fill with angle and color stops."""

    type: Literal["linear_gradient"] = "linear_gradient"
    angle: float = Field(
        ge=0.0,
        lt=360.0,
        description="Gradient angle in degrees (0=left-to-right, 90=bottom-to-top)"
    )
    stops: list[ColorStop] = Field(
        min_length=2,
        max_length=20,
        description="Color stops (minimum 2, maximum 20)"
    )

    @field_validator("stops")
    @classmethod
    def validate_stops_ascending(cls, v: list[ColorStop]) -> list[ColorStop]:
        """Ensure color stops are in ascending position order."""
        positions = [stop.position for stop in v]
        if positions != sorted(positions):
            raise ValueError("Color stop positions must be in ascending order")
        return v
```

#### 3c. RadialGradientFill

```python
class RadialGradientFill(BaseModel):
    """Radial gradient fill radiating from center point."""

    type: Literal["radial_gradient"] = "radial_gradient"
    center_x: float = Field(
        ge=0.0,
        description="Gradient center X in inches (relative to shape)"
    )
    center_y: float = Field(
        ge=0.0,
        description="Gradient center Y in inches (relative to shape)"
    )
    radius: float = Field(
        gt=0.0,
        description="Gradient radius in inches"
    )
    stops: list[ColorStop] = Field(
        min_length=2,
        max_length=20,
        description="Color stops (minimum 2, maximum 20)"
    )

    @field_validator("stops")
    @classmethod
    def validate_stops_ascending(cls, v: list[ColorStop]) -> list[ColorStop]:
        """Ensure color stops are in ascending position order."""
        positions = [stop.position for stop in v]
        if positions != sorted(positions):
            raise ValueError("Color stop positions must be in ascending order")
        return v
```

#### 3d. PatternFill

```python
class PatternType(str, Enum):
    """Built-in pattern types."""
    STRIPES = "stripes"
    DOTS = "dots"
    GRID = "grid"
    CHECKERBOARD = "checkerboard"


class PatternFill(BaseModel):
    """Repeating geometric pattern fill."""

    type: Literal["pattern"] = "pattern"
    pattern_type: PatternType = Field(
        description="Built-in pattern type"
    )
    spacing: float = Field(
        gt=0.0,
        le=2.0,
        description="Pattern element spacing in inches"
    )
    angle: float = Field(
        default=0.0,
        ge=0.0,
        lt=360.0,
        description="Pattern rotation in degrees"
    )
    scale: float = Field(
        default=1.0,
        gt=0.0,
        le=5.0,
        description="Pattern scale multiplier"
    )
    colors: list[str] = Field(
        min_length=1,
        max_length=2,
        description="Pattern colors (1 for single-color, 2 for alternating)"
    )

    @field_validator("colors")
    @classmethod
    def validate_hex_colors(cls, v: list[str]) -> list[str]:
        """Ensure all colors are valid hex format."""
        validated = []
        for color in v:
            if not color.startswith('#'):
                color = f"#{color}"
            if len(color) != 7:
                raise ValueError(f"Hex color must be 6 digits: {color}")
            validated.append(color.upper())
        return validated
```

#### FillStyle Union

```python
FillStyle = Annotated[
    Union[SolidFill, LinearGradientFill, RadialGradientFill, PatternFill],
    Field(discriminator="type")
]
```

**Relationships**:
- Used by BaseShape.fill field (composition)
- ColorStop used by gradient fills (composition)

**Validation Rules**:
- Discriminator field `type` determines concrete type
- Each concrete type has specific field validations
- Gradient stops must be 2-20, in ascending order
- Pattern colors must be 1-2 valid hex strings

---

### 4. ClipMask (Discriminated Union)

**Purpose**: Defines a shape boundary for clipping images.

#### 4a. CircleClipMask

```python
class CircleClipMask(BaseModel):
    """Circular clipping mask."""

    type: Literal["circle"] = "circle"
    center_x: float = Field(
        ge=0.0,
        description="Circle center X in inches (relative to image)"
    )
    center_y: float = Field(
        ge=0.0,
        description="Circle center Y in inches (relative to image)"
    )
    radius: float = Field(
        gt=0.0,
        description="Circle radius in inches"
    )
```

#### 4b. RectangleClipMask

```python
class RectangleClipMask(BaseModel):
    """Rectangular clipping mask."""

    type: Literal["rectangle"] = "rectangle"
    x: float = Field(
        ge=0.0,
        description="Rectangle X position in inches (relative to image)"
    )
    y: float = Field(
        ge=0.0,
        description="Rectangle Y position in inches (relative to image)"
    )
    width: float = Field(
        gt=0.0,
        description="Rectangle width in inches"
    )
    height: float = Field(
        gt=0.0,
        description="Rectangle height in inches"
    )
```

#### 4c. EllipseClipMask

```python
class EllipseClipMask(BaseModel):
    """Elliptical clipping mask."""

    type: Literal["ellipse"] = "ellipse"
    center_x: float = Field(
        ge=0.0,
        description="Ellipse center X in inches"
    )
    center_y: float = Field(
        ge=0.0,
        description="Ellipse center Y in inches"
    )
    radius_x: float = Field(
        gt=0.0,
        description="Horizontal radius in inches"
    )
    radius_y: float = Field(
        gt=0.0,
        description="Vertical radius in inches"
    )
```

#### 4d. StarClipMask

```python
class StarClipMask(BaseModel):
    """Star-shaped clipping mask."""

    type: Literal["star"] = "star"
    center_x: float = Field(ge=0.0, description="Star center X in inches")
    center_y: float = Field(ge=0.0, description="Star center Y in inches")
    outer_radius: float = Field(gt=0.0, description="Outer point radius in inches")
    inner_radius: float = Field(gt=0.0, description="Inner point radius in inches")
    points: int = Field(
        default=5,
        ge=3,
        le=20,
        description="Number of star points"
    )

    @field_validator("inner_radius")
    @classmethod
    def validate_inner_smaller(cls, v: float, info) -> float:
        """Ensure inner radius < outer radius."""
        if "outer_radius" in info.data and v >= info.data["outer_radius"]:
            raise ValueError(f"inner_radius must be less than outer_radius")
        return v
```

#### 4e. SVGPathClipMask

```python
class SVGPathClipMask(BaseModel):
    """Arbitrary path-based clipping mask."""

    type: Literal["svg_path"] = "svg_path"
    path_data: str = Field(
        min_length=1,
        max_length=5000,
        description="SVG path data defining mask boundary"
    )
    scale: float = Field(
        default=1.0,
        gt=0.0,
        le=10.0,
        description="Scale multiplier for path coordinates"
    )

    @field_validator("path_data")
    @classmethod
    def validate_path_syntax(cls, v: str) -> str:
        """Ensure path starts with M/m and ends with Z/z (closed path)."""
        trimmed = v.strip()
        if not (trimmed.startswith('M') or trimmed.startswith('m')):
            raise ValueError("Clipping path must start with M command")
        if not (trimmed.endswith('Z') or trimmed.endswith('z')):
            raise ValueError("Clipping path must be closed (end with Z)")
        return trimmed
```

#### ClipMask Union

```python
ClipMask = Annotated[
    Union[CircleClipMask, RectangleClipMask, EllipseClipMask, StarClipMask, SVGPathClipMask],
    Field(discriminator="type")
]
```

**Relationships**:
- Used by ImageElement.clip_mask field (composition)
- SVGPathClipMask reuses SVG path validation logic

**Validation Rules**:
- Discriminator field `type` determines concrete type
- All measurements in inches, positive values
- SVGPathClipMask must be closed path (ends with Z/z)
- Star inner_radius < outer_radius

---

## Modified Entities

### BaseShape (Extended)

**Changes**:
```python
class BaseShape(BaseModel):
    """Base model for all vector graphics shapes."""

    # ... existing fields ...

    # MODIFIED: fill_color deprecated in favor of fill (backward compatible)
    fill_color: Optional[str] = Field(
        default=None,
        deprecated=True,
        description="Legacy solid fill color. Use 'fill' instead."
    )
    fill: Optional[FillStyle] = Field(
        default=None,
        description="Fill style: solid, gradient, or pattern"
    )

    @field_validator("fill")
    @classmethod
    def ensure_fill_or_fill_color(cls, v, info):
        """Ensure only one of fill or fill_color is set."""
        if v is not None and info.data.get("fill_color") is not None:
            raise ValueError("Cannot specify both 'fill' and 'fill_color'")
        return v
```

**Migration Strategy**:
- Existing templates use `fill_color: "#RRGGBB"` → still works (backward compatible)
- New templates use `fill: {type: solid, color: "#RRGGBB"}` for explicit solid fills
- New templates use `fill: {type: linear_gradient, ...}` for gradients
- Parser converts legacy `fill_color` to `fill: {type: solid, color: ...}` internally

---

### ImageElement (Extended)

**Changes**:
```python
class ImageElement(BaseModel):
    """Image content with positioning, scaling, and optional clipping mask."""

    # ... existing fields (source_path, x, y, width, height, etc.) ...

    # NEW FIELD
    clip_mask: Optional[ClipMask] = Field(
        default=None,
        description="Optional clipping mask to crop image to shape"
    )
```

**Migration Strategy**:
- Existing templates without clip_mask → render normally (no clipping)
- New templates with clip_mask → apply clipping path during render

---

## Enums

### ShapeType (Extended)

```python
class ShapeType(str, Enum):
    """Vector shape types for discriminated union."""

    # Existing
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    TRIANGLE = "triangle"
    STAR = "star"
    LINE = "line"
    DECORATIVE_ELEMENT = "decorative_element"

    # NEW
    SVG_PATH = "svg_path"
```

---

## Entity Lifecycle

### SVGPath Lifecycle
1. **Creation**: Loaded from YAML template during template parsing
2. **Validation**: Pydantic validates path_data syntax, scale range
3. **Rendering**: SVG parser converts path_data to ReportLab Path object
4. **Completion**: Drawn to PDF canvas with fill/stroke styling

### Gradient Lifecycle
1. **Creation**: Loaded from YAML as part of shape's `fill` field
2. **Validation**: Pydantic validates stops count, positions, colors
3. **Rendering**: Gradient renderer converts stops to ReportLab gradient
4. **Application**: Gradient applied to shape fill region
5. **Completion**: Shape drawn with gradient fill

### ClipMask Lifecycle
1. **Creation**: Loaded from YAML as part of ImageElement
2. **Validation**: Pydantic validates mask type and dimensions
3. **Rendering**: Clipping renderer converts mask to ReportLab clipPath
4. **Application**: clipPath applied before image draw
5. **Restoration**: Canvas state restored after image (removes clip)
6. **Completion**: Image visible only within mask boundary

### Pattern Lifecycle
1. **Creation**: Loaded from YAML as part of shape's `fill` field
2. **Validation**: Pydantic validates pattern type, spacing, colors
3. **Form Creation**: Pattern renderer creates Form XObject (tile)
4. **Application**: Form referenced as fill pattern
5. **Tiling**: PDF renderer tiles pattern across shape
6. **Completion**: Shape filled with repeating pattern

---

## Data Relationships Summary

```
Panel
  └── shapes: list[Shape]
        ├── Rectangle (can use FillStyle)
        ├── Circle (can use FillStyle)
        ├── SVGPath (can use FillStyle) ← NEW
        └── ... other shapes
  └── images: list[ImageElement]
        └── clip_mask: Optional[ClipMask] ← NEW

FillStyle (union)
  ├── SolidFill
  ├── LinearGradientFill
  │     └── stops: list[ColorStop]
  ├── RadialGradientFill
  │     └── stops: list[ColorStop]
  └── PatternFill

ClipMask (union)
  ├── CircleClipMask
  ├── RectangleClipMask
  ├── EllipseClipMask
  ├── StarClipMask
  └── SVGPathClipMask
```

---

## Validation Summary

| Entity | Validators | Constraints |
|--------|-----------|-------------|
| SVGPath | path_data syntax, scale range | Starts with M/m, 1-10000 chars, scale 0-10 |
| ColorStop | position range, hex color format | 0.0-1.0, #RRGGBB |
| LinearGradientFill | stops count, ascending positions | 2-20 stops, sorted by position |
| RadialGradientFill | stops count, ascending positions | 2-20 stops, sorted by position |
| PatternFill | colors format, spacing/scale range | 1-2 colors, spacing 0-2", scale 0-5 |
| CircleClipMask | radius positive | radius > 0 |
| RectangleClipMask | dimensions positive | width, height > 0 |
| StarClipMask | inner < outer, points range | 3-20 points, inner < outer |
| SVGPathClipMask | closed path (ends with Z) | Starts M/m, ends Z/z, 1-5000 chars |

---

## Next Steps

1. Implement Pydantic models in `src/holiday_card/core/models.py`
2. Create YAML schema documentation (contracts/yaml-schema.md)
3. Generate quickstart examples (quickstart.md)
