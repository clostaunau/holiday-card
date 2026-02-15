# Implementation Plan: Text Overflow Prevention

**Branch**: `002-text-overflow-prevention` | **Date**: 2025-12-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/workspaces/holiday-card/specs/002-text-overflow-prevention/spec.md`

## Summary

Implement automatic text overflow prevention for holiday cards to ensure all text fits within designated boundaries. The system will detect overflow conditions and apply one of three strategies: font size reduction (shrink), multi-line wrapping (wrap), or truncation with ellipsis (truncate). This prevents text from extending past printable areas when cards are folded and printed.

**Technical Approach**: Enhance the existing `TextElement` model with overflow strategy configuration, implement a text fitting algorithm in the `ReportLabRenderer` that calculates text dimensions before rendering, and apply the appropriate adjustment strategy. The existing `_handle_text_overflow` method will be replaced with a more sophisticated system supporting multiple strategies.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ReportLab 4.0+ (PDF generation), Pydantic 2.0+ (model validation)
**Storage**: N/A (filesystem-based YAML templates)
**Testing**: pytest 7.0+, pdf2image (visual regression), imagehash (image comparison)
**Target Platform**: Linux/macOS/Windows (cross-platform CLI)
**Project Type**: Single project (library + CLI)
**Performance Goals**: Text overflow adjustment < 100ms per text element
**Constraints**: Minimum 8pt font size, 0.25" safe margins, print accuracy within 1mm tolerance
**Scale/Scope**: 5-10 templates, 1-10 text elements per card, typical text length 1-200 characters

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I - Library-First Architecture**: ✓ PASS
- Overflow detection logic implemented in `src/holiday_card/core/` (text_utils.py)
- Rendering strategy application in `src/holiday_card/renderers/reportlab_renderer.py`
- No CLI dependencies in core logic
- TextElement model enhancement in `src/holiday_card/core/models.py`

**Principle II - CLI-First Interface**: ✓ PASS
- No new CLI commands required (transparent enhancement to existing `generate` command)
- Overflow strategy configurable via YAML templates (no CLI changes)
- Users can override strategies programmatically if using library directly

**Principle III - Configuration-Driven Design**: ✓ PASS
- Overflow strategy stored in YAML template files (per text element)
- No code changes required for users to configure strategies
- Pydantic validation ensures valid strategy values

**Principle IV - Print Accuracy**: ✓ PASS
- Text fitting preserves 0.25" safe margin requirement
- Font size calculations use ReportLab's stringWidth API for accuracy
- Maintains existing measurement precision (inches → points at render time)

**Principle V - Simplicity**: ✓ PASS
- No new dependencies (uses existing ReportLab text measurement APIs)
- Enhances existing `_handle_text_overflow` method rather than adding complex abstraction
- Straightforward iterative shrinking algorithm
- Text wrapping uses ReportLab's built-in paragraph support

**Principle VI - Visual Testing**: ✓ PASS
- Visual regression tests will verify text fits within boundaries
- Reference PDFs will include overflow scenarios
- Existing test infrastructure (pdf2image + imagehash) sufficient

**Summary**: All constitution principles satisfied. No complexity violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/002-text-overflow-prevention/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Technical research (Phase 0)
├── data-model.md        # Data model changes (Phase 1)
├── quickstart.md        # Integration guide (Phase 1)
├── contracts/           # N/A (no external APIs)
└── tasks.md             # Task breakdown (Phase 2)
```

### Source Code (repository root)

```text
src/holiday_card/
├── core/
│   ├── models.py               # Enhanced TextElement with overflow_strategy field
│   ├── text_utils.py           # NEW: Text fitting algorithms (measure, shrink, wrap)
│   ├── generators.py           # No changes (uses renderer as-is)
│   ├── templates.py            # No changes (loads YAML as-is)
│   └── themes.py               # No changes
├── renderers/
│   ├── base.py                 # No changes (interface unchanged)
│   ├── reportlab_renderer.py   # MODIFIED: Enhanced text rendering with strategies
│   └── preview_renderer.py     # FUTURE: Add overflow indicators (P3)
└── utils/
    ├── measurements.py         # No changes
    └── validators.py           # No changes

tests/
├── unit/
│   ├── test_text_utils.py      # NEW: Unit tests for fitting algorithms
│   ├── test_models.py          # MODIFIED: Test TextElement.overflow_strategy
│   └── test_renderer.py        # MODIFIED: Test overflow strategy application
├── integration/
│   ├── test_card_generation.py # MODIFIED: End-to-end overflow scenarios
│   └── test_visual_regression.py # MODIFIED: Visual tests for text fitting
└── fixtures/
    ├── reference_cards/        # NEW: Reference PDFs with overflow scenarios
    └── test_templates/         # NEW: Templates with overflow test cases

templates/
├── christmas/
│   └── classic.yaml            # MODIFIED: Add overflow_strategy to text elements
├── birthday/
│   └── balloons.yaml           # MODIFIED: Add overflow_strategy
└── [other templates]           # MODIFIED: Add overflow_strategy
```

