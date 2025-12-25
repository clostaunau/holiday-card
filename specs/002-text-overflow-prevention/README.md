# Feature 002: Text Overflow Prevention

**Status**: ✓ Ready for Implementation
**Branch**: `002-text-overflow-prevention`
**Priority**: P1 (MVP) + P2 (Full Feature)
**Estimated Effort**: 12-16 hours

## Quick Links

- [Feature Specification](./spec.md) - User stories, requirements, success criteria
- [Implementation Plan](./plan.md) - Technical architecture and approach
- [Task Breakdown](./tasks.md) - Dependency-ordered implementation tasks
- [Quickstart Guide](./quickstart.md) - Usage examples and integration
- [Technical Research](./research.md) - Key technical decisions
- [Data Model](./data-model.md) - Entity definitions and YAML schema
- [Consistency Analysis](./analysis-report.md) - Cross-document validation
- [Quality Checklists](./checklists/) - Requirements and testing validation

## Overview

Implement automatic text overflow prevention for holiday cards to ensure all text fits within designated boundaries. The system detects overflow conditions and applies one of three strategies: font size reduction (shrink), multi-line wrapping (wrap), or truncation with ellipsis (truncate).

### Problem

Currently, text can extend past printable boundaries when cards are folded, resulting in cutoff content on printed cards.

### Solution

- **Detection**: Measure text dimensions before rendering using ReportLab's stringWidth API
- **Adjustment**: Apply one of three strategies automatically or via configuration
  - **SHRINK**: Reduce font size iteratively (binary search) until text fits (min 8pt)
  - **WRAP**: Break text into multiple lines at word boundaries
  - **TRUNCATE**: Cut text with ellipsis (existing behavior)
- **Configuration**: Users can specify strategy per text element in YAML templates

## User Stories (Prioritized)

### P1 - Automatic Text Fitting (MVP)
Detect overflow and reduce font size automatically. **Essential** for preventing cutoff.

### P2 - Multi-Line Wrapping
Wrap long messages across multiple lines. **Important** for inside panel messages.

### P2 - Configurable Strategy
Allow explicit control over shrink/wrap/truncate per element. **Important** for flexibility.

### P3 - Visual Warnings (Deferred)
Preview mode shows adjustment indicators. **Nice-to-have** for future release.

### P3 - Boundary Modes (Deferred)
Strict vs. relaxed enforcement. **Nice-to-have** for advanced users.

## Technical Approach

### Core Components

1. **OverflowStrategy Enum** (AUTO, SHRINK, WRAP, TRUNCATE)
2. **TextElement Enhancement** (overflow_strategy, max_lines, min_font_size fields)
3. **Text Utilities Module** (measure_text, shrink_to_fit, wrap_text functions)
4. **Renderer Updates** (strategy application in ReportLabRenderer)

### Key Algorithms

- **Font Reduction**: Binary search (6 iterations for 6-144pt range)
- **Text Wrapping**: Word boundary detection with width measurement
- **Line Height**: 1.2x font size (typography standard)
- **AUTO Selection**: Length-based heuristic (< 30 chars → SHRINK, else → WRAP)

### Constitution Compliance

- ✓ Library-First: Core logic in `src/holiday_card/core/`
- ✓ CLI-First: Transparent enhancement to existing `generate` command
- ✓ Configuration-Driven: Strategy in YAML templates
- ✓ Print Accuracy: 0.25" margins, 1mm tolerance maintained
- ✓ Simplicity: No new dependencies, enhances existing code
- ✓ Visual Testing: pdf2image + imagehash validation

## Implementation Roadmap

### Phase 1: Foundation (~2 hours)
- T001-T005: Add enums, models, enhance TextElement, create text_utils.py

### Phase 2: MVP - SHRINK Strategy (~6 hours)
- T006-T016: Implement font size reduction, tests, visual validation
- **Checkpoint**: Basic overflow prevention working

### Phase 3: WRAP Strategy (~4 hours)
- T017-T027: Implement multi-line wrapping, tests, visual validation
- **Checkpoint**: Full shrink + wrap capability

### Phase 4: Configuration (~4 hours)
- T028-T037: Explicit strategy configuration, template updates
- **Checkpoint**: User-configurable strategies

