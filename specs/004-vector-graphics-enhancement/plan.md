# Implementation Plan: Vector Graphics Enhancement

**Branch**: `004-vector-graphics-enhancement` | **Date**: 2025-12-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/workspaces/holiday-card/specs/004-vector-graphics-enhancement/spec.md`

## Summary

Expand the holiday-card-generator's vector graphics capabilities by adding SVG path import, gradient fills (linear and radial), image clipping masks, and pattern fills. This enhancement will increase commercial template coverage from approximately 25% to 70%+ by enabling sophisticated decorative elements (holly leaves, detailed snowflakes, wreaths), modern gradient backgrounds, photo cards with shaped frames, and festive pattern fills. The implementation extends the existing shape system (Rectangle, Circle, Triangle, Star, Line) while maintaining backward compatibility and adhering to the library-first architecture principle.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ReportLab 4.0+ (PDF generation with path/gradient support), Pillow 10.0+ (image processing for masks), Pydantic 2.0+ (model validation)
**Storage**: Filesystem - YAML templates with new element types, SVG path data as strings
**Testing**: pytest 7.0+ with visual regression (pdf2image + imagehash)
**Target Platform**: Python CLI application, OS-independent
**Project Type**: Single project (library-first architecture)
**Performance Goals**: Card generation time increase <20% for templates using new features vs. basic templates
**Constraints**: Print accuracy (300 DPI, 0.25" safe margin), offline operation (no network), backward compatibility (all existing templates work unmodified)
**Scale/Scope**: 4 new shape types (SVGPath, LinearGradient, RadialGradient, PatternFill), ~15 new model classes, extends existing ShapeRenderer

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Library-First Architecture ✅ PASS

**Compliance**: New vector graphics features follow existing architecture:
- Core models in `src/holiday_card/core/models.py` (SVGPath, gradient/pattern models)
- Rendering logic in `src/holiday_card/renderers/shape_renderer.py` extensions
- No CLI-specific code in core modules
- Independently testable without CLI overhead

**Evidence**: Extends existing BaseShape → ShapeRenderer pattern used by Rectangle, Circle, etc.

### Principle II: CLI-First Interface ✅ PASS

**Compliance**: No new CLI commands required - new features accessible through existing `holiday-card generate` command via YAML template definitions.

**Evidence**: SVG paths, gradients, patterns, and clipping masks defined in YAML templates, processed by existing template system.

### Principle III: Configuration-Driven Design ✅ PASS

**Compliance**: All new graphics primitives MUST be definable in YAML:
- SVG paths: `type: svg_path, path_data: "M 10 10 L 20 20 ..."`
- Gradients: `fill: {type: linear_gradient, angle: 45, stops: [...]}`
- Patterns: `fill: {type: pattern, pattern_type: stripes, ...}`
- Clipping masks: `clip_mask: {shape: circle, ...}`

**Evidence**: FR-017, FR-018 require YAML integration for all new element types.

### Principle IV: Print Accuracy ✅ PASS

**Compliance**: Maintains existing measurement standards:
- SVG paths use inches for coordinates, converted to points at render time
- Gradients and patterns respect safe margins
- Clipping masks ensure images stay within panel boundaries
- All conversions use 72 pts/inch standard

**Evidence**: Extends existing inch-based measurement system; no changes to page size or margin enforcement.

### Principle V: Simplicity ⚠️ POTENTIAL VIOLATION - JUSTIFIED

**Potential Violation**: Adds complexity through SVG path parsing and gradient/pattern rendering.

**Justification**:
- SVG path parsing is essential to meet the "increase template coverage to 70%" success criterion (SC-004)
- ReportLab natively supports paths and gradients - we're exposing existing functionality, not reimplementing
- Alternatives rejected:
  - Limit to basic shapes: Fails to achieve coverage goal (only ~25% currently)
  - Full SVG file import: Over-engineering (Constitution Principle V), introduces XML parsing, metadata handling
  - External rendering service: Violates offline operation requirement

**Mitigation**:
- Use ReportLab's built-in path/gradient APIs (no custom rendering math)
- Gracefully degrade unsupported SVG commands (FR-006)
- Pattern fills use simple repeating shapes (no complex tiling algorithms)

### Principle VI: Visual Testing ✅ PASS

**Compliance**: Extends existing visual regression testing:
- New reference PDFs for SVG path rendering
- Gradient color transition validation
- Clipping mask boundary verification
- Pattern repeatability checks
- All using existing pdf2image + imagehash infrastructure

**Evidence**: No new testing infrastructure needed; reuses existing fixtures and comparison logic.

## Project Structure

### Documentation (this feature)

```text
specs/004-vector-graphics-enhancement/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── yaml-schema.md   # Extended YAML schema for new element types
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/holiday_card/
├── core/
│   ├── models.py                    # EXTEND: Add SVGPath, gradient, pattern, mask models
│   ├── templates.py                 # EXTEND: YAML parsing for new element types
│   └── validators.py (NEW)          # SVG path validation, gradient color stop validation
├── renderers/
│   ├── shape_renderer.py            # EXTEND: Add SVG path, gradient, pattern rendering
│   ├── gradient_renderer.py (NEW)   # Gradient-specific rendering logic
│   ├── pattern_renderer.py (NEW)    # Pattern fill rendering logic
│   └── clipping_renderer.py (NEW)   # Image clipping mask rendering
└── utils/
    ├── svg_parser.py (NEW)          # SVG path data parsing (M, L, C, Q, A commands)
    └── gradient_utils.py (NEW)      # Color interpolation for gradients

