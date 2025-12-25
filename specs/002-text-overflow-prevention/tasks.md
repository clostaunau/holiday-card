# Tasks: Text Overflow Prevention

**Input**: Design documents from `/workspaces/holiday-card/specs/002-text-overflow-prevention/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ N/A

**Organization**: Tasks are grouped by user story (P1-P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- File paths are absolute from repository root: `/workspaces/holiday-card/`

---

## Phase 1: Foundation (Shared Infrastructure)

**Purpose**: Core data models and utilities that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T001 [P] [Foundation] Add `OverflowStrategy` enum to `/workspaces/holiday-card/src/holiday_card/core/models.py`
  - Values: AUTO, SHRINK, WRAP, TRUNCATE
  - Inherit from `str, Enum` pattern (consistent with existing enums)

- [ ] T002 [P] [Foundation] Add `AdjustmentResult` model to `/workspaces/holiday-card/src/holiday_card/core/models.py`
  - Fields: was_adjusted, strategy_applied, original_font_size, final_font_size, lines_used, content_truncated
  - Pydantic BaseModel with validation

- [ ] T003 [Foundation] Enhance `TextElement` model in `/workspaces/holiday-card/src/holiday_card/core/models.py`
  - Add: overflow_strategy (default AUTO), max_lines (optional), min_font_size (default 8)
  - Add: _adjustment_applied private field (PrivateAttr)
  - Add: get_adjustment_result() and set_adjustment_result() methods
  - Depends on: T001 (OverflowStrategy), T002 (AdjustmentResult)

- [ ] T004 [P] [Foundation] Create `/workspaces/holiday-card/src/holiday_card/core/text_utils.py` module
  - Create empty module with docstring
  - Add TextMetrics model (width_pts, height_pts, line_count, fits_within_bounds)

- [ ] T005 [P] [Foundation] Add unit tests for new models in `/workspaces/holiday-card/tests/unit/test_models.py`
  - test_overflow_strategy_enum_values()
  - test_adjustment_result_creation()
  - test_text_element_overflow_strategy_default()
  - test_text_element_overflow_strategy_validation()

**Checkpoint**: Foundation complete - Core models ready for implementation

---

## Phase 2: User Story 1 - Automatic Text Fitting via Font Size Reduction (Priority: P1) 🎯 MVP

**Goal**: Detect text overflow and automatically reduce font size until text fits within boundaries (minimum 8pt)

**Independent Test**: Create a card with long text (e.g., "Merry Christmas and Happy New Year to Everyone!") at large font size, verify font auto-reduces to fit within designated width

### Unit Tests for User Story 1 (TDD: Write tests FIRST)

- [ ] T006 [P] [US1] Create `/workspaces/holiday-card/tests/unit/test_text_utils.py`
  - test_measure_text_width_single_line() - Basic width measurement
  - test_measure_text_returns_metrics() - TextMetrics structure

- [ ] T007 [P] [US1] Add shrink algorithm tests to `/workspaces/holiday-card/tests/unit/test_text_utils.py`
  - test_shrink_to_fit_reduces_font_size() - Oversized text shrinks
  - test_shrink_to_fit_returns_original_if_fits() - Undersized text unchanged
  - test_shrink_to_fit_enforces_minimum() - 8pt minimum enforced
  - test_shrink_to_fit_binary_search_efficiency() - <10 iterations

### Implementation for User Story 1

- [ ] T008 [US1] Implement `measure_text()` in `/workspaces/holiday-card/src/holiday_card/core/text_utils.py`
  - Function signature: `measure_text(canvas, content, font_name, font_size, max_width, max_height=None) -> TextMetrics`
  - Use `canvas.stringWidth()` for width calculation
  - Calculate height as font_size * 1.2 for single line
  - Return TextMetrics with fits_within_bounds flag
  - Depends on: T004 (TextMetrics model)

- [ ] T009 [US1] Implement `shrink_to_fit()` in `/workspaces/holiday-card/src/holiday_card/core/text_utils.py`
  - Function signature: `shrink_to_fit(canvas, content, font_name, initial_size, max_width, min_size=8) -> int`
  - Binary search algorithm (research.md decision #2)
  - Use measure_text() for width checking
  - Return final font size (may equal min_size)
  - Depends on: T008 (measure_text)

- [ ] T010 [US1] Implement `_apply_shrink_strategy()` in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Method signature: `_apply_shrink_strategy(text: TextElement, panel: Panel) -> tuple[int, str]`
  - Call shrink_to_fit() to get adjusted font size
  - Return (final_font_size, original_content)
  - Handle edge case: if shrunk to min and still overflows, truncate
  - Depends on: T009 (shrink_to_fit)

- [ ] T011 [US1] Implement `_select_auto_strategy()` in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Method signature: `_select_auto_strategy(text: TextElement) -> OverflowStrategy`
  - Heuristic: len(content) < 30 → SHRINK, else → WRAP if height specified, else SHRINK
  - Based on research.md decision #5

- [ ] T012 [US1] Replace `_handle_text_overflow()` with `_fit_text_element()` in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Method signature: `_fit_text_element(text: TextElement, panel: Panel) -> tuple[int, list[str], AdjustmentResult]`
  - Check if overflow_strategy is AUTO, call _select_auto_strategy()
  - Route to _apply_shrink_strategy() when SHRINK selected
  - Create AdjustmentResult tracking what was done
  - Return (font_size, [content], adjustment_result)
  - Depends on: T010 (_apply_shrink_strategy), T011 (_select_auto_strategy)

- [ ] T013 [US1] Update `render_text()` in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Replace call to `_handle_text_overflow()` with `_fit_text_element()`
  - Use returned font_size for rendering
  - Store adjustment_result via text.set_adjustment_result()
  - Preserve existing alignment, color, rotation logic
  - Depends on: T012 (_fit_text_element)

### Integration Tests for User Story 1

- [ ] T014 [US1] Add overflow tests to `/workspaces/holiday-card/tests/integration/test_card_generation.py`
  - test_overflow_shrink_long_greeting() - Long greeting auto-shrinks
  - test_overflow_no_adjustment_short_text() - Short text unchanged
  - test_overflow_min_font_size_enforced() - Extreme text hits 8pt minimum
  - Generate actual PDFs, verify no exceptions

### Visual Regression Tests for User Story 1

- [ ] T015 [US1] Create test templates in `/workspaces/holiday-card/tests/fixtures/test_templates/`
  - Create overflow-shrink-test.yaml with long greeting text
  - Set width constraint that requires shrinking

- [ ] T016 [US1] Add visual tests to `/workspaces/holiday-card/tests/integration/test_visual_regression.py`
  - test_visual_shrink_strategy() - Generate PDF, compare to reference
  - Store reference PDF in `/workspaces/holiday-card/tests/fixtures/reference_cards/overflow_scenarios/shrink.pdf`

**Checkpoint**: User Story 1 (SHRINK strategy) fully functional - MVP complete!

---

## Phase 3: User Story 2 - Multi-Line Text Wrapping (Priority: P2)

**Goal**: Wrap long text across multiple lines to fit within width boundary while respecting height constraints

**Independent Test**: Create card with long inside message, verify text wraps to multiple lines and all lines fit within panel boundaries

### Unit Tests for User Story 2 (TDD: Write tests FIRST)

- [ ] T017 [P] [US2] Add wrapping tests to `/workspaces/holiday-card/tests/unit/test_text_utils.py`
  - test_wrap_text_at_word_boundaries() - Text wraps at spaces
  - test_wrap_text_single_word_exceeds_width() - Long word forced to single line
  - test_wrap_text_respects_max_lines() - Line limit enforced
  - test_wrap_text_returns_list_of_lines() - Output format

- [ ] T018 [P] [US2] Add line height tests to `/workspaces/holiday-card/tests/unit/test_text_utils.py`
  - test_calculate_line_height() - Returns 1.2x font size
  - test_measure_text_height_multi_line() - Height calculation for wrapped text

### Implementation for User Story 2

- [ ] T019 [US2] Implement `calculate_line_height()` in `/workspaces/holiday-card/src/holiday_card/core/text_utils.py`
  - Function signature: `calculate_line_height(font_size_pt: int) -> float`
  - Return font_size * 1.2 (research.md decision #6)

- [ ] T020 [US2] Implement `wrap_text()` in `/workspaces/holiday-card/src/holiday_card/core/text_utils.py`
  - Function signature: `wrap_text(canvas, content, font_name, font_size, max_width, max_lines=None) -> list[str]`
  - Word boundary wrapping algorithm (research.md decision #3)
  - Use measure_text() to check each line width
  - Return list of wrapped lines
  - Depends on: T008 (measure_text), T019 (calculate_line_height)

- [ ] T021 [US2] Update `measure_text()` to support multi-line in `/workspaces/holiday-card/src/holiday_card/core/text_utils.py`
  - Accept lines parameter: `measure_text(canvas, content, font_name, font_size, max_width, max_height=None, lines=None)`
  - If lines provided, calculate total height using calculate_line_height()
  - Update TextMetrics.line_count
  - Depends on: T019 (calculate_line_height)

- [ ] T022 [US2] Implement `_apply_wrap_strategy()` in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Method signature: `_apply_wrap_strategy(text: TextElement, panel: Panel) -> tuple[int, list[str]]`
  - Call wrap_text() to get wrapped lines
  - Check if wrapped text fits within height (if specified)
  - If doesn't fit, reduce font size and re-wrap
  - Return (final_font_size, wrapped_lines)
  - Depends on: T020 (wrap_text), T021 (measure multi-line)

- [ ] T023 [US2] Update `_fit_text_element()` to handle WRAP strategy in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Add routing to _apply_wrap_strategy() when WRAP selected
  - Create AdjustmentResult with lines_used count
  - Depends on: T022 (_apply_wrap_strategy)

- [ ] T024 [US2] Update `render_text()` to render multi-line text in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Handle list of lines from _fit_text_element()
  - Calculate y position for each line (subtract line_height)
  - Render each line with proper alignment
  - Depends on: T023 (WRAP routing)

### Integration Tests for User Story 2

- [ ] T025 [US2] Add wrap tests to `/workspaces/holiday-card/tests/integration/test_card_generation.py`
  - test_overflow_wrap_long_message() - Long message wraps to multiple lines
  - test_overflow_wrap_respects_height() - Wrapped text fits within height constraint
  - test_overflow_wrap_shrinks_if_needed() - Font reduced if wrapping exceeds height

### Visual Regression Tests for User Story 2

- [ ] T026 [US2] Create wrap test template in `/workspaces/holiday-card/tests/fixtures/test_templates/`
  - Create overflow-wrap-test.yaml with long multi-sentence message
  - Set width and height constraints

- [ ] T027 [US2] Add visual wrap test to `/workspaces/holiday-card/tests/integration/test_visual_regression.py`
  - test_visual_wrap_strategy() - Generate PDF with wrapped text, compare to reference
  - Store reference in `/workspaces/holiday-card/tests/fixtures/reference_cards/overflow_scenarios/wrap.pdf`

**Checkpoint**: User Story 2 (WRAP strategy) fully functional

---

## Phase 4: User Story 3 - Configurable Overflow Strategy (Priority: P2)

**Goal**: Allow users to explicitly configure overflow strategy (shrink/wrap/truncate/auto) per text element in templates

**Independent Test**: Create templates with explicit overflow_strategy values, verify each behaves according to its configuration

### Unit Tests for User Story 3 (TDD: Write tests FIRST)

- [ ] T028 [P] [US3] Add strategy selection tests to `/workspaces/holiday-card/tests/unit/test_renderer.py`
  - test_explicit_shrink_strategy_applied() - Configured SHRINK strategy used
  - test_explicit_wrap_strategy_applied() - Configured WRAP strategy used
  - test_explicit_truncate_strategy_applied() - Configured TRUNCATE strategy used
  - test_auto_strategy_selects_appropriate() - AUTO picks SHRINK or WRAP based on heuristic

### Implementation for User Story 3

- [ ] T029 [US3] Implement `_apply_truncate_strategy()` in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Method signature: `_apply_truncate_strategy(text: TextElement, panel: Panel) -> tuple[int, str]`
  - Reuse existing `_handle_text_overflow()` logic (lines 295-326 in reportlab_renderer.py)
  - Binary search for truncation point with ellipsis
  - Return (original_font_size, truncated_content)

- [ ] T030 [US3] Update `_fit_text_element()` to handle TRUNCATE strategy in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Add routing to _apply_truncate_strategy() when TRUNCATE selected
  - Create AdjustmentResult with content_truncated flag
  - Depends on: T029 (_apply_truncate_strategy)

- [ ] T031 [US3] Update `_select_auto_strategy()` heuristic in `/workspaces/holiday-card/src/holiday_card/renderers/reportlab_renderer.py`
  - Refine logic based on research.md decision #5
  - Consider: text length, has height constraint, panel position
  - Document heuristic clearly in docstring

### Integration Tests for User Story 3

- [ ] T032 [US3] Add strategy configuration tests to `/workspaces/holiday-card/tests/integration/test_card_generation.py`
  - test_explicit_strategy_overrides_auto() - Configured strategy takes precedence
  - test_mixed_strategies_same_card() - Different elements use different strategies
  - test_auto_strategy_adapts_to_text_length() - AUTO picks correctly

### Template Updates for User Story 3

- [ ] T033 [P] [US3] Update `/workspaces/holiday-card/templates/christmas/classic.yaml`
  - Add overflow_strategy: "shrink" to front greeting
  - Add overflow_strategy: "wrap" to inside message
  - Add width constraints where missing

- [ ] T034 [P] [US3] Update `/workspaces/holiday-card/templates/christmas/modern.yaml`
  - Add overflow_strategy configuration
  - Add width constraints

- [ ] T035 [P] [US3] Update `/workspaces/holiday-card/templates/birthday/balloons.yaml`
  - Add overflow_strategy configuration
  - Add width constraints

- [ ] T036 [P] [US3] Update `/workspaces/holiday-card/templates/hanukkah/menorah.yaml`
  - Add overflow_strategy configuration
  - Add width constraints

- [ ] T037 [P] [US3] Update `/workspaces/holiday-card/templates/generic/celebration.yaml`
  - Add overflow_strategy configuration
  - Add width constraints

**Checkpoint**: User Story 3 (configurable strategies) fully functional

---

## Phase 5: User Story 4 - Visual Overflow Warnings in Preview (Priority: P3) [OPTIONAL]

**Goal**: Preview mode shows visual indicators for text elements that were automatically adjusted

**Status**: Deferred to future release - requires preview renderer enhancements

**Tasks**: Not included in initial implementation (P1/P2 sufficient for MVP++)

---

## Phase 6: User Story 5 - Boundary Enforcement Configuration (Priority: P3) [OPTIONAL]

**Goal**: Strict vs. relaxed boundary enforcement modes

**Status**: Deferred to future release - strict mode is sufficient for initial release

**Tasks**: Not included in initial implementation (P1/P2 sufficient for MVP++)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality improvements across all implemented user stories

- [ ] T038 [P] [Polish] Add property-based tests in `/workspaces/holiday-card/tests/unit/test_overflow_properties.py`
  - Use Hypothesis library
  - test_shrink_always_fits_property() - Any text shrunk to 8pt+ fits
  - test_wrap_never_exceeds_max_lines_property() - Wrapped text respects limits
  - test_truncate_never_overflows_property() - Truncated text always fits

- [ ] T039 [P] [Polish] Performance profiling tests in `/workspaces/holiday-card/tests/integration/test_performance.py`
  - test_overflow_adjustment_under_100ms() - Per-element performance
  - test_card_generation_under_10s() - End-to-end performance
  - Profile shrink algorithm iterations, wrap calculations

- [ ] T040 [Polish] Update `/workspaces/holiday-card/CLAUDE.md` with new feature
  - Add "Text overflow prevention with configurable strategies" to recent changes
  - Document overflow_strategy configuration option

- [ ] T041 [Polish] Add overflow examples to `/workspaces/holiday-card/specs/002-text-overflow-prevention/quickstart.md`
  - Already created, verify completeness
  - Add troubleshooting scenarios

- [ ] T042 [P] [Polish] Code cleanup and linting
  - Run ruff check on all modified files
  - Run mypy type checking
  - Fix any linting issues

- [ ] T043 [Polish] Visual regression test for all templates
  - test_all_templates_no_overflow() - Generate PDFs for all 5 templates
  - Verify no text exceeds boundaries
  - Compare against reference PDFs

**Checkpoint**: Feature complete, tested, documented, and production-ready

---

## Dependencies & Execution Order

### Phase Dependencies

1. **Foundation (Phase 1)**: No dependencies - START HERE
2. **User Story 1 (Phase 2)**: Depends on Foundation complete
3. **User Story 2 (Phase 3)**: Depends on Foundation + US1 (uses shrink as fallback)
4. **User Story 3 (Phase 4)**: Depends on US1 + US2 (routes to their strategies)
5. **Polish (Phase 7)**: Depends on all implemented user stories

### Critical Path

```
Foundation (T001-T005)
    ↓
