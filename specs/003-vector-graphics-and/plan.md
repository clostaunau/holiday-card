# Implementation Plan: Vector Graphics and Decorative Elements System

**Branch**: `003-vector-graphics-and-decorative-elements` | **Date**: 2025-12-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/workspaces/holiday-card/specs/003-vector-graphics-and/spec.md`

## Summary

Extend the holiday card generator with vector graphics capabilities, enabling sophisticated geometric designs through basic shape primitives (rectangle, circle, triangle, star, line) and pre-built decorative elements (Christmas trees, ornaments, gift boxes). Shapes support z-index layering, styling properties (fill, stroke, opacity, rotation), and configuration via YAML templates. This enables creation of professional designs like the geometric Christmas tree card with overlapping triangles and ornamental decorations.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ReportLab 4.0+ (drawing primitives), Pillow 10.0+, Typer 0.9+, PyYAML 6.0+, Pydantic 2.0+
**Storage**: Local filesystem (YAML templates with shape_elements, decorative element definitions)
**Testing**: pytest 7.0+, pytest-cov, pdf2image + imagehash for visual regression of shape rendering
**Target Platform**: Cross-platform (Linux, macOS, Windows)
**Project Type**: Extension to existing CLI application
**Performance Goals**: Card generation with 50+ shapes under 10 seconds
**Constraints**: Print accuracy (1mm tolerance), safe margins (0.25"), backward compatibility with existing templates
**Scale/Scope**: 5 shape primitives, 10+ decorative elements, unlimited shapes per card

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verified against `.specify/memory/constitution.md` v1.0.0:

- [x] **I. Library-First Architecture**: Shape models in `core/models.py`, rendering in `renderers/`, decorative elements in `core/decorative.py`, no CLI dependencies
- [x] **II. CLI-First Interface**: All shape/element features accessible via existing `holiday-card generate` command with YAML templates
- [x] **III. Configuration-Driven**: Shapes and decorative elements defined in YAML templates, decorative element library in `decorative_elements/*.yaml`
- [x] **IV. Print Accuracy**: Shapes use inches as primary unit, z-index ensures predictable layering, measurements within 1mm tolerance
- [x] **V. Simplicity**: No new runtime dependencies (uses existing ReportLab), filesystem-based decorative element library, minimal abstractions
- [x] **VI. Visual Testing**: Visual regression tests for each shape type, decorative element, and geometric tree composition

## Project Structure

### Documentation (this feature)

```text
specs/003-vector-graphics-and-decorative-elements/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # ReportLab drawing API research
├── data-model.md        # Shape and DecorativeElement entity definitions
├── quickstart.md        # Shape usage examples
├── contracts/           # Interface contracts
│   └── shape-yaml-schema.md  # YAML schema for shapes
└── tasks.md             # Implementation tasks (created by /speckit.tasks)
```

### Source Code Extensions

```text
src/holiday_card/
├── core/
│   ├── models.py                 # EXTENDED: Add Shape models, ShapeElement union
│   ├── decorative.py             # NEW: DecorativeElement model and library loader
│   └── shape_factory.py          # NEW: Factory for creating shapes from YAML
├── renderers/
│   ├── reportlab_renderer.py     # EXTENDED: Add shape rendering methods
│   └── shape_renderer.py         # NEW: Dedicated shape rendering logic
└── utils/
    └── shape_validators.py       # NEW: Shape-specific validation

decorative_elements/              # NEW: Pre-built decorative element library
├── christmas/
│   ├── geometric_tree.yaml
│   ├── traditional_tree.yaml
│   ├── ornament_bauble.yaml
│   └── ornament_star.yaml
├── generic/
│   ├── gift_box.yaml
│   ├── star_topper.yaml
│   └── wreath.yaml
└── hanukkah/
    ├── menorah.yaml
    └── dreidel.yaml

templates/                        # EXTENDED: Add shape_elements to existing
├── christmas/
│   ├── geometric.yaml            # NEW: Demonstrates shape capabilities
│   └── classic.yaml              # UNCHANGED
└── ...
```

### Test Additions

```text
tests/
├── unit/
│   ├── test_shape_models.py     # NEW: Shape model validation
│   ├── test_decorative.py       # NEW: Decorative element loading
│   └── test_shape_factory.py    # NEW: YAML to shape conversion
├── integration/
│   ├── test_shape_rendering.py  # NEW: End-to-end shape rendering
│   └── test_decorative_rendering.py  # NEW: Decorative element rendering
└── visual/
    ├── fixtures/
    │   └── reference_cards/
    │       ├── shapes_basic.pdf         # NEW: All 5 basic shapes
    │       ├── shapes_layering.pdf      # NEW: Z-index demonstration
    │       ├── shapes_styling.pdf       # NEW: Opacity, rotation, stroke
    │       ├── decorative_all.pdf       # NEW: All decorative elements
    │       └── geometric_tree_card.pdf  # NEW: Full geometric Christmas tree
    └── test_visual_regression.py  # EXTENDED: Add shape tests
```

## Architecture

### Phase 0: Research & Validation

**Research Topics**:

1. **ReportLab Drawing Primitives** (`research.md`)
   - Survey available drawing methods: `rect()`, `circle()`, `wedge()`, `polygon()`, `line()`
   - Investigate opacity/transparency support: `setFillAlpha()`, `setStrokeAlpha()`
   - Rotation mechanisms: `rotate()` with save/restore state
   - Z-index simulation: Manual ordering of drawing calls (draw lowest z-index first)
   - Performance characteristics: How many shapes before slowdown?

2. **Shape Geometry Calculations**
   - Triangle vertex calculation from center + size
   - Star point calculation (outer/inner radius, n-points)
   - Rotation matrix for arbitrary rotation around center
   - Bounding box calculation for rotated shapes

3. **YAML Schema Design**
   - Union type handling in Pydantic (discriminated union for shape types)
   - Nested composition structure for decorative elements
   - Backward compatibility with existing Panel/Template schemas

**Validation Activities**:
- [ ] Create ReportLab prototype: Render all 5 shape types with opacity and rotation
- [ ] Verify z-index ordering: Draw 10 overlapping shapes in specified order
- [ ] Test transparency blending: Render 3 semi-transparent overlapping circles
- [ ] Measure performance: Generate card with 100+ shapes, verify <10s
- [ ] Validate YAML parsing: Load shape_elements with Pydantic discriminated union

**Risks & Mitigations**:

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| ReportLab doesn't support alpha transparency | HIGH | LOW | Research shows `setFillAlpha()` exists; verify in prototype |
| Z-index with 100+ shapes causes performance issues | MEDIUM | MEDIUM | Profile rendering; consider spatial indexing if needed |
| Pydantic discriminated unions complex with YAML | MEDIUM | LOW | Use `type` discriminator field; validate in prototype |
| Rotation around center requires complex matrix math | LOW | LOW | Use ReportLab's built-in rotate() with save/restore |
| Decorative element compositions create circular refs | MEDIUM | LOW | Validate during loading; decorative elements only use basic shapes |

### Phase 1: Detailed Design

**Core Models** (`data-model.md`):

```python
# Existing: Color, Panel, Template, etc.

class ShapeType(str, Enum):
    """Discriminator for shape variants."""
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    TRIANGLE = "triangle"
    STAR = "star"
    LINE = "line"

class BaseShape(BaseModel):
    """Common properties for all shapes."""
    id: str = Field(default_factory=uuid4)
    type: ShapeType  # Discriminator field
    z_index: int = Field(default=0)
    fill_color: Optional[str] = None  # Hex color or None for no fill
    stroke_color: Optional[str] = None  # Hex color or None for no stroke
    stroke_width: float = Field(default=0.0, ge=0.0)  # Points
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    rotation: float = Field(default=0.0, ge=0.0, lt=360.0)  # Degrees

class Rectangle(BaseShape):
    """Rectangle shape with position and dimensions."""
    type: Literal[ShapeType.RECTANGLE] = ShapeType.RECTANGLE
    x: float = Field(ge=0.0)  # Inches from panel left
    y: float = Field(ge=0.0)  # Inches from panel bottom
    width: float = Field(gt=0.0)  # Inches
    height: float = Field(gt=0.0)  # Inches

class Circle(BaseShape):
    """Circle shape with center and radius."""
    type: Literal[ShapeType.CIRCLE] = ShapeType.CIRCLE
    center_x: float = Field(ge=0.0)  # Inches
    center_y: float = Field(ge=0.0)  # Inches
    radius: float = Field(gt=0.0)  # Inches

class Triangle(BaseShape):
    """Triangle shape with three vertices."""
    type: Literal[ShapeType.TRIANGLE] = ShapeType.TRIANGLE
    x1: float = Field(ge=0.0)  # Inches
    y1: float = Field(ge=0.0)
    x2: float = Field(ge=0.0)
    y2: float = Field(ge=0.0)
    x3: float = Field(ge=0.0)
    y3: float = Field(ge=0.0)

class Star(BaseShape):
    """Star shape with configurable points."""
    type: Literal[ShapeType.STAR] = ShapeType.STAR
    center_x: float = Field(ge=0.0)  # Inches
    center_y: float = Field(ge=0.0)
    outer_radius: float = Field(gt=0.0)  # Inches
    inner_radius: float = Field(gt=0.0)  # Inches
    points: int = Field(default=5, ge=3, le=20)

class Line(BaseShape):
    """Line shape with start and end points."""
    type: Literal[ShapeType.LINE] = ShapeType.LINE
    start_x: float = Field(ge=0.0)  # Inches
    start_y: float = Field(ge=0.0)
    end_x: float = Field(ge=0.0)
    end_y: float = Field(ge=0.0)

# Discriminated union
Shape = Annotated[
    Rectangle | Circle | Triangle | Star | Line,
    Field(discriminator='type')
]

class DecorativeElement(BaseModel):
    """Composition of shapes forming a reusable design unit."""
    id: str = Field(default_factory=uuid4)
    name: str  # e.g., "geometric_tree"
    x: float = Field(ge=0.0)  # Position in inches
    y: float = Field(ge=0.0)
    scale: float = Field(default=1.0, gt=0.0)  # Proportional scale
    rotation: float = Field(default=0.0)  # Degrees
    color_palette: Optional[dict[str, str]] = None  # role -> hex color
    shapes: list[Shape]  # Internal composition (relative coords)

# Union type for polymorphic rendering
ShapeElement = Rectangle | Circle | Triangle | Star | Line | DecorativeElement

# EXTENDED: Panel model
class Panel(BaseModel):
    # ... existing fields ...
    shape_elements: list[ShapeElement] = Field(default_factory=list)
    # Rendering order: shapes sorted by z_index, then text_elements, then image_elements
```

**YAML Schema Examples** (`contracts/shape-yaml-schema.md`):

```yaml
# Basic shape in panel
panels:
  - position: front
    # ... existing fields ...
    shape_elements:
      - type: rectangle
        x: 1.0
        y: 2.0
        width: 3.0
        height: 1.5
        fill_color: "#A8B5A0"  # Sage green
        stroke_color: "#333333"
        stroke_width: 2
        opacity: 0.8
        z_index: 1

      - type: circle
        center_x: 4.0
        center_y: 5.0
        radius: 0.5
        fill_color: "#B85C50"  # Burgundy
        z_index: 2

      - type: triangle
        x1: 2.0
        y1: 3.0
        x2: 3.0
        y2: 3.0
        x3: 2.5
        y3: 4.0
        fill_color: "#D4AF37"  # Gold
        rotation: 15
        z_index: 3

# Decorative element in panel
shape_elements:
  - type: decorative_element
    name: geometric_tree
    x: 4.25  # Center of panel
    y: 3.0
    scale: 1.2
    rotation: 0
    color_palette:
      tree_primary: "#A8B5A0"
      tree_accent: "#B85C50"
      ornament: "#D4AF37"
```

**Decorative Element Library Format**:

```yaml
# decorative_elements/christmas/geometric_tree.yaml
name: geometric_tree
description: "Geometric Christmas tree with overlapping triangles"
default_width: 3.0  # Inches (for scale calculation)
default_height: 4.0
color_roles:
  - tree_primary: "#A8B5A0"  # Default sage
  - tree_accent: "#B85C50"   # Default burgundy
  - ornament: "#D4AF37"      # Default gold
  - star: "#FFD700"          # Default bright gold

shapes:
  # Base triangle (largest)
  - type: triangle
    x1: 0.0
    y1: 0.0
    x2: 3.0
    y2: 0.0
    x3: 1.5
    y3: 1.5
    fill_color: "{tree_primary}"  # Template variable
    z_index: 1

  # Middle triangle
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

  # Top triangle
  - type: triangle
    x1: 1.0
    y1: 2.0
    x2: 2.0
    y2: 2.0
    x3: 1.5
    y3: 3.5
    fill_color: "{tree_primary}"
    z_index: 3

  # Star topper
  - type: star
    center_x: 1.5
    center_y: 3.8
    outer_radius: 0.3
    inner_radius: 0.15
    points: 5
    fill_color: "{star}"
    z_index: 10

  # Ornaments (circles)
  - type: circle
    center_x: 1.0
    center_y: 1.2
    radius: 0.15
    fill_color: "{ornament}"
    z_index: 5
```

**Rendering Strategy**:

1. **Z-Index Sorting**: Collect all renderable elements (shapes, text, images) and sort by z_index
2. **ReportLab Context Management**: Use `saveState()`/`restoreState()` for rotation
3. **Measurement Conversion**: Convert inches to points (72 pts/inch) at render time
4. **Color Parsing**: Convert hex strings to ReportLab Color objects
5. **Opacity Handling**: Use `setFillAlpha()` and `setStrokeAlpha()` before drawing
6. **Decorative Element Expansion**: Resolve color palette templates, apply scale/rotation transforms

**Component Interactions**:

```
Template YAML
    ↓ (parsed by templates.py)
Panel with shape_elements list
    ↓ (validated by Pydantic)
List[ShapeElement] (discriminated union)
    ↓ (sorted by z_index in renderer)
ReportLabRenderer.render_shape()
    ↓ (delegates to shape-specific methods)
canvas.rect() / canvas.circle() / canvas.polygon() / etc.
    ↓
PDF output
```

### Phase 2: Implementation Sequence

**Iteration 1: Basic Shape Rendering (US1, US6 - P1)**
- Add Shape models to `core/models.py`
- Implement `ShapeRenderer` with methods for each shape type
- Extend `Panel` model with `shape_elements` field
- Add YAML parsing support in `templates.py`
- Unit tests for shape model validation
- Integration test: Render card with all 5 shape types

**Iteration 2: Z-Index Layering (US2 - P1)**
- Implement z-index sorting in renderer
- Handle mixed element types (shapes, text, images)
- Visual regression test: 10+ overlapping shapes
- Edge case tests: Same z-index, negative z-index

**Iteration 3: Shape Styling (US3 - P2)**
- Implement opacity rendering with `setFillAlpha()`
- Implement rotation with save/restore state
- Add stroke rendering (width, color)
- Visual regression tests for each property
- Edge case tests: Opacity interaction, stroke overflow

**Iteration 4: Decorative Element System (US4, US5 - P2/P3)**
- Create `DecorativeElement` model
- Implement decorative element library loader
- Create 10 decorative element YAML definitions
- Implement color palette template substitution
- Implement scale and rotation transforms
- Visual regression test for each decorative element

**Iteration 5: Reference Template & Polish**
- Create `geometric_christmas_tree.yaml` template
- Visual regression test for complete geometric tree card
- Performance testing with 50+ shapes
- Documentation and YAML schema guide
- Backward compatibility verification

### Phase 3: Testing Strategy

**Unit Tests** (pytest):
- Shape model validation (required fields, ranges)
- Discriminated union parsing from YAML
- Decorative element library loading
- Color palette substitution
- Measurement conversions (inches to points)
- Z-index sorting with mixed element types

**Integration Tests**:
- End-to-end: YAML → Card → PDF with shapes
- All 5 shape types render correctly
- Z-index ordering with 15+ elements
- Decorative elements with scale/rotation
- Backward compatibility: Existing templates still work

**Visual Regression Tests** (pdf2image + imagehash):
- Reference PDFs for each shape type
- Reference PDFs for opacity, rotation, stroke variations
- Reference PDFs for each decorative element
- Reference PDF for geometric Christmas tree card
- Hash comparison with tolerance for minor rendering differences

**Performance Tests**:
- Card with 50 shapes generates in <10 seconds
- Card with 100 shapes generates in <20 seconds
- Decorative element loading <100ms for 10 elements

**Edge Case Tests**:
- Shape extends beyond panel boundaries (clipping)
- Invalid z_index (negative, non-integer)
- Invalid colors (malformed hex, out of range)
- Decorative element with scale 0 or negative
- Missing color palette entries
- Very large stroke_width
- Rotation of 360+ degrees

### Phase 4: Deployment Considerations

**Backward Compatibility**:
- Existing templates without `shape_elements` must work unchanged
- Panel model with `shape_elements=[]` is default
- No changes to CLI commands (uses existing `generate` command)

**Documentation Updates**:
- YAML schema guide with shape examples
- Decorative element catalog with visual previews
- Tutorial: Creating geometric designs
- Migration guide: Adding shapes to existing templates

**Future Enhancements** (Out of Scope):
- SVG import for custom vector graphics
- Gradient fills for shapes
- Pattern fills (hatching, dots)
- Curved paths and bezier curves
- Shape grouping for complex compositions
- Animation/preview of layering order

## Dependencies

**Runtime** (no new dependencies):
- ReportLab 4.0+ (already present) - drawing primitives
- Pydantic 2.0+ (already present) - discriminated unions

**Development** (already present):
- pytest 7.0+
- pdf2image (visual regression)
- imagehash (visual comparison)

## Configuration

**Decorative Element Library Path**:
- Default: `decorative_elements/` (relative to package)
- Environment variable: `HOLIDAY_CARD_DECORATIVE_PATH` (override)

**Visual Regression Tolerance**:
- Hash difference threshold: 5 (out of 64-bit hash)
- Allows minor anti-aliasing differences across platforms

## Rollout Plan

**Phase A: Development** (This Feature)
- Implement all 5 shape types
- Create 10 decorative elements
- Visual regression test suite
- Geometric Christmas tree reference template

**Phase B: Documentation**
- YAML schema reference
- Decorative element catalog
- Tutorial examples

**Phase C: Community**
- Accept decorative element contributions
- Gallery of community-created designs
- Template marketplace (future)

## Success Metrics

- [ ] All 5 shape types (Rectangle, Circle, Triangle, Star, Line) render correctly
- [ ] Z-index layering works with 10+ overlapping shapes
- [ ] 10+ decorative elements in library
- [ ] Geometric Christmas tree template demonstrates capability
- [ ] 100% backward compatibility with existing templates
- [ ] Visual regression tests pass on Linux, macOS, Windows
- [ ] Performance: 50 shapes in <10 seconds
- [ ] Documentation: YAML schema guide and tutorials complete
