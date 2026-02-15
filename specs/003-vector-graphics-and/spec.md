# Feature Specification: Vector Graphics and Decorative Elements System

**Feature Branch**: `003-vector-graphics-and-decorative-elements`
**Created**: 2025-12-25
**Status**: Draft
**Input**: User description: "Add vector graphics and decorative element support to enable creating sophisticated template designs like geometric Christmas tree cards with overlapping shapes, decorative ornaments, and layered compositions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Shape Rendering (Priority: P1)

As a card creator, I want to add basic geometric shapes (rectangles, circles, triangles, stars, lines) to my card templates so I can create simple geometric designs and decorative patterns.

**Why this priority**: Foundation for all other vector graphics features. Without basic shapes, decorative elements and compositions cannot be built. Delivers immediate value by enabling geometric card designs.

**Independent Test**: Can be fully tested by creating a template with 5 different shape types, generating a PDF, and visually verifying the shapes render correctly with proper positioning and colors.

**Acceptance Scenarios**:

1. **Given** a template with a rectangle shape definition, **When** the card is generated, **Then** the rectangle appears at the specified position with correct dimensions, fill color, and stroke
2. **Given** a template with a circle shape definition, **When** the card is generated, **Then** the circle appears centered at the specified position with correct radius and colors
3. **Given** a template with a triangle shape definition, **When** the card is generated, **Then** the triangle appears with correct vertices and orientation
4. **Given** a template with a star shape definition, **When** the card is generated, **Then** the star appears with correct number of points and dimensions
5. **Given** a template with a line shape definition, **When** the card is generated, **Then** the line appears with correct start/end points and stroke properties

---

### User Story 2 - Shape Layering and Overlap (Priority: P1)

As a card creator, I want to layer shapes with z-index values so overlapping elements render in the correct visual order, enabling sophisticated geometric compositions like overlapping triangles.

**Why this priority**: Critical for creating the geometric Christmas tree design (overlapping triangles) and other professional designs. Without proper layering, shapes cannot create depth and visual interest.

**Independent Test**: Can be fully tested by creating a template with 10+ overlapping shapes at different z-index values, generating a PDF, and verifying the rendering order matches z-index priority (higher values on top).

**Acceptance Scenarios**:

1. **Given** a template with 3 overlapping circles at z-index 1, 2, 3, **When** the card is generated, **Then** circle 3 renders on top, circle 2 in middle, circle 1 at bottom
2. **Given** a template with shapes having same z-index, **When** the card is generated, **Then** shapes render in definition order (later shapes on top)
3. **Given** a template mixing shapes and text with z-index values, **When** the card is generated, **Then** all elements respect z-index ordering across types
4. **Given** a template with 15+ overlapping shapes, **When** the card is generated, **Then** all shapes render in correct z-index order without artifacts

---

### User Story 3 - Shape Styling and Visual Properties (Priority: P2)

As a card creator, I want to configure shape visual properties (fill color, stroke color, stroke width, opacity, rotation) so I can create visually rich and varied designs.

**Why this priority**: Enables professional-looking designs with visual depth. Essential for creating earth-tone geometric trees, semi-transparent overlays, and rotated elements.

**Independent Test**: Can be fully tested by creating shapes with each property (opacity 0.5, rotation 45deg, thick stroke, etc.) and visually verifying each property renders correctly.

**Acceptance Scenarios**:

1. **Given** a shape with opacity 0.5, **When** the card is generated, **Then** the shape renders semi-transparent allowing underlying content to show through
2. **Given** a shape with rotation 45, **When** the card is generated, **Then** the shape rotates 45 degrees clockwise around its center
3. **Given** a shape with stroke_width 3 and stroke_color, **When** the card is generated, **Then** the shape has a 3-point border in the specified color
4. **Given** a shape with fill_color but no stroke, **When** the card is generated, **Then** the shape renders solid with no border
5. **Given** a shape with stroke but no fill, **When** the card is generated, **Then** the shape renders as an outline only

---

### User Story 4 - Pre-built Decorative Elements (Priority: P2)

As a card creator, I want to use pre-built decorative elements (Christmas trees, ornaments, gift boxes, stars) so I can quickly create professional holiday cards without manually composing shapes.

**Why this priority**: Major productivity boost. Users can create sophisticated designs without understanding shape composition. Enables non-technical users to create professional cards.

**Independent Test**: Can be fully tested by creating templates using each decorative element type, generating PDFs, and verifying elements render as expected compositions.

