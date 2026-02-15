# Implementation Plan: Holiday Card Generator

**Branch**: `001-holiday-card-generator` | **Date**: 2025-12-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-holiday-card-generator/spec.md`

## Summary

Build a Python CLI application that generates printable PDF greeting cards optimized for color laser printing on 8.5" x 11" paper. The system uses ReportLab for precise PDF generation, supports multiple fold formats (half-fold, quarter-fold, tri-fold), and provides a template-based design system with customizable themes for various occasions.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ReportLab 4.0+, Pillow 10.0+, Typer 0.9+, PyYAML 6.0+, Pydantic 2.0+
**Storage**: Local filesystem (YAML templates, PNG/JPG images, PDF output)
**Testing**: pytest 7.0+, pytest-cov, hypothesis, pdf2image, imagehash
**Target Platform**: Cross-platform (Linux, macOS, Windows)
**Project Type**: Single CLI application
**Performance Goals**: Card generation under 10 seconds
**Constraints**: Offline operation, 0.25" minimum safe margins, 150+ DPI for images
**Scale/Scope**: 20+ templates, 10+ themes, unlimited card generation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verified against `.specify/memory/constitution.md` v1.0.0:

- [x] **I. Library-First Architecture**: Core logic in `src/holiday_card/core/`, CLI in `cli/`, renderers separate
- [x] **II. CLI-First Interface**: All features via `holiday-card` commands, JSON output supported
- [x] **III. Configuration-Driven**: Templates in `templates/*.yaml`, themes in `themes/*.yaml`
- [x] **IV. Print Accuracy**: Inches as primary unit, 0.25" margins, 72 pts/inch conversion at render
- [x] **V. Simplicity**: 5 runtime deps, filesystem only, offline operation, no over-engineering
- [x] **VI. Visual Testing**: pytest + pdf2image + imagehash for PDF validation

## Project Structure

### Documentation (this feature)

```text
specs/001-holiday-card-generator/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Technology decisions
├── data-model.md        # Entity definitions
├── quickstart.md        # Getting started guide
├── contracts/           # Interface contracts
│   └── cli-interface.md # CLI command specifications
└── tasks.md             # Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
└── holiday_card/
    ├── __init__.py           # Package init with version
    ├── __main__.py           # CLI entry point
    ├── cli/
    │   ├── __init__.py
    │   └── commands.py       # Typer CLI commands
    ├── core/
    │   ├── __init__.py
    │   ├── models.py         # Pydantic/dataclass models
    │   ├── generators.py     # PDF generation logic
    │   ├── templates.py      # Template loading/management
    │   └── themes.py         # Theme definitions
    ├── renderers/
    │   ├── __init__.py
    │   ├── base.py           # Renderer protocol/ABC
    │   ├── reportlab_renderer.py  # ReportLab implementation
    │   └── preview_renderer.py    # Preview image generation
    └── utils/
        ├── __init__.py
        ├── measurements.py   # Unit conversions (inches/points)
        └── validators.py     # Input validation

templates/
├── christmas/
│   ├── classic.yaml
│   └── modern.yaml
├── hanukkah/
│   └── menorah.yaml
├── birthday/
│   └── balloons.yaml
└── generic/
    └── celebration.yaml

themes/
├── christmas.yaml
├── hanukkah.yaml
├── birthday.yaml
└── generic.yaml

tests/
├── conftest.py           # Shared fixtures
├── unit/
│   ├── test_models.py
│   ├── test_generators.py
│   └── test_templates.py
├── integration/
│   └── test_full_generation.py
└── fixtures/
    ├── sample_templates/
    └── reference_cards/

output/                   # Generated PDFs (gitignored)
```

**Structure Decision**: Single project with src/ layout for clean package separation. Core domain logic isolated from CLI and rendering concerns. Strategy pattern for renderers allows future backends.

## Implementation Phases

### Phase 1: Core Infrastructure (P1 - MVP)

1. **Project Setup**
   - Initialize pyproject.toml with dependencies
   - Configure pytest, mypy, ruff
   - Create src/ layout structure

2. **Core Models**
   - Implement Card, Template, Theme, Panel dataclasses
   - Add Pydantic validation
   - Define measurement constants

3. **ReportLab Renderer**
   - Implement PDF canvas setup (8.5" x 11")
   - Add fold line drawing for each format
   - Implement panel content placement
   - Handle text and image rendering

4. **Basic CLI**
   - `holiday-card create` command
   - `holiday-card templates` listing
   - Basic error handling

### Phase 2: Template System (P2)

1. **YAML Template Loading**
   - Template schema definition
   - Template discovery and loading
   - Validation against schema

2. **Theme System**
   - Theme YAML loading
   - Color application to templates
   - Theme override support

3. **Image Handling**
   - Pillow integration for image loading
   - Aspect ratio preservation
   - DPI validation for print quality

### Phase 3: Advanced Features (P3)

1. **Preview Generation**
   - PDF to image conversion
   - Preview command implementation
   - Fold visualization

2. **Custom Templates**
   - `holiday-card init` command
   - Template validation command
   - Custom template documentation

3. **Polish**
   - Comprehensive error messages
   - Progress indicators
   - JSON output mode

## Testing Strategy

| Test Type | Purpose | Tools |
|-----------|---------|-------|
| Unit | Model validation, calculations | pytest |
| Visual Regression | PDF output correctness | pdf2image, imagehash |
| Property-Based | Edge case discovery | hypothesis |
| Integration | End-to-end workflows | pytest |

## Dependencies

### Runtime
```toml
[project.dependencies]
reportlab = ">=4.0"
Pillow = ">=10.0"
typer = {extras = ["all"], version = ">=0.9"}
PyYAML = ">=6.0"
pydantic = ">=2.0"
```

### Development
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "hypothesis>=6.0",
    "pdf2image>=1.16",
    "imagehash>=4.3",
    "mypy>=1.0",
    "ruff>=0.1",
]
```

## Notes

- **uncle-duke-python agent** is available for Python development guidance, code reviews, and best practices during implementation
- All measurements use inches as the primary unit, converted to points (72 pts/inch) for ReportLab
- Templates stored as YAML for easy editing by non-developers
- Visual regression testing ensures print accuracy across updates