**Structure Decision**: Using existing single-project layout (src/ + tests/). The text overflow logic fits naturally into the existing architecture:
- Core domain models (`models.py`) get new fields
- New utility module (`text_utils.py`) for reusable fitting algorithms
- Renderer (`reportlab_renderer.py`) orchestrates strategy application
- Templates (YAML) configure per-element strategies

## Complexity Tracking

> **No constitution violations - this section intentionally empty**

---

## Phase 0: Research & Decisions

See [research.md](./research.md) for:
- ReportLab text measurement API investigation
- Font size reduction algorithm design
- Text wrapping approaches (simple vs. Paragraph API)
- Minimum font size threshold justification
- Strategy selection heuristics
- Performance profiling approach

**Key Decisions**:
1. Use ReportLab's `canvas.stringWidth()` for accurate text width calculation
2. Implement iterative binary search for font size reduction (faster than linear)
3. Use ReportLab's Flowables/Paragraph for multi-line wrapping
4. Minimum font size: 8pt (WCAG AA readability threshold)
5. Default strategy: "auto" - shrink for titles, wrap for messages, truncate for labels

---

## Phase 1: Architecture & Design

### Data Model Changes

See [data-model.md](./data-model.md) for full entity definitions.

**Enhanced Entities**:

1. **TextElement** (modified in `core/models.py`)
   - Add: `overflow_strategy: OverflowStrategy = OverflowStrategy.AUTO`
   - Add: `max_lines: Optional[int] = None` (for wrap strategy)
   - Add: `_adjustment_applied: Optional[AdjustmentResult] = None` (private, for preview)

2. **OverflowStrategy** (new enum in `core/models.py`)
   - Values: `AUTO`, `SHRINK`, `WRAP`, `TRUNCATE`
   - Default: `AUTO` (smart selection based on context)

3. **AdjustmentResult** (new model in `core/models.py`)
   - Fields: `original_font_size`, `final_font_size`, `lines_used`, `strategy_applied`, `was_adjusted`
   - Used for preview warnings (P3) and debugging

4. **TextMetrics** (new model in `core/text_utils.py`)
   - Fields: `width`, `height`, `line_count`, `fits_within_bounds`
   - Returned by measurement functions

### API Contracts

N/A - No external APIs. Internal Python API remains backward compatible:
- `CardGenerator.create_card()` - no signature changes
- `ReportLabRenderer.render_text()` - no signature changes (internal enhancements)
- Template YAML schema - backward compatible (overflow_strategy optional)

### Component Architecture

```
User Input (YAML template)
    ↓
Template Loader (core/templates.py)
    ↓ loads TextElement with overflow_strategy
Card Model (core/models.py)
    ↓ passed to
CardGenerator (core/generators.py)
    ↓ passed to
ReportLabRenderer (renderers/reportlab_renderer.py)
    ↓ calls
TextUtils.measure_text() ← Check if overflow
    ↓ if overflow detected
TextUtils.fit_text_with_strategy()
    ↓ returns adjusted font size / wrapped lines
render_text() ← Apply adjustment and render
    ↓
PDF Canvas (ReportLab)
```

**Key Modules**:

1. **text_utils.py** (NEW)
   - `measure_text(content, font_name, font_size, max_width, max_height) -> TextMetrics`
   - `shrink_to_fit(content, font_name, initial_size, max_width, min_size=8) -> int`
   - `wrap_text(content, font_name, font_size, max_width, max_lines) -> list[str]`
   - `calculate_line_height(font_size) -> float` (1.2x font size standard)

2. **reportlab_renderer.py** (MODIFIED)
   - Replace `_handle_text_overflow()` with `_fit_text_element()`
   - New: `_apply_shrink_strategy()`
   - New: `_apply_wrap_strategy()`
   - Keep: `_apply_truncate_strategy()` (existing logic)
   - New: `_select_auto_strategy()` (heuristic for AUTO mode)

3. **models.py** (MODIFIED)
   - Add `OverflowStrategy` enum
   - Add `AdjustmentResult` model
   - Enhance `TextElement` with overflow fields

### Integration Points

See [quickstart.md](./quickstart.md) for:
- How to configure overflow strategy in templates
- How to use overflow prevention programmatically
- How to test overflow scenarios
- How to interpret adjustment results

---

## Phase 2: Implementation Tasks

See [tasks.md](./tasks.md) for dependency-ordered task breakdown.

