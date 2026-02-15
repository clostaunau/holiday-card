# Implementation Tasks: Vector Graphics and Decorative Elements System

**Feature Branch**: `003-vector-graphics-and-decorative-elements`
**Created**: 2025-12-25
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Task Organization

Tasks are organized by user story priority and implementation iteration. Each task is independently testable and delivers incremental value.

### Dependency Flow

```
Setup (T000) →
  Iteration 1: Basic Shapes (T100-T106) →
    Iteration 2: Z-Index Layering (T200-T204) →
      Iteration 3: Styling (T300-T305) →
        Iteration 4: Decorative Elements (T400-T407) →
          Iteration 5: Polish & Documentation (T500-T505)
```

---

## T000: Project Setup

### T000.1: Create Feature Branch

**User Story**: N/A (Setup)
**Priority**: P0
**Dependencies**: None

**Description**: Create and checkout feature branch for vector graphics implementation.

**Steps**:
1. Create branch from main: `git checkout -b 003-vector-graphics-and-decorative-elements`
2. Verify clean working directory
3. Push branch to remote

**Acceptance Criteria**:
- [ ] Branch `003-vector-graphics-and-decorative-elements` exists
- [ ] Branch is checked out locally
- [ ] Branch pushed to remote repository

**Estimated Effort**: 5 minutes

---

### T000.2: Set Up Test Fixtures Directory

**User Story**: N/A (Setup)
**Priority**: P0
**Dependencies**: T000.1

**Description**: Create directory structure for visual regression test reference PDFs.

**Steps**:
1. Create `tests/visual/fixtures/reference_cards/` directory
2. Create `.gitkeep` file to track empty directory
3. Document fixture naming convention in README

**Acceptance Criteria**:
- [ ] Directory `tests/visual/fixtures/reference_cards/` exists
- [ ] Directory tracked in git
- [ ] README documents fixture organization

**Estimated Effort**: 10 minutes

---

## Iteration 1: Basic Shape Rendering (US1, US6)

**Goal**: Implement 5 basic shape types with YAML parsing and rendering.

### T100: Define Shape Models

**User Story**: US1 - Basic Shape Rendering (P1), US6 - YAML Template Definition (P1)
**Priority**: P1
**Dependencies**: T000.2

**Description**: Add Pydantic models for all 5 shape types to `src/holiday_card/core/models.py`.

**Implementation**:
1. Add `ShapeType` enum with values: rectangle, circle, triangle, star, line
2. Create `BaseShape` abstract model with common properties:
   - `id: str`
   - `type: ShapeType` (discriminator)
   - `z_index: int = 0`
   - `fill_color: Optional[str]` (hex)
   - `stroke_color: Optional[str]` (hex)
   - `stroke_width: float = 0.0`
   - `opacity: float = 1.0`
   - `rotation: float = 0.0`
3. Create concrete shape models:
   - `Rectangle(BaseShape)`: x, y, width, height
   - `Circle(BaseShape)`: center_x, center_y, radius
   - `Triangle(BaseShape)`: x1, y1, x2, y2, x3, y3
   - `Star(BaseShape)`: center_x, center_y, outer_radius, inner_radius, points
   - `Line(BaseShape)`: start_x, start_y, end_x, end_y
4. Create discriminated union: `Shape = Annotated[Rectangle | Circle | Triangle | Star | Line, Field(discriminator='type')]`
5. Add validation:
   - All positions/dimensions >= 0.0
   - Opacity in [0.0, 1.0]
   - Rotation in [0.0, 360.0)
   - Stroke_width >= 0.0
   - Hex color format validation
   - Star: inner_radius < outer_radius

**Files Modified**:
- `src/holiday_card/core/models.py`

**Tests**:
- Unit tests: `tests/unit/test_shape_models.py`
  - Test each shape type instantiation
  - Test validation rules (ranges, hex colors)
  - Test discriminated union parsing from dict
  - Test invalid values raise ValidationError

**Acceptance Criteria**:
- [ ] All 5 shape types defined as Pydantic models
- [ ] BaseShape with common properties
- [ ] Discriminated union works with `type` field
- [ ] Validation rules enforce constraints
- [ ] Unit tests pass (100% coverage for models)

**Estimated Effort**: 3 hours

---

### T101: Extend Panel Model for Shapes

**User Story**: US6 - YAML Template Definition (P1)
**Priority**: P1
**Dependencies**: T100

**Description**: Add `shape_elements` field to Panel model for backward compatibility.

**Implementation**:
1. Extend `Panel` model in `src/holiday_card/core/models.py`:
   ```python
   class Panel(BaseModel):
       # ... existing fields ...
       shape_elements: list[Shape] = Field(default_factory=list)
   ```
2. Ensure default empty list maintains backward compatibility
3. Update Panel docstring to document shape_elements

**Files Modified**:
- `src/holiday_card/core/models.py`

**Tests**:
- Unit tests: `tests/unit/test_models.py`
  - Test Panel with empty shape_elements
  - Test Panel with multiple shapes
  - Test backward compatibility (existing Panel YAML loads)

**Acceptance Criteria**:
- [ ] Panel.shape_elements field exists
- [ ] Defaults to empty list
- [ ] Existing templates load without modification
- [ ] Unit tests pass

**Estimated Effort**: 30 minutes

---

### T102: Implement YAML Template Parsing for Shapes

**User Story**: US6 - YAML Template Definition (P1)
**Priority**: P1
**Dependencies**: T101

**Description**: Extend template loading to parse shape_elements from YAML.

