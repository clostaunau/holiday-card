# Tasks: Holiday Card Generator

**Input**: Design documents from `/specs/001-holiday-card-generator/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/cli-interface.md, research.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure per plan.md (src/holiday_card/, templates/, themes/, tests/)
- [x] T002 Create pyproject.toml with dependencies (reportlab, Pillow, typer, PyYAML, pydantic) in pyproject.toml
- [x] T003 [P] Create package __init__.py with version in src/holiday_card/__init__.py
- [x] T004 [P] Create CLI entry point in src/holiday_card/__main__.py
- [x] T005 [P] Configure pytest in pyproject.toml [tool.pytest.ini_options]
- [x] T006 [P] Configure ruff linting in pyproject.toml [tool.ruff]
- [x] T007 [P] Configure mypy type checking in pyproject.toml [tool.mypy]
- [x] T008 [P] Create .gitignore with output/, .venv/, __pycache__/, *.pdf patterns
- [x] T009 [P] Create tests/conftest.py with shared pytest fixtures
- [x] T010 [P] Create output/ directory placeholder with .gitkeep

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T011 Implement measurement constants (PAGE_WIDTH, PAGE_HEIGHT, SAFE_MARGIN, POINTS_PER_INCH) in src/holiday_card/utils/measurements.py
- [x] T012 [P] Implement Color value object with RGB validation in src/holiday_card/core/models.py
- [x] T013 [P] Implement FoldType enum (half_fold, quarter_fold, tri_fold) in src/holiday_card/core/models.py
- [x] T014 [P] Implement OccasionType enum (christmas, hanukkah, birthday, generic) in src/holiday_card/core/models.py
- [x] T015 [P] Implement PanelPosition enum (front, back, inside_left, inside_right, center) in src/holiday_card/core/models.py
- [x] T016 Implement base Renderer protocol/ABC in src/holiday_card/renderers/base.py
- [x] T017 Create empty CLI app structure with Typer in src/holiday_card/cli/__init__.py
- [x] T018 Create src/holiday_card/cli/commands.py with app = typer.Typer() initialization
- [x] T019 Implement input validators (file path, color range, dimensions) in src/holiday_card/utils/validators.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Create a Simple Holiday Card (Priority: P1) MVP

**Goal**: User can select a template, add a greeting message, and generate a printable PDF with correct 8.5" x 11" dimensions and fold guides

**Independent Test**: Run `holiday-card create christmas-classic -m "Merry Christmas!"` and verify PDF output has correct page size and fold lines

### Implementation for User Story 1

- [x] T020 [P] [US1] Implement TextElement model with position, font, size, color in src/holiday_card/core/models.py
- [x] T021 [P] [US1] Implement Panel model with position, dimensions, text_elements in src/holiday_card/core/models.py
- [x] T022 [US1] Implement Template model with id, name, occasion, fold_type, panels in src/holiday_card/core/models.py
- [x] T023 [US1] Implement Card model with template_id, fold_type, panels, output_path in src/holiday_card/core/models.py
- [x] T024 [US1] Create YAML template loader in src/holiday_card/core/templates.py
- [x] T025 [US1] Implement template discovery (scan templates/ directory) in src/holiday_card/core/templates.py
- [x] T026 [US1] Create ReportLab PDF canvas setup (8.5" x 11" Letter size) in src/holiday_card/renderers/reportlab_renderer.py
- [x] T027 [US1] Implement fold line drawing for half_fold format in src/holiday_card/renderers/reportlab_renderer.py
- [x] T028 [US1] Implement panel layout calculation for half_fold in src/holiday_card/renderers/reportlab_renderer.py
- [x] T029 [US1] Implement text rendering with font and positioning in src/holiday_card/renderers/reportlab_renderer.py
- [x] T030 [US1] Implement CardGenerator class orchestrating template + renderer in src/holiday_card/core/generators.py
- [x] T031 [US1] Create christmas-classic template YAML in templates/christmas/classic.yaml
- [x] T032 [US1] Implement `holiday-card templates` command (list available templates) in src/holiday_card/cli/commands.py
- [x] T033 [US1] Implement `holiday-card create` command with --message option in src/holiday_card/cli/commands.py
- [x] T034 [US1] Add --output option to create command for custom output path in src/holiday_card/cli/commands.py
- [x] T035 [US1] Add error handling for missing template, invalid paths in src/holiday_card/cli/commands.py
- [x] T036 [US1] Add success output message with PDF path and card details in src/holiday_card/cli/commands.py

**Checkpoint**: User Story 1 complete - users can create basic half-fold cards from template

---

## Phase 4: User Story 2 - Customize Card Layout and Format (Priority: P2)

**Goal**: User can choose different fold formats (half, quarter, tri-fold) and customize text positioning and borders

**Independent Test**: Run `holiday-card create christmas-classic --fold-type quarter_fold` and verify output has correct 4-panel layout with proper orientations

### Implementation for User Story 2

- [x] T037 [P] [US2] Implement BorderStyle enum (solid, dashed, dotted, decorative) in src/holiday_card/core/models.py
- [x] T038 [P] [US2] Implement Border model with style, width, color, corner_radius in src/holiday_card/core/models.py
- [x] T039 [P] [US2] Implement FontStyle enum (normal, bold, italic, bold_italic) in src/holiday_card/core/models.py
- [x] T040 [P] [US2] Implement TextAlignment enum (left, center, right) in src/holiday_card/core/models.py
- [x] T041 [US2] Implement fold line drawing for quarter_fold format in src/holiday_card/renderers/reportlab_renderer.py
- [x] T042 [US2] Implement fold line drawing for tri_fold format in src/holiday_card/renderers/reportlab_renderer.py
- [x] T043 [US2] Implement panel layout calculation for quarter_fold (with rotation) in src/holiday_card/renderers/reportlab_renderer.py
- [x] T044 [US2] Implement panel layout calculation for tri_fold in src/holiday_card/renderers/reportlab_renderer.py
- [x] T045 [US2] Implement panel rotation (180 for quarter-fold back panel) in src/holiday_card/renderers/reportlab_renderer.py
- [x] T046 [US2] Implement border rendering (solid, dashed, dotted styles) in src/holiday_card/renderers/reportlab_renderer.py
- [x] T047 [US2] Implement text alignment options (left, center, right) in src/holiday_card/renderers/reportlab_renderer.py
- [x] T048 [US2] Implement font style variations (bold, italic) in src/holiday_card/renderers/reportlab_renderer.py
- [x] T049 [US2] Add --fold-type option to create command in src/holiday_card/cli/commands.py
- [x] T050 [US2] Create christmas-modern template (quarter_fold) in templates/christmas/modern.yaml
- [x] T051 [US2] Implement text overflow handling (truncation or scaling) in src/holiday_card/renderers/reportlab_renderer.py

**Checkpoint**: User Story 2 complete - users can create cards in any fold format with customized text

---

## Phase 5: User Story 3 - Add Custom Images and Graphics (Priority: P2)

**Goal**: User can add their own photos/graphics to cards with proper positioning and print-quality scaling

**Independent Test**: Run `holiday-card create christmas-classic --image ./photo.jpg` and verify image appears in PDF at correct position with proper resolution

### Implementation for User Story 3

- [x] T052 [P] [US3] Implement ImageElement model with source_path, position, size, preserve_aspect in src/holiday_card/core/models.py
- [x] T053 [US3] Implement image loading with Pillow in src/holiday_card/core/generators.py
- [x] T054 [US3] Implement image format validation (PNG, JPG only) in src/holiday_card/utils/validators.py
- [x] T055 [US3] Implement DPI validation (minimum 150 DPI warning) in src/holiday_card/utils/validators.py
- [x] T056 [US3] Implement aspect ratio preservation logic in src/holiday_card/renderers/reportlab_renderer.py
- [x] T057 [US3] Implement image rendering to PDF canvas in src/holiday_card/renderers/reportlab_renderer.py
- [x] T058 [US3] Implement safe margin enforcement for images (0.25" from edges) in src/holiday_card/renderers/reportlab_renderer.py
- [x] T059 [US3] Add --image option (repeatable) to create command in src/holiday_card/cli/commands.py
- [x] T060 [US3] Add error handling for corrupted/unsupported image files in src/holiday_card/cli/commands.py
- [x] T061 [US3] Create birthday-balloons template with image zone in templates/birthday/balloons.yaml

**Checkpoint**: User Story 3 complete - users can add images to their cards

---

## Phase 6: User Story 4 - Preview Card Before Printing (Priority: P3)

**Goal**: User can see a visual preview of their card design before generating the final PDF

**Independent Test**: Run `holiday-card preview christmas-classic --message "Test"` and verify PNG preview image is generated showing all panels

### Implementation for User Story 4

- [x] T062 [US4] Implement PreviewRenderer class in src/holiday_card/renderers/preview_renderer.py
- [x] T063 [US4] Implement PDF to image conversion using pdf2image in src/holiday_card/renderers/preview_renderer.py
- [x] T064 [US4] Implement fold line visualization in preview (highlighted guides) in src/holiday_card/renderers/preview_renderer.py
- [x] T065 [US4] Implement `holiday-card preview` command in src/holiday_card/cli/commands.py
- [x] T066 [US4] Add --dpi option to preview command (default 150) in src/holiday_card/cli/commands.py
- [x] T067 [US4] Add --format option to preview command (png, jpg) in src/holiday_card/cli/commands.py
- [x] T068 [US4] Add --show-guides option to preview command in src/holiday_card/cli/commands.py

**Checkpoint**: User Story 4 complete - users can preview cards before printing

---

## Phase 7: User Story 5 - Use Pre-defined Color Themes (Priority: P3)

**Goal**: User can apply coordinated color themes that automatically style the card design

**Independent Test**: Run `holiday-card create christmas-classic --theme winter-blue` and verify card uses blue color scheme instead of default red/green

### Implementation for User Story 5

- [x] T069 [P] [US5] Implement Theme model with colors (primary, secondary, background, text) in src/holiday_card/core/models.py
- [x] T070 [US5] Implement YAML theme loader in src/holiday_card/core/themes.py
- [x] T071 [US5] Implement theme discovery (scan themes/ directory) in src/holiday_card/core/themes.py
- [x] T072 [US5] Implement theme application to template colors in src/holiday_card/core/generators.py
- [x] T073 [US5] Implement theme color override for individual elements in src/holiday_card/renderers/reportlab_renderer.py
- [x] T074 [US5] Create christmas.yaml theme file (red-green, gold, winter-blue) in themes/christmas.yaml
- [x] T075 [US5] Create hanukkah.yaml theme file (blue-white, silver) in themes/hanukkah.yaml
- [x] T076 [US5] Create birthday.yaml theme file (pastel, bright, elegant) in themes/birthday.yaml
- [x] T077 [US5] Create generic.yaml theme file (neutral, celebration) in themes/generic.yaml
- [x] T078 [US5] Implement `holiday-card themes` command (list available themes) in src/holiday_card/cli/commands.py
- [x] T079 [US5] Add --theme option to create command in src/holiday_card/cli/commands.py
- [x] T080 [US5] Add --occasion filter to themes command in src/holiday_card/cli/commands.py

**Checkpoint**: User Story 5 complete - users can apply color themes to cards

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T081 [P] Create hanukkah-menorah template in templates/hanukkah/menorah.yaml
- [x] T082 [P] Create generic-celebration template in templates/generic/celebration.yaml
- [x] T083 [P] Add --format option (table, json, yaml) to templates command in src/holiday_card/cli/commands.py
- [x] T084 [P] Add --format option to themes command in src/holiday_card/cli/commands.py
- [x] T085 Implement `holiday-card init` command for custom templates in src/holiday_card/cli/commands.py
- [x] T086 Implement `holiday-card validate` command for template validation in src/holiday_card/cli/commands.py
- [x] T087 [P] Add --verbose and --quiet global options in src/holiday_card/cli/commands.py
- [x] T088 [P] Add environment variable support (HOLIDAY_CARD_TEMPLATES, HOLIDAY_CARD_OUTPUT) in src/holiday_card/cli/commands.py
- [x] T089 [P] Implement JSON output mode for create command in src/holiday_card/cli/commands.py
- [x] T090 Add comprehensive error messages with suggestions in src/holiday_card/cli/commands.py
- [x] T091 [P] Create unit tests for models in tests/unit/test_models.py
- [x] T092 [P] Create unit tests for measurement utilities in tests/unit/test_measurements.py
- [x] T093 [P] Create unit tests for validators in tests/unit/test_validators.py
- [x] T094 Create integration test for full card generation in tests/integration/test_full_generation.py
- [x] T095 Validate quickstart.md instructions work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1) should complete first as MVP
  - US2-US5 can proceed after US1 or in parallel if staffed
- **Polish (Phase 8)**: Can start after US1, ideally after all stories complete

### User Story Dependencies

| Story | Depends On | Can Parallelize With |
|-------|------------|----------------------|
| US1 (P1) | Foundational only | None (MVP first) |
| US2 (P2) | US1 (uses renderer) | US3 (different concerns) |
| US3 (P2) | US1 (uses renderer) | US2 (different concerns) |
| US4 (P3) | US1 (needs PDF output) | US5 (different concerns) |
| US5 (P3) | US1 (uses templates) | US4 (different concerns) |

### Within Each User Story

1. Models before services
2. Services before renderers
3. Renderers before CLI commands
4. Core implementation before error handling
5. Templates/themes created alongside their loaders

---

## Parallel Execution Examples

### Setup Phase (all [P] tasks together):
```bash
# These can run in parallel:
T003: Create package __init__.py
T004: Create CLI entry point
T005: Configure pytest
T006: Configure ruff
T007: Configure mypy
T008: Create .gitignore
T009: Create conftest.py
T010: Create output/ directory
```

### User Story 1 Models (parallel):
```bash
# These can run in parallel:
T020: Implement TextElement model
T021: Implement Panel model
```

### User Story 2 Enums (parallel):
```bash
# These can run in parallel:
T037: Implement BorderStyle enum
T038: Implement Border model
T039: Implement FontStyle enum
T040: Implement TextAlignment enum
```

### Polish Phase Tests (parallel):
```bash
# These can run in parallel:
T091: Unit tests for models
T092: Unit tests for measurements
T093: Unit tests for validators
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T010)
2. Complete Phase 2: Foundational (T011-T019)
3. Complete Phase 3: User Story 1 (T020-T036)
4. **STOP and VALIDATE**: Run `holiday-card create christmas-classic -m "Test"` and verify PDF
5. MVP is deployable!

### Incremental Delivery

| Milestone | Stories | Capabilities |
|-----------|---------|--------------|
| MVP | US1 | Basic card creation with templates |
| v1.1 | + US2 | Multiple fold formats, borders |
| v1.2 | + US3 | Custom images |
| v1.3 | + US4, US5 | Preview, color themes |
| v1.4 | + Polish | Full CLI, validation, tests |

### Task Counts

| Phase | Tasks | Parallelizable |
|-------|-------|----------------|
| Setup | 10 | 8 |
| Foundational | 9 | 5 |
| US1 (P1) | 17 | 2 |
| US2 (P2) | 15 | 4 |
| US3 (P2) | 10 | 1 |
| US4 (P3) | 7 | 0 |
| US5 (P3) | 12 | 1 |
| Polish | 15 | 9 |
| **Total** | **95** | **30** |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- **uncle-duke-python agent** available for Python guidance during implementation
- All measurements use inches, converted to points (72 pts/inch) for ReportLab