**High-Level Milestones**:
1. Data model enhancements (OverflowStrategy, TextElement fields)
2. Text measurement utilities (text_utils.py)
3. Font size reduction algorithm
4. Text wrapping algorithm
5. Strategy application in renderer
6. Template schema updates
7. Unit tests
8. Integration tests
9. Visual regression tests

---

## Phase 3: Testing Strategy

### Unit Tests

**test_text_utils.py**:
- `test_measure_text_width()` - Verify width calculation accuracy
- `test_measure_text_height()` - Verify height calculation for multi-line
- `test_shrink_to_fit_within_width()` - Test font reduction algorithm
- `test_shrink_to_fit_min_threshold()` - Ensure 8pt minimum enforced
- `test_wrap_text_at_word_boundaries()` - Verify wrapping logic
- `test_wrap_text_max_lines()` - Test line limit enforcement
- `test_calculate_line_height()` - Verify 1.2x spacing

**test_models.py**:
- `test_text_element_overflow_strategy_validation()` - Valid enum values
- `test_overflow_strategy_default_auto()` - Default value
- `test_adjustment_result_creation()` - Model instantiation

**test_renderer.py**:
- `test_apply_shrink_strategy()` - Font size reduction rendering
- `test_apply_wrap_strategy()` - Multi-line rendering
- `test_apply_truncate_strategy()` - Ellipsis truncation
- `test_select_auto_strategy_title()` - Auto selects shrink for short text
- `test_select_auto_strategy_message()` - Auto selects wrap for long text

### Integration Tests

**test_card_generation.py**:
- `test_overflow_shrink_front_greeting()` - Long greeting auto-shrinks
- `test_overflow_wrap_inside_message()` - Long message wraps
- `test_overflow_respects_safe_margins()` - 0.25" margins preserved
- `test_overflow_min_font_size_then_truncate()` - Extreme overflow handling
- `test_no_overflow_no_adjustment()` - Short text unchanged

### Visual Regression Tests

**test_visual_regression.py**:
- `test_visual_shrink_strategy()` - Compare PDF with shrunk text to reference
- `test_visual_wrap_strategy()` - Compare PDF with wrapped text to reference
- `test_visual_all_templates_no_overflow()` - Verify all templates fit correctly
- Reference PDFs in `tests/fixtures/reference_cards/overflow_scenarios/`

### Property-Based Tests (Hypothesis)

**test_overflow_properties.py**:
- `test_shrink_always_fits()` - Any text shrunk to 8pt+ always fits within bounds
- `test_wrap_never_exceeds_max_lines()` - Wrapped text respects line limit
- `test_truncate_never_overflows()` - Truncated text always fits

---

## Phase 4: Deployment & Rollout

### Backward Compatibility

- **Templates without overflow_strategy**: Default to AUTO (transparent enhancement)
- **Existing card generation code**: No API changes (all enhancements internal)
- **Existing tests**: Should pass without modification (new tests additive)

### Migration Path

1. **Immediate**: All existing templates gain overflow protection with AUTO strategy
2. **Optional**: Template authors can add explicit `overflow_strategy` to YAML for control
3. **Future**: Preview mode (P3) can show adjustment indicators

### Performance Impact

- **Per-text-element overhead**: ~1-5ms for measurement + potential adjustment
- **Typical card (5 text elements)**: ~5-25ms additional processing
- **Well within 100ms/element requirement and 10s total generation requirement**

### Documentation Updates

- Update template authoring guide with overflow_strategy field
- Add troubleshooting guide for text fitting issues
- Document minimum font size threshold and rationale

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| ReportLab stringWidth inaccurate for some fonts | High | Low | Add safety margin (5% padding) in calculations |
| Wrapped text exceeds panel height | Medium | Medium | Reduce font size if wrapping doesn't fit vertically |
| Performance degradation for long text | Low | Low | Profile and optimize (binary search, caching) |
| Minimum 8pt too small to read | Medium | Low | Make configurable (default 8pt, allow override) |
| Auto strategy picks wrong approach | Low | Medium | Allow explicit strategy override in templates |

---

## Success Metrics

- **Functional**: 100% of test cards pass visual regression (no overflow)
- **Performance**: <100ms per text element (measured in tests)
- **Compatibility**: All existing tests pass
- **Usability**: 0 manual text adjustments needed for standard templates
- **Quality**: Minimum 8pt font size maintained (verified in tests)

---

## Future Enhancements (Out of Scope)

- P3: Visual overflow warnings in preview mode
- P3: Boundary enforcement configuration (strict/relaxed)
- Advanced wrapping with hyphenation
- Custom minimum font size per template
- Overflow strategy inheritance (panel-level defaults)
- Real-time overflow detection in CLI (before render)