**Implementation**:
1. Verify Pydantic automatically handles discriminated union parsing
2. Add validation in `src/holiday_card/core/templates.py`:
   - Clear error messages for invalid shape types
   - Validate shape coordinates within panel boundaries (warning)
3. Test parsing with sample YAML files

**Files Modified**:
- `src/holiday_card/core/templates.py` (minimal changes, Pydantic handles most)

**Tests**:
- Integration tests: `tests/integration/test_template_loading.py`
  - Load template with all 5 shape types
  - Test invalid shape type error message
  - Test missing required field error message
  - Test out-of-range values error message

**Acceptance Criteria**:
- [ ] Templates with shape_elements parse correctly
- [ ] Clear validation error messages
- [ ] All 5 shape types parse from YAML
- [ ] Integration tests pass

**Estimated Effort**: 1 hour

---

### T103: Create Shape Renderer Module

**User Story**: US1 - Basic Shape Rendering (P1)
**Priority**: P1
**Dependencies**: T102

**Description**: Create dedicated shape rendering module with methods for each shape type.

**Implementation**:
1. Create `src/holiday_card/renderers/shape_renderer.py`
2. Implement `ShapeRenderer` class with methods:
   - `render_rectangle(canvas, rect: Rectangle, panel_offset_x, panel_offset_y)`
   - `render_circle(canvas, circle: Circle, panel_offset_x, panel_offset_y)`
   - `render_triangle(canvas, triangle: Triangle, panel_offset_x, panel_offset_y)`
   - `render_star(canvas, star: Star, panel_offset_x, panel_offset_y)`
   - `render_line(canvas, line: Line, panel_offset_x, panel_offset_y)`
3. Each method:
   - Converts inches to points (× 72)
   - Applies fill_color and stroke_color (if set)
   - Applies stroke_width
   - Uses ReportLab primitives: rect(), circle(), polygon path, line()
4. Helper methods:
   - `_hex_to_reportlab_color(hex_str: str) -> Color`
   - `_calculate_star_points(star: Star) -> list[tuple[float, float]]`
   - `_inches_to_points(inches: float) -> float`

**Files Created**:
- `src/holiday_card/renderers/shape_renderer.py`

**Tests**:
- Unit tests: `tests/unit/test_shape_renderer.py`
  - Mock canvas, verify correct ReportLab calls
  - Test each shape type renders
  - Test inch-to-point conversion
  - Test hex-to-color conversion

**Acceptance Criteria**:
- [ ] ShapeRenderer class exists
- [ ] All 5 shape types have render methods
- [ ] Measurement conversion (inches → points)
- [ ] Color conversion (hex → ReportLab Color)
- [ ] Unit tests pass (mocked canvas)

**Estimated Effort**: 4 hours

---

### T104: Integrate Shapes into ReportLab Renderer

**User Story**: US1 - Basic Shape Rendering (P1)
**Priority**: P1
**Dependencies**: T103

**Description**: Extend ReportLabRenderer to render shapes from Panel.shape_elements.

**Implementation**:
1. Modify `src/holiday_card/renderers/reportlab_renderer.py`:
   - Import ShapeRenderer
   - In `render_panel()` method, add shape rendering loop:
     ```python
     shape_renderer = ShapeRenderer()
     for shape in panel.shape_elements:
         if isinstance(shape, Rectangle):
             shape_renderer.render_rectangle(canvas, shape, panel.x, panel.y)
         elif isinstance(shape, Circle):
             shape_renderer.render_circle(canvas, shape, panel.x, panel.y)
         # ... etc for all shape types
     ```
   - Render shapes before text_elements (for now, z-index in Iteration 2)

**Files Modified**:
- `src/holiday_card/renderers/reportlab_renderer.py`

**Tests**:
- Integration tests: `tests/integration/test_shape_rendering.py`
  - End-to-end: YAML template → PDF with shapes
  - Verify each shape type renders without error
  - Visual inspection of generated PDF (manual for now)

**Acceptance Criteria**:
- [ ] ReportLabRenderer calls ShapeRenderer
- [ ] Shapes render in generated PDFs
- [ ] All 5 shape types work end-to-end
- [ ] Integration tests pass

**Estimated Effort**: 2 hours

---

### T105: Create Test Template with All Shape Types

**User Story**: US1 - Basic Shape Rendering (P1)
**Priority**: P1
**Dependencies**: T104

**Description**: Create comprehensive test template demonstrating all 5 shape types.

**Implementation**:
1. Create `tests/fixtures/templates/shapes_all_types.yaml`:
   - Front panel with one of each shape type
   - Different colors, sizes, positions
   - No overlaps (simple layout for clarity)
2. Document shape purpose in comments
3. Generate reference PDF manually

**Files Created**:
- `tests/fixtures/templates/shapes_all_types.yaml`

**Tests**:
- Manual visual verification: Generate PDF, inspect each shape
- Store reference PDF: `tests/visual/fixtures/reference_cards/shapes_all_types.pdf`

**Acceptance Criteria**:
- [ ] Template defines all 5 shape types
- [ ] Template generates valid PDF
- [ ] Each shape visually correct (manual check)
- [ ] Reference PDF stored for visual regression

**Estimated Effort**: 1 hour

---

### T106: Visual Regression Test for Basic Shapes

**User Story**: US1 - Basic Shape Rendering (P1)
**Priority**: P1
**Dependencies**: T105

**Description**: Implement visual regression test comparing generated PDFs to reference.