tests/
├── unit/
│   ├── test_svg_parser.py (NEW)             # SVG path command parsing
│   ├── test_gradient_models.py (NEW)        # Gradient color stop validation
│   ├── test_pattern_models.py (NEW)         # Pattern fill model validation
│   └── test_clipping_masks.py (NEW)         # Clipping mask validation
├── integration/
│   ├── test_svg_rendering.py (NEW)          # End-to-end SVG path rendering
│   ├── test_gradient_rendering.py (NEW)     # Gradient visual output
│   ├── test_clipping_rendering.py (NEW)     # Clipped image output
│   └── test_pattern_rendering.py (NEW)      # Pattern fill output
└── fixtures/
    ├── reference_cards/
    │   ├── svg_holly_leaf.pdf (NEW)         # Visual regression baseline
    │   ├── gradient_sunset.pdf (NEW)        # Gradient rendering baseline
    │   ├── photo_circle_clip.pdf (NEW)      # Clipping mask baseline
    │   └── stripe_pattern.pdf (NEW)         # Pattern fill baseline
    └── sample_data/
        ├── holly_leaf.svg (NEW)             # SVG path data for testing
        └── test_photo.jpg (NEW)             # Sample image for clipping tests

templates/christmas/
├── holly_wreath.yaml (NEW)          # Example using SVG paths
├── gradient_snowscape.yaml (NEW)    # Example using gradients
├── photo_ornament.yaml (NEW)        # Example using clipping masks
└── festive_stripes.yaml (NEW)       # Example using pattern fills
```

**Structure Decision**: Single project structure maintained (library-first architecture). New functionality extends existing modules rather than creating parallel subsystems. Renderers follow single-responsibility pattern: one renderer class per feature (gradients, patterns, clipping) called by the main ShapeRenderer coordinator.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| SVG path parsing complexity (Principle V) | Required to achieve 70% template coverage goal (SC-004). Commercial holiday card designs rely heavily on complex decorative shapes (holly, snowflakes, wreaths) that cannot be composed from basic geometric primitives. | **Basic shapes only**: Achieves only ~25% coverage (current state), fails SC-004. **Full SVG file import**: Over-engineering, introduces XML parsing, metadata handling, text-on-path, filters - massive scope creep. **Bitmap decorations**: Violates print quality (scalability), increases file size. |
| Gradient rendering (Principle V) | Required for ~10% additional template coverage and modern design aesthetics. Gradients are native to ReportLab - we expose existing functionality. | **Solid colors only**: Eliminates entire category of professional-looking designs (sky backgrounds, metallic effects). **Pre-rendered gradient images**: Bitmap approach violates print quality and scalability. |
| Pattern fills (Principle V) | Required for ~5% additional template coverage (festive textiles, wrapping paper effects). Uses simple repeating shapes. | **Omit patterns**: Sacrifices festive character and traditional holiday design patterns (plaid, stripes, dots). |

**Total Complexity Cost**: 3 new renderer classes, 1 SVG parser utility, ~15 new model classes. All extend existing architecture without breaking changes.

**Mitigation Strategy**:
- Use ReportLab's native path/gradient APIs (no custom rendering)
- Gracefully degrade unsupported SVG commands (log warning, skip)
- Pattern fills limited to built-in types (stripes, dots) - no arbitrary pattern images
- Comprehensive visual regression tests catch rendering issues early