### Phase 5: Polish (~2 hours)
- T038-T043: Property tests, performance validation, documentation

**Total**: ~16 hours for full feature (P1 + P2)
**MVP**: ~8 hours for P1 only

## Testing Strategy

### Test Types

- **Unit**: 15 tests (text_utils, models, renderer)
- **Integration**: 9 tests (card generation end-to-end)
- **Visual**: 4 tests (PDF comparison with references)
- **Property**: 3 tests (Hypothesis edge cases)
- **Performance**: 2 tests (<100ms, <10s requirements)
- **Manual**: Print and fold validation

### Test Coverage

- ✓ All user stories independently tested
- ✓ All functional requirements covered
- ✓ All success criteria validated
- ✓ Edge cases handled
- ✓ Backward compatibility verified

## Success Criteria

- **SC-001**: 100% of cards have zero text overflow (automated visual tests)
- **SC-002**: Minimum 8pt font size enforced (readable)
- **SC-003**: <100ms per text element (performance)
- **SC-004**: Visual regression tests pass (PDF comparison)
- **SC-005**: Manual print test confirms no cutoff (10 test prints)
- **SC-006**: All existing tests pass (backward compatibility)
- **SC-007**: 90% of use cases configurable via YAML

## Files Modified/Created

### New Files
```
src/holiday_card/core/text_utils.py
tests/unit/test_text_utils.py
tests/unit/test_overflow_properties.py
tests/integration/test_performance.py
tests/fixtures/test_templates/overflow-*.yaml
tests/fixtures/reference_cards/overflow_scenarios/*.pdf
```

### Modified Files
```
src/holiday_card/core/models.py (TextElement, +enums)
src/holiday_card/renderers/reportlab_renderer.py (render_text, +strategies)
tests/unit/test_models.py (+overflow tests)
tests/integration/test_card_generation.py (+overflow scenarios)
tests/integration/test_visual_regression.py (+overflow visuals)
templates/christmas/*.yaml (+overflow_strategy)
templates/birthday/*.yaml (+overflow_strategy)
templates/hanukkah/*.yaml (+overflow_strategy)
templates/generic/*.yaml (+overflow_strategy)
CLAUDE.md (feature documentation)
```

## Quick Start (for Implementers)

1. **Checkout branch**: Already on `002-text-overflow-prevention`
2. **Review docs**: Read spec.md, plan.md, quickstart.md
3. **Start with Foundation**: Begin with T001-T005 (data models)
4. **Follow TDD**: Write tests FIRST (ensure they FAIL)
5. **Implement incrementally**: Foundation → US1 → US2 → US3 → Polish
6. **Validate at checkpoints**: Test each user story independently
7. **Run full suite**: `pytest tests/` before marking complete

## Configuration Example

### Before (existing template)
```yaml
text_elements:
  - content: "Merry Christmas!"
    x: 2.0
    y: 3.0
    font_size: 36
```

### After (with overflow prevention)
```yaml
text_elements:
  - content: "Merry Christmas and Happy New Year!"
    x: 2.0
    y: 3.0
    width: 4.0                    # Required for overflow detection
    font_size: 36
    overflow_strategy: "shrink"   # AUTO, SHRINK, WRAP, or TRUNCATE
    min_font_size: 12             # Don't go below 12pt (optional)
```

## Dependencies

**None** - Uses existing ReportLab APIs, no new packages required.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| ReportLab stringWidth inaccurate | Add 5% safety margin |
| Wrapped text exceeds height | Auto-reduce font size |
| Performance degradation | Binary search, profiling |
| Min 8pt too small | Configurable min_font_size |
| AUTO picks wrong strategy | Allow explicit override |

## Approval Status

- ✓ Specification approved (requirements.md checklist)
- ✓ Test strategy approved (test.md checklist)
- ✓ Consistency validated (analysis-report.md)
- ✓ Constitution compliant (plan.md)
- ✓ Ready for implementation

## Next Steps

1. Begin implementation with Foundation phase (T001-T005)
2. Follow task order in tasks.md
3. Validate at each checkpoint
4. Update this README with implementation notes as you progress

---

**Last Updated**: 2025-12-25
**Workflow Phase**: Planning Complete → Implementation Ready
