# Tasks: Vector Graphics Enhancement

**Input**: Design documents from `/workspaces/holiday-card/specs/004-vector-graphics-enhancement/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Tests are included based on Constitution Principle VI (Visual Testing requirement)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project structure**: `src/holiday_card/`, `tests/` at repository root
- Paths use existing project layout (library-first architecture)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and foundational model structure

- [ ] T001 Add new ShapeType.SVG_PATH enum value to src/holiday_card/core/models.py
- [ ] T002 [P] Create src/holiday_card/utils/svg_parser.py module with SVGPathParser class skeleton
- [ ] T003 [P] Create src/holiday_card/utils/gradient_utils.py module with color interpolation utilities
- [ ] T004 [P] Create src/holiday_card/core/validators.py module for shared validation logic

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 [P] Implement ColorStop model in src/holiday_card/core/models.py with position and color validation
- [ ] T006 [P] Implement SolidFill model in src/holiday_card/core/models.py
- [ ] T007 [P] Implement LinearGradientFill model in src/holiday_card/core/models.py with stops validation
- [ ] T008 [P] Implement RadialGradientFill model in src/holiday_card/core/models.py with stops validation
- [ ] T009 [P] Implement PatternType enum and PatternFill model in src/holiday_card/core/models.py
- [ ] T010 Implement FillStyle discriminated union in src/holiday_card/core/models.py (combines T006-T009)
- [ ] T011 [P] Implement CircleClipMask model in src/holiday_card/core/models.py
- [ ] T012 [P] Implement RectangleClipMask model in src/holiday_card/core/models.py
- [ ] T013 [P] Implement EllipseClipMask model in src/holiday_card/core/models.py
- [ ] T014 [P] Implement StarClipMask model in src/holiday_card/core/models.py with inner < outer validation
- [ ] T015 [P] Implement SVGPathClipMask model in src/holiday_card/core/models.py with closed path validation
- [ ] T016 Implement ClipMask discriminated union in src/holiday_card/core/models.py (combines T011-T015)
- [ ] T017 Extend BaseShape model to add fill: Optional[FillStyle] field in src/holiday_card/core/models.py (maintain fill_color backward compatibility)
- [ ] T018 Extend ImageElement model to add clip_mask: Optional[ClipMask] field in src/holiday_card/core/models.py
- [ ] T019 [P] Update src/holiday_card/core/templates.py to parse FillStyle from YAML (support both legacy fill_color and new fill object)
- [ ] T020 [P] Update src/holiday_card/core/templates.py to parse ClipMask from YAML

**Checkpoint**: Foundation ready - all data models implemented, user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Import SVG Decorations (Priority: P1) 🎯 MVP

**Goal**: Enable importing SVG path-based decorations (holly leaves, detailed snowflakes, wreaths, ornate ornaments) to create more sophisticated holiday cards

**Independent Test**: Import a sample SVG file containing holly leaves, render a card, and verify the output matches the source design with correct fill and stroke colors

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T021 [P] [US1] Create unit test for SVG path data parsing in tests/unit/test_svg_parser.py (test M, L, C, Q, A, Z commands)
- [ ] T022 [P] [US1] Create unit test for SVGPath model validation in tests/unit/test_svg_models.py (test scale range, path syntax validation)
- [ ] T023 [P] [US1] Create test fixture holly_leaf.svg with sample SVG path data in tests/fixtures/sample_data/
- [ ] T024 [P] [US1] Create integration test for SVG rendering in tests/integration/test_svg_rendering.py (test end-to-end card generation with SVG path)
- [ ] T025 [US1] Create visual regression baseline tests/fixtures/reference_cards/svg_holly_leaf.pdf (run after T031 completes)

### Implementation for User Story 1

- [ ] T026 [P] [US1] Implement SVGPath model in src/holiday_card/core/models.py extending BaseShape with path_data and scale fields
- [ ] T027 [US1] Implement SVGPathParser.parse() method in src/holiday_card/utils/svg_parser.py to convert path data string to command list
- [ ] T028 [US1] Implement SVGPathParser._parse_move_command() for M/m commands in src/holiday_card/utils/svg_parser.py
- [ ] T029 [P] [US1] Implement SVGPathParser._parse_line_commands() for L/l/H/h/V/v commands in src/holiday_card/utils/svg_parser.py
- [ ] T030 [P] [US1] Implement SVGPathParser._parse_curve_commands() for C/c/S/s/Q/q/T/t commands in src/holiday_card/utils/svg_parser.py
- [ ] T031 [P] [US1] Implement SVGPathParser._parse_arc_command() for A/a commands in src/holiday_card/utils/svg_parser.py
- [ ] T032 [US1] Implement SVGPathParser._parse_close_command() for Z/z in src/holiday_card/utils/svg_parser.py
- [ ] T033 [US1] Add graceful degradation for unsupported SVG commands in SVGPathParser (log warning, skip command) per FR-006
- [ ] T034 [US1] Implement ShapeRenderer.render_svg_path() method in src/holiday_card/renderers/shape_renderer.py using ReportLab Path API
- [ ] T035 [US1] Add SVG path rendering support to ShapeRenderer.render_shape() dispatcher in src/holiday_card/renderers/shape_renderer.py
- [ ] T036 [US1] Update src/holiday_card/core/templates.py to parse SVGPath from YAML templates
- [ ] T037 [US1] Add validation and error handling for SVG path parsing errors in src/holiday_card/core/validators.py
- [ ] T038 [US1] Add logging for SVG path rendering operations (warnings for unsupported commands)
- [ ] T038a [US1] Create edge case test for SVG paths extending beyond safe margins in tests/integration/test_svg_rendering.py (verify clipping or warning behavior per spec.md edge case 5)

**Checkpoint**: At this point, SVG paths should render correctly in generated cards. Test with templates/christmas/holly_wreath.yaml example.

---

## Phase 4: User Story 2 - Apply Gradient Backgrounds (Priority: P2)

**Goal**: Enable linear and radial gradient fills for backgrounds and shapes to create modern designs with depth, sky backgrounds, sunset effects, and metallic appearances

**Independent Test**: Create a card with a linear gradient background and verify smooth color transitions. Create a card with radial gradient ornament and verify radiating colors from center.

### Tests for User Story 2

- [ ] T039 [P] [US2] Create unit test for ColorStop validation in tests/unit/test_gradient_models.py (test position range 0-1, color format)
- [ ] T040 [P] [US2] Create unit test for LinearGradientFill validation in tests/unit/test_gradient_models.py (test stops count, ascending order)
- [ ] T041 [P] [US2] Create unit test for RadialGradientFill validation in tests/unit/test_gradient_models.py
- [ ] T042 [P] [US2] Create unit test for color interpolation in tests/unit/test_gradient_utils.py
- [ ] T043 [P] [US2] Create integration test for linear gradient rendering in tests/integration/test_gradient_rendering.py
- [ ] T044 [P] [US2] Create integration test for radial gradient rendering in tests/integration/test_gradient_rendering.py
- [ ] T045 [P] [US2] Create visual regression baseline tests/fixtures/reference_cards/gradient_sunset.pdf (linear gradient)
- [ ] T046 [P] [US2] Create visual regression baseline tests/fixtures/reference_cards/gradient_ornament.pdf (radial gradient)

### Implementation for User Story 2

- [ ] T047 [US2] Create src/holiday_card/renderers/gradient_renderer.py module with GradientRenderer class
- [ ] T048 [US2] Implement GradientRenderer.render_linear_gradient() in src/holiday_card/renderers/gradient_renderer.py using ReportLab linearGradient API
- [ ] T049 [US2] Implement GradientRenderer.render_radial_gradient() in src/holiday_card/renderers/gradient_renderer.py using ReportLab radialGradient API
- [ ] T050 [US2] Implement gradient_endpoints() helper in src/holiday_card/utils/gradient_utils.py to convert angle to coordinates
- [ ] T051 [US2] Implement color_interpolation() helper in src/holiday_card/utils/gradient_utils.py for smooth color transitions
- [ ] T052 [US2] Update ShapeRenderer to detect fill.type and delegate to GradientRenderer when fill is LinearGradientFill or RadialGradientFill in src/holiday_card/renderers/shape_renderer.py
- [ ] T053 [US2] Add gradient fill validation in src/holiday_card/core/validators.py (minimum 2 stops, maximum 20 stops, positions ascending)
- [ ] T054 [US2] Add error handling for gradient rendering failures (fallback to solid fill with warning)
- [ ] T055 [US2] Add logging for gradient rendering operations (angle conversion, stop count)

**Checkpoint**: At this point, gradient fills should render smoothly on shapes. Test with templates/christmas/gradient_snowscape.yaml and templates/christmas/metallic_ornaments.yaml examples.

---

## Phase 5: User Story 3 - Clip Images to Shapes (Priority: P3)

**Goal**: Enable clipping photos and images to decorative shapes (circles, stars, custom paths) to create photo cards with elegant frames and collages

**Independent Test**: Place a photo on a card with a circular clipping mask and verify the image displays only within the circle boundary. Test with star mask and SVG path mask.

### Tests for User Story 3

- [ ] T056 [P] [US3] Create unit test for CircleClipMask validation in tests/unit/test_clipping_masks.py (test radius > 0)
- [ ] T057 [P] [US3] Create unit test for StarClipMask validation in tests/unit/test_clipping_masks.py (test inner < outer, points range)
- [ ] T058 [P] [US3] Create unit test for SVGPathClipMask validation in tests/unit/test_clipping_masks.py (test closed path requirement)
- [ ] T059 [P] [US3] Create test fixture test_photo.jpg sample image in tests/fixtures/sample_data/
- [ ] T060 [P] [US3] Create integration test for circular clipping in tests/integration/test_clipping_rendering.py
- [ ] T061 [P] [US3] Create integration test for star clipping in tests/integration/test_clipping_rendering.py
- [ ] T062 [P] [US3] Create integration test for SVG path clipping in tests/integration/test_clipping_rendering.py
- [ ] T063 [P] [US3] Create visual regression baseline tests/fixtures/reference_cards/photo_circle_clip.pdf
- [ ] T064 [P] [US3] Create visual regression baseline tests/fixtures/reference_cards/photo_star_clip.pdf

### Implementation for User Story 3

- [ ] T065 [US3] Create src/holiday_card/renderers/clipping_renderer.py module with ClippingRenderer class
- [ ] T066 [US3] Implement ClippingRenderer.create_circle_path() in src/holiday_card/renderers/clipping_renderer.py using ReportLab Path.circle()
- [ ] T067 [P] [US3] Implement ClippingRenderer.create_rectangle_path() in src/holiday_card/renderers/clipping_renderer.py
- [ ] T068 [P] [US3] Implement ClippingRenderer.create_ellipse_path() in src/holiday_card/renderers/clipping_renderer.py
- [ ] T069 [US3] Implement ClippingRenderer.create_star_path() in src/holiday_card/renderers/clipping_renderer.py (reuse Star shape logic)
- [ ] T070 [US3] Implement ClippingRenderer.create_svg_path() in src/holiday_card/renderers/clipping_renderer.py (reuse SVGPathParser)
- [ ] T071 [US3] Implement ClippingRenderer.apply_clip_mask() in src/holiday_card/renderers/clipping_renderer.py using canvas.clipPath()
- [ ] T072 [US3] Update ReportLabRenderer to detect ImageElement.clip_mask and apply clipping before drawImage() in src/holiday_card/renderers/reportlab_renderer.py
- [ ] T073 [US3] Add canvas state management (saveState/restoreState) for clipping contexts in src/holiday_card/renderers/clipping_renderer.py
- [ ] T074 [US3] Add clipping mask validation in src/holiday_card/core/validators.py (mask dimensions within image bounds)
- [ ] T075 [US3] Add error handling for invalid clipping masks (fallback to no clipping with warning)
- [ ] T076 [US3] Add logging for clipping operations (mask type, dimensions)

**Checkpoint**: At this point, images should clip correctly to various mask shapes. Test with templates/christmas/photo_ornament.yaml example.

---

## Phase 6: User Story 4 - Apply Pattern Fills (Priority: P4)

**Goal**: Enable repeating patterns (stripes, dots, plaid, checkerboard) for backgrounds and shapes to create festive designs reminiscent of wrapping paper and traditional holiday textiles

**Independent Test**: Create a card with a striped pattern background and verify the pattern repeats correctly across the surface. Test with polka dot and checkerboard patterns.

### Tests for User Story 4

- [ ] T077 [P] [US4] Create unit test for PatternFill validation in tests/unit/test_pattern_models.py (test pattern_type enum, spacing range, colors count)
- [ ] T078 [P] [US4] Create integration test for stripe pattern rendering in tests/integration/test_pattern_rendering.py
- [ ] T079 [P] [US4] Create integration test for dot pattern rendering in tests/integration/test_pattern_rendering.py
- [ ] T080 [P] [US4] Create integration test for grid pattern rendering in tests/integration/test_pattern_rendering.py
- [ ] T081 [P] [US4] Create integration test for checkerboard pattern rendering in tests/integration/test_pattern_rendering.py
- [ ] T082 [P] [US4] Create visual regression baseline tests/fixtures/reference_cards/stripe_pattern.pdf
- [ ] T083 [P] [US4] Create visual regression baseline tests/fixtures/reference_cards/dot_pattern.pdf

### Implementation for User Story 4

- [ ] T084 [US4] Create src/holiday_card/renderers/pattern_renderer.py module with PatternRenderer class
- [ ] T085 [US4] Implement PatternRenderer._create_stripe_tile() in src/holiday_card/renderers/pattern_renderer.py using beginForm/endForm
- [ ] T086 [P] [US4] Implement PatternRenderer._create_dot_tile() in src/holiday_card/renderers/pattern_renderer.py
- [ ] T087 [P] [US4] Implement PatternRenderer._create_grid_tile() in src/holiday_card/renderers/pattern_renderer.py
- [ ] T088 [P] [US4] Implement PatternRenderer._create_checkerboard_tile() in src/holiday_card/renderers/pattern_renderer.py
- [ ] T089 [US4] Implement PatternRenderer.render_pattern_fill() in src/holiday_card/renderers/pattern_renderer.py to create and apply pattern
- [ ] T090 [US4] Add pattern rotation and scaling transformations in src/holiday_card/renderers/pattern_renderer.py
- [ ] T091 [US4] Update ShapeRenderer to detect fill.type and delegate to PatternRenderer when fill is PatternFill in src/holiday_card/renderers/shape_renderer.py
- [ ] T092 [US4] Add pattern fill validation in src/holiday_card/core/validators.py (spacing range, scale range, valid colors)
- [ ] T093 [US4] Add edge case handling for very small shapes (auto-scale pattern or fallback to solid fill)
- [ ] T094 [US4] Add error handling for pattern rendering failures (fallback to solid fill with warning)
- [ ] T095 [US4] Add logging for pattern rendering operations (pattern type, tile dimensions)

**Checkpoint**: All user stories should now be independently functional. Pattern fills should render correctly across shapes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration, example templates, documentation, and performance validation

- [ ] T096 [P] Create templates/christmas/holly_wreath.yaml example template using SVG paths
- [ ] T097 [P] Create templates/christmas/gradient_snowscape.yaml example template using linear gradient
- [ ] T098 [P] Create templates/christmas/metallic_ornaments.yaml example template using radial gradients
- [ ] T099 [P] Create templates/christmas/photo_ornament.yaml example template using circular clipping mask
- [ ] T100 [P] Create templates/christmas/festive_stripes.yaml example template using stripe pattern
- [ ] T101 [P] Create templates/christmas/holiday_masterpiece.yaml example combining all features (per quickstart.md Scenario 6)
- [ ] T102 Run all visual regression tests and update baselines if needed in tests/fixtures/reference_cards/
- [ ] T103 [P] Add performance benchmarking for SVG path rendering (compare to basic shapes)
- [ ] T104 [P] Add performance benchmarking for gradient rendering
- [ ] T105 [P] Add performance benchmarking for clipping and pattern fills
- [ ] T106 Verify backward compatibility: Run all existing templates and ensure no regressions
- [ ] T107 [P] Update CLAUDE.md with vector graphics usage patterns and best practices
- [ ] T108 [P] Add docstrings to all new classes and methods (SVGPathParser, GradientRenderer, etc.)
- [ ] T109 Run ruff linting on all new/modified files (src/holiday_card/core/models.py, utils/, renderers/)
- [ ] T110 Run mypy type checking on all new/modified files
- [ ] T111 Validate all quickstart.md scenarios work end-to-end (6 scenarios)
- [ ] T112 Measure template coverage improvement (verify >=70% of commercial templates now achievable per SC-004)
- [ ] T112a Validate performance threshold: generation time <20% increase for templates using new features vs. baseline (per plan.md performance target PERF-001)
- [ ] T113 Code cleanup and refactoring for consistency across renderers

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User Story 1 (SVG Paths): Can start after Foundational - No dependencies on other stories
  - User Story 2 (Gradients): Can start after Foundational - No dependencies on other stories (can run parallel with US1)
  - User Story 3 (Clipping): Can start after Foundational - Depends on US1 for SVGPathClipMask support (can run parallel with US2)
  - User Story 4 (Patterns): Can start after Foundational - No dependencies on other stories (can run parallel with US1/US2/US3)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1 - SVG Paths)**: INDEPENDENT - Can complete and test standalone
- **User Story 2 (P2 - Gradients)**: INDEPENDENT - Can complete and test standalone, can apply gradients to SVG paths if US1 complete
- **User Story 3 (P3 - Clipping)**: WEAK DEPENDENCY on US1 - SVGPathClipMask reuses SVG parser, but can use basic shape masks independently
- **User Story 4 (P4 - Patterns)**: INDEPENDENT - Can complete and test standalone

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before parsers/renderers
- Core rendering logic before integration with ShapeRenderer
- Validation and error handling after core functionality
- Story complete and tested before moving to next priority

### Parallel Opportunities

- **Setup (Phase 1)**: T002, T003, T004 can run in parallel
- **Foundational (Phase 2)**:
  - T005-T009 (fill models) can run in parallel
  - T011-T015 (clip mask models) can run in parallel
  - T019, T020 (YAML parsing) can run in parallel
- **User Story 1 Tests**: T021-T024 can run in parallel
- **User Story 1 Implementation**: T029-T031 (SVG command parsers) can run in parallel after T027
- **User Story 2 Tests**: T039-T044 can run in parallel, T045-T046 baselines can run in parallel
- **User Story 2 Implementation**: T050, T051 (gradient utils) can run in parallel
- **User Story 3 Tests**: T056-T058, T060-T062 can run in parallel
- **User Story 3 Implementation**: T067-T068 (clip path creators) can run in parallel
- **User Story 4 Tests**: T078-T081 can run in parallel
- **User Story 4 Implementation**: T086-T088 (pattern tile creators) can run in parallel
- **Polish**: T096-T101 (example templates) can run in parallel, T103-T105 (benchmarks) can run in parallel
- **Different user stories can be worked on in parallel** once Foundational phase completes

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T021: "Create unit test for SVG path data parsing in tests/unit/test_svg_parser.py"
Task T022: "Create unit test for SVGPath model validation in tests/unit/test_svg_models.py"
Task T023: "Create test fixture holly_leaf.svg in tests/fixtures/sample_data/"
Task T024: "Create integration test for SVG rendering in tests/integration/test_svg_rendering.py"

# Launch all SVG command parsers together (after T027 completes):
Task T029: "Implement line commands parser in src/holiday_card/utils/svg_parser.py"
Task T030: "Implement curve commands parser in src/holiday_card/utils/svg_parser.py"
Task T031: "Implement arc command parser in src/holiday_card/utils/svg_parser.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T020) - CRITICAL foundation
3. Complete Phase 3: User Story 1 (T021-T038a) - SVG path import
4. **STOP and VALIDATE**: Test User Story 1 independently with holly_wreath.yaml template
5. Deploy/demo SVG path capability

**MVP Deliverable**: Users can import SVG-based decorative elements (holly leaves, snowflakes, wreaths) and generate professional-looking cards. Template coverage increases from ~25% to ~50%.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (T001-T020)
2. Add User Story 1 → Test independently → Deploy/Demo (MVP - ~50% coverage)
3. Add User Story 2 → Test independently → Deploy/Demo (~60% coverage with gradients)
4. Add User Story 3 → Test independently → Deploy/Demo (~75% coverage with photo cards)
5. Add User Story 4 → Test independently → Deploy/Demo (~80% coverage with festive patterns)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T020)
2. Once Foundational is done (after T020):
   - Developer A: User Story 1 (T021-T038a) - SVG paths
   - Developer B: User Story 2 (T039-T055) - Gradients
   - Developer C: User Story 4 (T077-T095) - Patterns
3. User Story 3 waits for US1 completion (SVG parser needed for SVGPathClipMask)
4. Stories integrate independently via shared FillStyle and ClipMask models

---

## Task Summary

**Total Tasks**: 115

**Tasks per User Story**:
- Setup: 4 tasks
- Foundational: 16 tasks (BLOCKS all stories)
- User Story 1 (SVG Paths): 19 tasks (MVP - includes T038a)
- User Story 2 (Gradients): 17 tasks
- User Story 3 (Clipping): 20 tasks
- User Story 4 (Patterns): 20 tasks
- Polish: 19 tasks (includes T112a)

**Parallel Opportunities**:
- 42 tasks marked [P] for parallel execution
- 4 user stories can run in parallel after Foundational phase (US1, US2, US4 fully independent; US3 has weak dependency on US1)

**Independent Test Criteria**:
- US1: Render card with holly leaf SVG, verify visual match
- US2: Render card with gradient sky, verify smooth color transitions
- US3: Render photo card with circular mask, verify clipping boundary
- US4: Render card with striped background, verify pattern repetition

**Suggested MVP Scope**: User Story 1 (SVG path import) - Delivers ~50% template coverage increase

**Format Validation**: ✓ All tasks follow checklist format with ID, [P] marker, [Story] label, and file paths

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Visual regression tests use pdf2image + imagehash per Constitution Principle VI
- Backward compatibility maintained via fill_color field coexistence with fill field
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Performance target: <20% generation time increase for templates using new features vs. basic templates