**Implementation**:
1. Create or extend `tests/visual/test_visual_regression.py`
2. Implement test function:
   ```python
   def test_shapes_all_types_visual():
       # Generate PDF from template
       generated_pdf = generate_card("shapes_all_types.yaml")
       reference_pdf = "tests/visual/fixtures/reference_cards/shapes_all_types.pdf"

       # Convert to images
       gen_img = pdf_to_image(generated_pdf)
       ref_img = pdf_to_image(reference_pdf)

       # Compare hashes
       gen_hash = imagehash.average_hash(gen_img)
       ref_hash = imagehash.average_hash(ref_img)

       # Allow small tolerance (5 bits different)
       assert gen_hash - ref_hash <= 5, f"Visual regression: hash diff {gen_hash - ref_hash}"
   ```
3. Document hash tolerance rationale (anti-aliasing differences)

**Files Modified/Created**:
- `tests/visual/test_visual_regression.py`

**Tests**:
- Run visual regression test suite
- Verify test passes with reference PDF
- Verify test fails with intentional shape change

**Acceptance Criteria**:
- [ ] Visual regression test framework exists
- [ ] Test for all shape types passes
- [ ] Hash tolerance documented
- [ ] Test fails when shapes change

**Estimated Effort**: 2 hours

---

## Iteration 2: Z-Index Layering (US2)

**Goal**: Implement z-index sorting for correct layering of overlapping shapes.

### T200: Extend Models with Z-Index

**User Story**: US2 - Shape Layering and Overlap (P1)
**Priority**: P1
**Dependencies**: T106

**Description**: Ensure all renderable elements (shapes, text, images) support z_index.

**Implementation**:
1. Shapes already have z_index (from T100)
2. Add z_index to TextElement model (if not present):
   ```python
   class TextElement(BaseModel):
       # ... existing fields ...
       z_index: int = Field(default=100, description="Rendering layer")
   ```
3. Add z_index to ImageElement model:
   ```python
   class ImageElement(BaseModel):
       # ... existing fields ...
       z_index: int = Field(default=100, description="Rendering layer")
   ```
4. Document default z_index values (shapes=0, text/images=100)

**Files Modified**:
- `src/holiday_card/core/models.py`

**Tests**:
- Unit tests: Verify TextElement and ImageElement have z_index field

**Acceptance Criteria**:
- [ ] All element types have z_index property
- [ ] Default values documented
- [ ] Unit tests pass

**Estimated Effort**: 30 minutes

---

### T201: Implement Z-Index Sorting in Renderer

**User Story**: US2 - Shape Layering and Overlap (P1)
**Priority**: P1
**Dependencies**: T200

**Description**: Sort all panel elements by z_index before rendering.

**Implementation**:
1. Modify `ReportLabRenderer.render_panel()`:
   ```python
   def render_panel(self, canvas, panel: Panel):
       # Collect all elements with z_index
       elements = []
       for shape in panel.shape_elements:
           elements.append(('shape', shape, shape.z_index))
       for text in panel.text_elements:
           elements.append(('text', text, text.z_index))
       for image in panel.image_elements:
           elements.append(('image', image, image.z_index))

       # Sort by z_index (lowest first = bottom layer)
       elements.sort(key=lambda e: e[2])

       # Render in sorted order
       for elem_type, elem, _ in elements:
           if elem_type == 'shape':
               self._render_shape(elem)
           elif elem_type == 'text':
               self._render_text(elem)
           elif elem_type == 'image':
               self._render_image(elem)
   ```
2. Refactor rendering logic into helper methods if needed

**Files Modified**:
- `src/holiday_card/renderers/reportlab_renderer.py`

**Tests**:
- Integration tests: `tests/integration/test_z_index_layering.py`
  - Create template with mixed elements at different z-index
  - Verify rendering order (mock canvas, check call order)

**Acceptance Criteria**:
- [ ] Elements sorted by z_index before rendering
- [ ] Lowest z_index renders first (bottom)
- [ ] Same z_index renders in definition order
- [ ] Integration tests verify order

**Estimated Effort**: 2 hours

---

### T202: Create Layering Test Template

**User Story**: US2 - Shape Layering and Overlap (P1)
**Priority**: P1
**Dependencies**: T201

**Description**: Create template with 10+ overlapping shapes demonstrating z-index.

**Implementation**:
1. Create `tests/fixtures/templates/shapes_layering.yaml`:
   - 10-15 overlapping circles/rectangles
   - Varying z_index values (1, 2, 3, ... 10)
   - Different colors for visual verification
   - Some with opacity for transparency
2. Document expected layering order in comments

**Files Created**:
- `tests/fixtures/templates/shapes_layering.yaml`

**Tests**:
- Generate PDF, manually verify layering order
- Store reference PDF

**Acceptance Criteria**:
- [ ] Template with 10+ overlapping shapes
- [ ] Clear z-index progression
- [ ] Visual layering is correct
- [ ] Reference PDF stored

**Estimated Effort**: 1 hour

---

### T203: Visual Regression Test for Layering

**User Story**: US2 - Shape Layering and Overlap (P1)
**Priority**: P1
**Dependencies**: T202

**Description**: Add visual regression test for z-index layering.

**Implementation**:
1. Add test to `tests/visual/test_visual_regression.py`:
   ```python
   def test_shapes_layering_visual():
       # Same pattern as T106
       # Compare generated vs reference PDF
   ```
2. Generate and store reference PDF

**Files Modified**:
- `tests/visual/test_visual_regression.py`

**Acceptance Criteria**:
- [ ] Visual regression test for layering
- [ ] Test passes with reference PDF
- [ ] Layering order verified

**Estimated Effort**: 30 minutes

---

### T204: Edge Case Tests for Z-Index