US1 Implementation (T006-T013)
    ↓
US1 Tests (T014-T016) ← MVP CHECKPOINT
    ↓
US2 Implementation (T017-T024)
    ↓
US2 Tests (T025-T027)
    ↓
US3 Implementation (T028-T031)
    ↓
US3 Tests & Templates (T032-T037)
    ↓
Polish (T038-T043)
```

### Parallel Opportunities

**Within Foundation**:
- T001 (OverflowStrategy) ∥ T002 (AdjustmentResult) ∥ T004 (text_utils.py) ∥ T005 (tests)
- T003 depends on T001+T002

**Within US1 Tests**:
- T006 (test_text_utils.py creation) ∥ T007 (shrink tests)

**Within US1 Implementation**:
- Once T009 (shrink_to_fit) complete, T010+T011 can run parallel
- T012 depends on T010+T011

**Within US2 Tests**:
- T017 (wrap tests) ∥ T018 (line height tests)

**Within US2 Implementation**:
- T019 (line_height) ∥ T020 (wrap_text) can prepare in parallel, but T020 uses T019

**Within US3 Templates**:
- T033-T037 (all template updates) can run 100% parallel

**Within Polish**:
- T038 (property tests) ∥ T039 (performance) ∥ T040 (CLAUDE.md) ∥ T041 (quickstart) ∥ T042 (linting)

---

## Implementation Strategy

### Minimum Viable Product (MVP) - US1 Only

1. Complete Foundation (T001-T005) - ~2 hours
2. Complete US1 (T006-T016) - ~6 hours
3. **STOP and VALIDATE**: Test US1 independently
4. Deploy if sufficient (basic overflow prevention functional)

**Total MVP time**: ~8 hours

### MVP++ (US1 + US2) - Recommended

1. Complete Foundation (T001-T005)
2. Complete US1 (T006-T016) - SHRINK working
3. Complete US2 (T017-T027) - WRAP working
4. **VALIDATE**: Both strategies working independently
5. Deploy with full functionality (except explicit config)

**Total MVP++ time**: ~12 hours

### Full Feature (US1 + US2 + US3)

1. Complete Foundation
2. Complete US1 - SHRINK
3. Complete US2 - WRAP
4. Complete US3 - Configurable strategies + template updates
5. Complete Polish - Tests, docs, performance
6. **VALIDATE**: All strategies + configuration working
7. Deploy production-ready feature

**Total time**: ~16 hours

### Parallel Team Strategy (if 2 developers available)

**After Foundation completes**:
- Developer A: US1 (SHRINK) - T006-T016
- Developer B: US2 (WRAP) - T017-T027 (some dependency on US1)

**Then**:
- Developer A: US3 implementation - T028-T031
- Developer B: Template updates - T033-T037

**Finally**:
- Both: Polish tasks in parallel - T038-T042

**Total team time**: ~10 hours with 2 developers

---

## Notes

- Tests use TDD approach - write tests FIRST, ensure they FAIL, then implement
- Commit after each task or logical group of parallel tasks
- Each checkpoint should be validated independently
- US1 is fully functional MVP (core overflow prevention)
- US2 adds multi-line capability (important for messages)
- US3 adds configurability (polish)
- US4 and US5 deferred (P3, future releases)
- All tasks include absolute file paths for clarity
- Visual regression tests require reference PDFs (generate after implementation validated)

---

## Testing Validation Checklist

Before marking feature complete, verify:

- [ ] All unit tests pass (`pytest tests/unit/`)
- [ ] All integration tests pass (`pytest tests/integration/`)
- [ ] Visual regression tests pass (no unexpected differences)
- [ ] Property-based tests pass (Hypothesis)
- [ ] Performance tests meet <100ms/element requirement
- [ ] All existing tests still pass (backward compatibility)
- [ ] Manual testing: print actual cards, fold, verify no text cutoff
- [ ] All 5 templates generate without errors
- [ ] Code passes ruff linting
- [ ] Code passes mypy type checking