**Acceptance Scenarios**:

1. **Given** a template with a "geometric_tree" decorative element, **When** the card is generated, **Then** a multi-triangle Christmas tree with ornaments renders at the specified position
2. **Given** a template with an "ornament_bauble" element, **When** the card is generated, **Then** a circular ornament with highlight and hanger renders correctly
3. **Given** a template with a "gift_box" element, **When** the card is generated, **Then** a box with ribbon and bow renders at the specified position
4. **Given** a template with a "star" decorative element, **When** the card is generated, **Then** a multi-pointed star renders correctly
5. **Given** a template with multiple decorative elements, **When** the card is generated, **Then** all elements respect z-index ordering

---

### User Story 5 - Decorative Element Customization (Priority: P3)

As a card creator, I want to customize decorative elements by scaling, rotating, and recoloring them so I can adapt pre-built elements to my specific design needs.

**Why this priority**: Increases flexibility and reusability of decorative elements. Lower priority because basic element usage (P2) already delivers value.

**Independent Test**: Can be fully tested by creating decorative elements with scale, rotation, and color overrides, then verifying proportional scaling and correct color application.

**Acceptance Scenarios**:

1. **Given** a decorative element with scale 1.5, **When** the card is generated, **Then** the element renders 50% larger while maintaining proportions
2. **Given** a decorative element with rotation 30, **When** the card is generated, **Then** the entire element rotates 30 degrees as a unit
3. **Given** a decorative element with color_palette override, **When** the card is generated, **Then** element colors use the override palette instead of defaults
4. **Given** a decorative element with scale 0.5, **When** the card is generated, **Then** the element renders at half size while maintaining visual quality

---

### User Story 6 - YAML Template Definition (Priority: P1)

As a template designer, I want to define shape_elements and decorative_elements in YAML templates so I can create reusable sophisticated card designs without modifying source code.

**Why this priority**: Critical for Configuration-Driven Design principle. Without YAML support, feature violates constitution and cannot be used by non-developers.

**Independent Test**: Can be fully tested by creating a YAML template with shape_elements and decorative_elements, loading it via CLI, generating a card, and verifying correct rendering.

**Acceptance Scenarios**:

1. **Given** a YAML template with shape_elements list, **When** the template is loaded, **Then** all shape definitions parse correctly and validate via Pydantic
2. **Given** a YAML template with decorative_elements list, **When** the template is loaded, **Then** all decorative element definitions parse correctly
3. **Given** a YAML template with invalid shape properties, **When** the template is loaded, **Then** clear validation error messages identify the issues
4. **Given** a YAML template mixing shapes, decorative elements, text, and images, **When** the card is generated, **Then** all elements render with correct z-index ordering
5. **Given** an existing template without shape_elements, **When** the template is loaded, **Then** backward compatibility is maintained and card generates correctly

---

### Edge Cases

- What happens when a shape extends beyond panel boundaries? (Should clip to panel or warn)
- How does the system handle invalid z-index values (negative, non-integer)? (Validation error)
- What happens when overlapping opaque shapes have conflicting fill colors? (Top shape wins, correct layering)
- How does rotation affect bounding box calculations for positioning? (Rotate around center point)
- What happens when decorative element scale is 0 or negative? (Validation error)
- How does the system handle very large numbers of shapes (100+)? (Performance consideration, should work but may be slow)
- What happens when stroke_width exceeds shape dimensions? (Stroke may extend beyond or overlap)
- How does opacity interact with overlapping shapes? (Cumulative transparency)
- What happens when decorative elements reference undefined color palette entries? (Use default or validation error)
- How does the system handle circular references in element compositions? (Validation error during loading)

## Requirements *(mandatory)*

### Functional Requirements

#### Shape Primitives

- **FR-001**: System MUST support rendering Rectangle shapes with x, y, width, height properties in inches
- **FR-002**: System MUST support rendering Circle shapes with center_x, center_y, radius properties in inches
- **FR-003**: System MUST support rendering Triangle shapes with three vertex coordinates (x1, y1, x2, y2, x3, y3) in inches
- **FR-004**: System MUST support rendering Star shapes with center_x, center_y, outer_radius, inner_radius, points properties
- **FR-005**: System MUST support rendering Line shapes with start_x, start_y, end_x, end_y properties in inches

#### Shape Styling