**User Story**: US2 - Shape Layering and Overlap (P1)
**Priority**: P1
**Dependencies**: T203

**Description**: Test edge cases for z-index handling.

**Implementation**:
1. Add unit tests in `tests/unit/test_z_index_edge_cases.py`:
   - Negative z_index values
   - Very large z_index values (1000000)
   - Same z_index across all elements
   - Empty shape_elements list
2. Add validation tests:
   - Non-integer z_index should fail (Pydantic validation)

**Files Created**:
- `tests/unit/test_z_index_edge_cases.py`

**Acceptance Criteria**:
- [ ] Negative z_index works (renders first)
- [ ] Large z_index works (renders last)
- [ ] Same z_index renders in definition order
- [ ] All edge case tests pass

**Estimated Effort**: 1 hour

---

## Iteration 3: Shape Styling (US3)

**Goal**: Implement opacity, rotation, and stroke styling for shapes.

### T300: Implement Opacity Rendering

**User Story**: US3 - Shape Styling and Visual Properties (P2)
**Priority**: P2
**Dependencies**: T204

**Description**: Add opacity (alpha) rendering to ShapeRenderer.

**Implementation**:
1. Modify `ShapeRenderer` methods to apply opacity:
   ```python
   def render_rectangle(self, canvas, rect: Rectangle, offset_x, offset_y):
       if rect.opacity < 1.0:
           canvas.setFillAlpha(rect.opacity)
           canvas.setStrokeAlpha(rect.opacity)

       # ... existing rendering code ...

       if rect.opacity < 1.0:
           canvas.setFillAlpha(1.0)  # Reset to opaque
           canvas.setStrokeAlpha(1.0)
   ```
2. Apply to all shape render methods
3. Handle edge case: opacity 0.0 (invisible shape)

**Files Modified**:
- `src/holiday_card/renderers/shape_renderer.py`

**Tests**:
- Unit tests: Mock canvas, verify setFillAlpha/setStrokeAlpha calls
- Integration test: Render shapes with opacity 0.5, verify semi-transparent

**Acceptance Criteria**:
- [ ] Opacity property affects shape rendering
- [ ] Opacity 0.0 makes shape invisible
- [ ] Opacity 1.0 is fully opaque
- [ ] Alpha resets after each shape

**Estimated Effort**: 1 hour

---

### T301: Implement Rotation Rendering

**User Story**: US3 - Shape Styling and Visual Properties (P2)
**Priority**: P2
**Dependencies**: T300

**Description**: Add rotation rendering using ReportLab transformation matrix.

**Implementation**:
1. Modify each `ShapeRenderer.render_*` method:
   ```python
   def render_rectangle(self, canvas, rect: Rectangle, offset_x, offset_y):
       if rect.rotation != 0.0:
           canvas.saveState()

           # Calculate center point
           center_x = (offset_x + rect.x + rect.width / 2) * 72
           center_y = (offset_y + rect.y + rect.height / 2) * 72

           # Translate, rotate, translate back
           canvas.translate(center_x, center_y)
           canvas.rotate(rect.rotation)
           canvas.translate(-center_x, -center_y)

       # ... existing rendering code ...

       if rect.rotation != 0.0:
           canvas.restoreState()
   ```
2. Implement for all shape types (different center calculations)
3. Triangle center: ((x1+x2+x3)/3, (y1+y2+y3)/3)
4. Star/Circle center: (center_x, center_y)
5. Line center: ((start_x+end_x)/2, (start_y+end_y)/2)

**Files Modified**:
- `src/holiday_card/renderers/shape_renderer.py`

**Tests**:
- Unit tests: Mock canvas, verify saveState/rotate/restoreState calls
- Integration test: Render rotated shapes at 0, 45, 90, 180, 270 degrees

**Acceptance Criteria**:
- [ ] Rotation property rotates shapes
- [ ] Rotation around correct center point for each type
- [ ] Canvas state saved/restored correctly
- [ ] All rotation angles work (0-360)

**Estimated Effort**: 3 hours

---

### T302: Implement Stroke Rendering

**User Story**: US3 - Shape Styling and Visual Properties (P2)
**Priority**: P2
**Dependencies**: T301

**Description**: Add stroke (outline) rendering with width and color.

**Implementation**:
1. Modify `ShapeRenderer` to handle stroke:
   ```python
   def render_rectangle(self, canvas, rect: Rectangle, offset_x, offset_y):
       # Set fill color (if present)
       has_fill = rect.fill_color is not None
       if has_fill:
           canvas.setFillColor(self._hex_to_color(rect.fill_color))

       # Set stroke color and width (if present)
       has_stroke = rect.stroke_color is not None and rect.stroke_width > 0
       if has_stroke:
           canvas.setStrokeColor(self._hex_to_color(rect.stroke_color))
           canvas.setLineWidth(rect.stroke_width)

       # Draw with appropriate fill/stroke flags
       canvas.rect(x, y, w, h, stroke=int(has_stroke), fill=int(has_fill))
   ```
2. Implement for all shape types
3. Handle lines (stroke only, no fill)

**Files Modified**:
- `src/holiday_card/renderers/shape_renderer.py`

**Tests**:
- Unit tests: Verify setStrokeColor and setLineWidth calls
- Integration test: Render shapes with stroke only, fill only, both, neither

**Acceptance Criteria**:
- [ ] Stroke renders with correct width and color
- [ ] Fill and stroke can be used independently
- [ ] Lines ignore fill_color
- [ ] Shapes with neither fill nor stroke render invisibly (edge case)

**Estimated Effort**: 2 hours

---

### T303: Create Styling Test Template

**User Story**: US3 - Shape Styling and Visual Properties (P2)
**Priority**: P2
**Dependencies**: T302

**Description**: Create template demonstrating opacity, rotation, and stroke.

**Implementation**:
1. Create `tests/fixtures/templates/shapes_styling.yaml`:
   - Shapes with opacity 0.3, 0.5, 0.7, 1.0
   - Shapes rotated 0, 45, 90, 135, 180 degrees
   - Shapes with thick stroke (5pt), thin stroke (1pt), no stroke
   - Shapes with fill only, stroke only, both
2. Visually organized for easy verification

**Files Created**:
- `tests/fixtures/templates/shapes_styling.yaml`

**Tests**:
- Generate PDF, verify visual appearance
- Store reference PDF

**Acceptance Criteria**:
- [ ] Template demonstrates all styling properties
- [ ] PDF generated successfully
- [ ] Visual appearance correct
- [ ] Reference PDF stored

**Estimated Effort**: 1.5 hours

---

### T304: Visual Regression Test for Styling

**User Story**: US3 - Shape Styling and Visual Properties (P2)
**Priority**: P2
**Dependencies**: T303

**Description**: Add visual regression test for styling properties.

**Implementation**:
1. Add test to `tests/visual/test_visual_regression.py`:
   ```python
   def test_shapes_styling_visual():
       # Compare generated vs reference PDF
   ```

**Files Modified**:
- `tests/visual/test_visual_regression.py`

**Acceptance Criteria**:
- [ ] Visual regression test for styling
- [ ] Test passes with reference PDF

**Estimated Effort**: 30 minutes

---

### T305: Edge Case Tests for Styling

**User Story**: US3 - Shape Styling and Visual Properties (P2)
**Priority**: P2
**Dependencies**: T304

**Description**: Test edge cases for styling properties.

**Implementation**:
1. Add unit tests in `tests/unit/test_styling_edge_cases.py`:
   - Opacity 0.0 (invisible)
   - Rotation 360 (same as 0)
   - Rotation > 360 (should normalize)
   - Stroke width 0 (no stroke)
   - Very large stroke width (100pt)
   - Overlapping semi-transparent shapes (alpha blending)

**Files Created**:
- `tests/unit/test_styling_edge_cases.py`

**Acceptance Criteria**:
- [ ] All edge cases handled correctly
- [ ] No crashes or errors
- [ ] Edge case tests pass

**Estimated Effort**: 1 hour

---

## Iteration 4: Decorative Elements (US4, US5)

**Goal**: Implement decorative element library and composition system.

### T400: Create DecorativeElement Model

**User Story**: US4 - Pre-built Decorative Elements (P2), US5 - Decorative Element Customization (P3)
**Priority**: P2
**Dependencies**: T305

**Description**: Add DecorativeElement and DecorativeElementDefinition models.

**Implementation**:
1. Add to `src/holiday_card/core/models.py`:
   ```python
   class DecorativeElement(BaseModel):
       id: str = Field(default_factory=uuid4)
       type: Literal["decorative_element"] = "decorative_element"
       name: str  # Reference to library definition
       x: float = Field(ge=0.0)
       y: float = Field(ge=0.0)
       scale: float = Field(default=1.0, gt=0.0)
       rotation: float = Field(default=0.0, ge=0.0, lt=360.0)
       color_palette: Optional[dict[str, str]] = None
       z_index: int = Field(default=0)

   class DecorativeElementDefinition(BaseModel):
       name: str
       description: Optional[str]
       default_width: float = Field(gt=0.0)
       default_height: float = Field(gt=0.0)
       color_roles: dict[str, str]  # role -> default hex color
       shapes: list[Shape]  # Internal composition
   ```
2. Update ShapeElement union: `ShapeElement = Rectangle | Circle | Triangle | Star | Line | DecorativeElement`
3. Validation: shapes list cannot contain DecorativeElements (no nesting)

**Files Modified**:
- `src/holiday_card/core/models.py`

**Tests**:
- Unit tests: `tests/unit/test_decorative_models.py`
  - Test DecorativeElement instantiation
  - Test DecorativeElementDefinition validation
  - Test no nesting validation

**Acceptance Criteria**:
- [ ] DecorativeElement model exists
- [ ] DecorativeElementDefinition model exists
- [ ] Validation prevents nesting
- [ ] Unit tests pass

**Estimated Effort**: 2 hours

---

### T401: Create Decorative Element Library Loader

**User Story**: US4 - Pre-built Decorative Elements (P2)
**Priority**: P2
**Dependencies**: T400

**Description**: Implement library loader for decorative element YAML definitions.

**Implementation**:
1. Create `src/holiday_card/core/decorative.py`:
   ```python
   class DecorativeElementLibrary:
       def __init__(self, library_path: Path):
           self.library_path = library_path
           self.definitions: dict[str, DecorativeElementDefinition] = {}

       def load_library(self):
           """Load all decorative element definitions from library path."""
           for yaml_file in self.library_path.glob("**/*.yaml"):
               definition = self._load_definition(yaml_file)
               self.definitions[definition.name] = definition

       def get_definition(self, name: str) -> DecorativeElementDefinition:
           """Get decorative element definition by name."""
           if name not in self.definitions:
               raise ValueError(f"Decorative element '{name}' not found")
           return self.definitions[name]

       def _load_definition(self, yaml_path: Path) -> DecorativeElementDefinition:
           with open(yaml_path) as f:
               data = yaml.safe_load(f)
           return DecorativeElementDefinition(**data)
   ```