- **FR-006**: All shapes MUST support fill_color property accepting hex color codes (e.g., "#A8B5A0")
- **FR-007**: All shapes MUST support stroke_color property accepting hex color codes
- **FR-008**: All shapes MUST support stroke_width property in points (default: 0 for no stroke)
- **FR-009**: All shapes MUST support opacity property as float 0.0-1.0 (default: 1.0 fully opaque)
- **FR-010**: All shapes MUST support rotation property in degrees 0-360 (default: 0)

#### Layering and Positioning

- **FR-011**: All shape and decorative elements MUST support z_index property as integer (default: 0)
- **FR-012**: System MUST render elements in z_index order from lowest to highest (higher z_index on top)
- **FR-013**: Elements with identical z_index MUST render in definition order (later elements on top)
- **FR-014**: Shape positioning MUST respect panel boundaries and 0.25" safe margin
- **FR-015**: All measurements MUST use inches as primary unit, converted to PDF points (72 pts/inch) at render time

#### Decorative Elements

- **FR-016**: System MUST provide at least 10 pre-built decorative elements in initial release
- **FR-017**: Decorative elements MUST include: geometric_tree, traditional_tree, ornament_bauble, ornament_star, gift_box, wreath, star_topper, snowflake, menorah, dreidel
- **FR-018**: Each decorative element MUST be defined as a composition of basic shapes
- **FR-019**: Decorative elements MUST support position (x, y), scale, and rotation properties
- **FR-020**: Decorative elements MUST support color_palette property to override default colors

#### Template Integration

- **FR-021**: YAML templates MUST support shape_elements list defining basic shapes
- **FR-022**: YAML templates MUST support decorative_elements list defining decorative compositions
- **FR-023**: Shape element definitions MUST validate via Pydantic models matching Shape types
- **FR-024**: Templates without shape_elements or decorative_elements MUST load and render correctly (backward compatibility)
- **FR-025**: Template loading MUST provide clear validation error messages for invalid shape/element definitions

#### Rendering

- **FR-026**: System MUST use ReportLab drawing primitives (rect, circle, polygon, wedge, line) for shape rendering
- **FR-027**: Shape rendering MUST respect panel clip boundaries to prevent content overflow
- **FR-028**: Opacity rendering MUST support alpha blending for overlapping semi-transparent shapes
- **FR-029**: Rotation MUST rotate shapes around their geometric center point
- **FR-030**: All shapes MUST render with print-quality precision (no aliasing or pixelation in PDF output)

### Key Entities

- **Shape**: Abstract base representing a geometric primitive with position, styling (fill_color, stroke_color, stroke_width, opacity, rotation), and layering (z_index). Concrete types: Rectangle, Circle, Triangle, Star, Line.

- **DecorativeElement**: Composition of multiple shapes forming a cohesive design unit. Has position (x, y), scale (proportional multiplier), rotation, color_palette (mapping of color roles to hex codes), and internal shape definitions with relative positioning.

- **ShapeElement**: Union type representing either a basic Shape or a DecorativeElement, enabling polymorphic rendering in the template system.

- **Panel**: Existing entity extended to support optional shape_elements list (list of ShapeElement) that render before/after other content based on z_index.

- **CardTemplate**: Existing entity extended to support shape_elements and decorative_elements at template level, defining reusable vector graphics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Templates can include at least 5 distinct basic shape types (Rectangle, Circle, Triangle, Star, Line) that render correctly in generated PDFs
- **SC-002**: Z-index layering works correctly with 10+ overlapping shapes, verified through visual regression testing against reference PDFs
- **SC-003**: At least 10 pre-built decorative elements are available and render correctly across different scales (0.5x to 2.0x)
- **SC-004**: A new "geometric_christmas_tree" reference template demonstrates the capability with overlapping triangles, ornaments, star topper, and gift box
- **SC-005**: All existing templates (001-holiday-card-generator) continue to load and generate correctly (100% backward compatibility)
- **SC-006**: Shape rendering maintains print accuracy within 1mm tolerance of specified positions
- **SC-007**: Opacity blending renders correctly for at least 3 overlapping semi-transparent shapes (verified visually)
- **SC-008**: All shape types support rotation 0-360 degrees rendering correctly in 45-degree increments
- **SC-009**: YAML schema validation provides clear error messages for at least 10 common shape definition mistakes
- **SC-010**: Visual regression test suite includes reference cards for each shape type, decorative element, and the geometric tree composition