2. Add default library path: `decorative_elements/` relative to package
3. Support environment variable override: `HOLIDAY_CARD_DECORATIVE_PATH`

**Files Created**:
- `src/holiday_card/core/decorative.py`

**Tests**:
- Unit tests: `tests/unit/test_decorative_library.py`
  - Test library loading
  - Test get_definition
  - Test missing definition error
  - Test invalid YAML error handling

**Acceptance Criteria**:
- [ ] DecorativeElementLibrary class exists
- [ ] Loads definitions from directory
- [ ] get_definition retrieves by name
- [ ] Clear error for missing definitions
- [ ] Unit tests pass

**Estimated Effort**: 2 hours

---

### T402: Implement Color Palette Substitution

**User Story**: US5 - Decorative Element Customization (P3)
**Priority**: P3
**Dependencies**: T401

**Description**: Implement color palette template substitution for decorative elements.

**Implementation**:
1. Add method to `DecorativeElementLibrary`:
   ```python
   def resolve_colors(
       self,
       definition: DecorativeElementDefinition,
       color_palette: Optional[dict[str, str]]
   ) -> list[Shape]:
       """Resolve {role} placeholders in shape colors."""
       palette = definition.color_roles.copy()
       if color_palette:
           palette.update(color_palette)  # Override defaults

       resolved_shapes = []
       for shape in definition.shapes:
           shape_copy = shape.copy(deep=True)

           # Substitute fill_color
           if shape_copy.fill_color and shape_copy.fill_color.startswith("{"):
               role = shape_copy.fill_color.strip("{}")
               shape_copy.fill_color = palette.get(role, shape_copy.fill_color)

           # Substitute stroke_color
           if shape_copy.stroke_color and shape_copy.stroke_color.startswith("{"):
               role = shape_copy.stroke_color.strip("{}")
               shape_copy.stroke_color = palette.get(role, shape_copy.stroke_color)

           resolved_shapes.append(shape_copy)

       return resolved_shapes
   ```
2. Validate all colors are valid hex after substitution

**Files Modified**:
- `src/holiday_card/core/decorative.py`

**Tests**:
- Unit tests: `tests/unit/test_color_palette.py`
  - Test substitution with default colors
  - Test substitution with overrides
  - Test partial override (some defaults used)
  - Test missing role (fallback to placeholder)

**Acceptance Criteria**:
- [ ] Color palette substitution works
- [ ] Overrides replace defaults
- [ ] Partial overrides work
- [ ] Unit tests pass

**Estimated Effort**: 2 hours

---

### T403: Implement Scale and Rotation Transforms

**User Story**: US5 - Decorative Element Customization (P3)
**Priority**: P3
**Dependencies**: T402

**Description**: Apply scale and rotation transforms to decorative element shapes.

**Implementation**:
1. Add method to `DecorativeElementLibrary`:
   ```python
   def apply_transforms(
       self,
       shapes: list[Shape],
       element: DecorativeElement
   ) -> list[Shape]:
       """Apply scale and rotation to all shapes in composition."""
       transformed = []
       for shape in shapes:
           shape_copy = shape.copy(deep=True)

           # Apply scale to all dimensions and positions
           shape_copy = self._apply_scale(shape_copy, element.scale)

           # Apply rotation (add to shape's rotation)
           shape_copy.rotation = (shape_copy.rotation + element.rotation) % 360

           transformed.append(shape_copy)

       return transformed

   def _apply_scale(self, shape: Shape, scale: float) -> Shape:
       """Scale all dimensions of a shape."""
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
       return shape
   ```

**Files Modified**:
- `src/holiday_card/core/decorative.py`

**Tests**:
- Unit tests: `tests/unit/test_decorative_transforms.py`
  - Test scale 0.5, 1.0, 2.0
  - Test rotation 0, 45, 90 degrees
  - Test combined scale + rotation
  - Verify proportions maintained

**Acceptance Criteria**:
- [ ] Scale multiplies all dimensions
- [ ] Rotation adds to shape rotations
- [ ] Proportions maintained
- [ ] Unit tests pass

**Estimated Effort**: 2 hours

---

### T404: Integrate Decorative Elements into Renderer

**User Story**: US4 - Pre-built Decorative Elements (P2)
**Priority**: P2
**Dependencies**: T403

**Description**: Extend renderer to handle DecorativeElement instances.

**Implementation**:
1. Modify `ReportLabRenderer`:
   - Initialize `DecorativeElementLibrary` on startup
   - When rendering DecorativeElement:
     a. Get definition from library
     b. Resolve color palette
     c. Apply scale and rotation transforms
     d. Render each shape in composition
   ```python
   def _render_decorative_element(self, canvas, element: DecorativeElement, panel):
       # Get definition
       definition = self.decorative_library.get_definition(element.name)

       # Resolve colors
       shapes = self.decorative_library.resolve_colors(
           definition, element.color_palette
       )

       # Apply transforms
       shapes = self.decorative_library.apply_transforms(shapes, element)

       # Translate shapes to element position
       for shape in shapes:
           # Adjust shape position by element.x, element.y
           shape = self._translate_shape(shape, element.x, element.y)

           # Render shape normally
           self.shape_renderer.render_shape(canvas, shape, panel.x, panel.y)
   ```

**Files Modified**:
- `src/holiday_card/renderers/reportlab_renderer.py`

**Tests**:
- Integration test: Render decorative element, verify shapes appear

**Acceptance Criteria**:
- [ ] Decorative elements render correctly
- [ ] Color palette overrides work
- [ ] Scale and rotation work
- [ ] Integration test passes

**Estimated Effort**: 3 hours

---

### T405: Create 10 Decorative Element Definitions

**User Story**: US4 - Pre-built Decorative Elements (P2)
**Priority**: P2
**Dependencies**: T404

**Description**: Create YAML definitions for 10 decorative elements.

**Implementation**:
1. Create directory: `decorative_elements/` with subdirectories:
   - `christmas/`
   - `hanukkah/`
   - `generic/`
2. Create decorative element YAML files:
   - `christmas/geometric_tree.yaml` - Overlapping triangles tree
   - `christmas/traditional_tree.yaml` - Classic tree silhouette
   - `christmas/ornament_bauble.yaml` - Round ornament
   - `christmas/ornament_star.yaml` - Star ornament
   - `generic/gift_box.yaml` - Gift with ribbon
   - `christmas/wreath.yaml` - Circular wreath
   - `christmas/star_topper.yaml` - Tree topper star
   - `christmas/snowflake.yaml` - Geometric snowflake
   - `hanukkah/menorah.yaml` - Nine-branched candelabra
   - `hanukkah/dreidel.yaml` - Spinning top
3. Each definition includes:
   - Descriptive name and description
   - default_width and default_height
   - color_roles with defaults
   - shapes composition (5-20 basic shapes)

**Files Created**:
- `decorative_elements/christmas/geometric_tree.yaml`
- `decorative_elements/christmas/traditional_tree.yaml`
- `decorative_elements/christmas/ornament_bauble.yaml`
- `decorative_elements/christmas/ornament_star.yaml`
- `decorative_elements/generic/gift_box.yaml`
- `decorative_elements/christmas/wreath.yaml`
- `decorative_elements/christmas/star_topper.yaml`
- `decorative_elements/christmas/snowflake.yaml`
- `decorative_elements/hanukkah/menorah.yaml`
- `decorative_elements/hanukkah/dreidel.yaml`

**Tests**:
- Validation: Load each definition, verify no errors
- Visual test: Render each element in isolation, verify appearance

**Acceptance Criteria**:
- [ ] 10 decorative elements defined
- [ ] All definitions parse without errors
- [ ] Each element visually correct (manual verification)
- [ ] Elements organized by occasion

**Estimated Effort**: 6 hours

---

### T406: Create Test Template with Decorative Elements

**User Story**: US4 - Pre-built Decorative Elements (P2)
**Priority**: P2
**Dependencies**: T405

**Description**: Create template demonstrating all decorative elements.

**Implementation**:
1. Create `tests/fixtures/templates/decorative_all.yaml`:
   - Grid layout showing all 10 elements
   - Each element at default scale
   - Labels identifying each element
2. Generate reference PDF

**Files Created**:
- `tests/fixtures/templates/decorative_all.yaml`

**Tests**:
- Generate PDF, verify all elements appear
- Store reference PDF

**Acceptance Criteria**:
- [ ] Template uses all 10 decorative elements
- [ ] PDF generated successfully
- [ ] All elements visible and correct
- [ ] Reference PDF stored

**Estimated Effort**: 1 hour

---

### T407: Visual Regression Test for Decorative Elements

**User Story**: US4 - Pre-built Decorative Elements (P2)
**Priority**: P2
**Dependencies**: T406

**Description**: Add visual regression test for decorative elements.

**Implementation**:
1. Add test to `tests/visual/test_visual_regression.py`:
   ```python
   def test_decorative_all_visual():
       # Compare generated vs reference PDF
   ```

**Files Modified**:
- `tests/visual/test_visual_regression.py`

**Acceptance Criteria**:
- [ ] Visual regression test for decorative elements
- [ ] Test passes with reference PDF

**Estimated Effort**: 30 minutes

---

## Iteration 5: Polish & Documentation (US All)

**Goal**: Create reference template, documentation, and final testing.

### T500: Create Geometric Christmas Tree Template

**User Story**: All user stories (demonstration)
**Priority**: P1
**Dependencies**: T407

**Description**: Create full geometric Christmas tree card template as feature showcase.

**Implementation**:
1. Create `templates/christmas/geometric.yaml`:
   - Front panel: geometric_tree decorative element, gift boxes, greeting
   - Inside left: Personal message with decorative stars
   - Inside right: Signature with small tree
   - Back: Simple star pattern
2. Use custom color palette (sage, burgundy, gold, teal)
3. Demonstrate layering, opacity, rotation
4. Professional, print-ready design

**Files Created**:
- `templates/christmas/geometric.yaml`

**Tests**:
- Generate PDF, verify professional appearance
- Print test on actual printer (if available)
- Store reference PDF

**Acceptance Criteria**:
- [ ] Complete geometric Christmas template created
- [ ] Matches specification's reference design
- [ ] Print-ready quality
- [ ] Reference PDF stored

**Estimated Effort**: 2 hours

---

### T501: Visual Regression Test for Geometric Tree Card

**User Story**: All user stories
**Priority**: P1
**Dependencies**: T500

**Description**: Add visual regression test for complete geometric tree card.

**Implementation**:
1. Add test to `tests/visual/test_visual_regression.py`:
   ```python
   def test_geometric_christmas_card_visual():
       # Compare generated vs reference PDF
   ```

**Files Modified**:
- `tests/visual/test_visual_regression.py`

**Acceptance Criteria**:
- [ ] Visual regression test for geometric tree card
- [ ] Test passes with reference PDF
- [ ] Demonstrates all features

**Estimated Effort**: 30 minutes

---

### T502: Backward Compatibility Test

**User Story**: All user stories (success criterion)
**Priority**: P1
**Dependencies**: T501

**Description**: Verify all existing templates still work unchanged.

**Implementation**:
1. Create test in `tests/integration/test_backward_compatibility.py`:
   ```python
   def test_existing_templates_unchanged():
       """Verify templates without shape_elements still work."""
       existing_templates = [
           "templates/christmas/classic.yaml",
           "templates/christmas/modern.yaml",
           "templates/hanukkah/menorah.yaml",
           "templates/birthday/balloons.yaml",
           "templates/generic/celebration.yaml",
       ]

       for template_path in existing_templates:
           # Load and generate card
           card_pdf = generate_card(template_path)

           # Verify PDF generated without errors
           assert card_pdf.exists()
           assert card_pdf.stat().st_size > 0
   ```
2. Run against all existing templates
3. Compare generated PDFs to previous versions (if available)

**Files Created**:
- `tests/integration/test_backward_compatibility.py`

**Acceptance Criteria**:
- [ ] All existing templates load without errors
- [ ] All existing templates generate PDFs
- [ ] No regressions in existing functionality
- [ ] Test passes

**Estimated Effort**: 1 hour

---

### T503: Performance Testing

**User Story**: All user stories (success criterion)
**Priority**: P2
**Dependencies**: T502

**Description**: Verify performance meets requirements (<10s for 50 shapes).

**Implementation**:
1. Create `tests/performance/test_shape_performance.py`:
   ```python
   def test_50_shapes_under_10_seconds():
       """Generate card with 50 shapes in under 10 seconds."""
       template = create_template_with_n_shapes(50)

       start_time = time.time()
       card_pdf = generate_card(template)
       end_time = time.time()

       elapsed = end_time - start_time
       assert elapsed < 10.0, f"Generation took {elapsed:.2f}s (max 10s)"

   def test_100_shapes_under_20_seconds():
       """Generate card with 100 shapes in under 20 seconds."""
       # Similar test with 100 shapes
   ```
2. Run performance tests on target hardware
3. Profile if performance issues found

**Files Created**:
- `tests/performance/test_shape_performance.py`

**Acceptance Criteria**:
- [ ] 50 shapes generate in <10 seconds
- [ ] 100 shapes generate in <20 seconds (stretch goal)
- [ ] Performance tests pass

**Estimated Effort**: 1.5 hours

---

### T504: Update Documentation

**User Story**: All user stories
**Priority**: P2
**Dependencies**: T503

**Description**: Update project documentation for vector graphics feature.

**Implementation**:
1. Update `CLAUDE.md`:
   - Add vector graphics to active features
   - Document new models and renderers
2. Create or update `README.md` section:
   - Quick example of using shapes
   - Link to quickstart guide
3. Update YAML schema documentation (already in `contracts/`)
4. Add docstrings to all new modules/classes

**Files Modified**:
- `CLAUDE.md`
- `README.md` (if exists)
- All new Python modules (docstrings)

**Acceptance Criteria**:
- [ ] CLAUDE.md updated
- [ ] README updated with shapes example
- [ ] All code has docstrings
- [ ] Documentation is accurate and helpful

**Estimated Effort**: 2 hours

---

### T505: Final Testing and Quality Check

**User Story**: All user stories
**Priority**: P1
**Dependencies**: T504

**Description**: Comprehensive final testing before feature completion.

**Implementation**:
1. Run full test suite:
   - Unit tests: `pytest tests/unit/`
   - Integration tests: `pytest tests/integration/`
   - Visual regression: `pytest tests/visual/`
   - Performance: `pytest tests/performance/`
2. Run linting: `ruff check .`
3. Run type checking: `mypy src/`
4. Code coverage: `pytest --cov=src/ --cov-report=html`
5. Manual testing:
   - Generate all example templates
   - Verify PDFs visually
   - Test on different platforms (if available)
6. Fix any issues found

**Acceptance Criteria**:
- [ ] All tests pass (unit, integration, visual, performance)
- [ ] No linting errors
- [ ] No type checking errors
- [ ] Code coverage ≥ 90%
- [ ] All example templates generate correctly
- [ ] No known bugs

**Estimated Effort**: 3 hours

---

## Summary

**Total Tasks**: 50
**Total Estimated Effort**: ~65 hours

**Iteration Breakdown**:
- Setup (T000): 15 minutes
- Iteration 1 - Basic Shapes (T100-T106): 13.5 hours
- Iteration 2 - Z-Index (T200-T204): 5 hours
- Iteration 3 - Styling (T300-T305): 9.5 hours
- Iteration 4 - Decorative Elements (T400-T407): 19.5 hours
- Iteration 5 - Polish (T500-T505): 10 hours

**Critical Path**:
T000 → T100 → T101 → T102 → T103 → T104 → T105 → T106 → T200 → T201 → T202 → T203 → T204 → T300 → T301 → T302 → T303 → T304 → T305 → T400 → T401 → T402 → T403 → T404 → T405 → T406 → T407 → T500 → T501 → T502 → T503 → T504 → T505

**Success Metrics**:
- [ ] All 5 shape types implemented and tested
- [ ] Z-index layering works correctly
- [ ] Opacity, rotation, stroke styling functional
- [ ] 10+ decorative elements in library
- [ ] Geometric Christmas tree template demonstrates feature
- [ ] 100% backward compatibility maintained
- [ ] Visual regression tests pass
- [ ] Performance targets met (<10s for 50 shapes)
- [ ] Documentation complete

---

**Ready for Implementation**: Tasks are sequenced, dependencies clear, acceptance criteria defined. Use `/speckit.implement` to begin execution.
