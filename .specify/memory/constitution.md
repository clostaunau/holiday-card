<!--
Sync Impact Report
==================
Version change: 0.0.0 → 1.0.0 (initial ratification)
Modified principles: N/A (new constitution)
Added sections:
  - Core Principles (6 principles)
  - Technology Stack
  - Development Workflow
  - Governance
Removed sections: N/A
Templates requiring updates:
  - .specify/templates/plan-template.md: ✅ compatible (Constitution Check section exists)
  - .specify/templates/spec-template.md: ✅ compatible (no changes needed)
  - .specify/templates/tasks-template.md: ✅ compatible (no changes needed)
Follow-up TODOs: None
-->

# Holiday Card Generator Constitution

## Core Principles

### I. Library-First Architecture

Core generation logic MUST be separated from CLI presentation layer.

- The `src/holiday_card/core/` module contains all business logic (models, generators, templates)
- The `src/holiday_card/cli/` module handles user interaction only
- The `src/holiday_card/renderers/` module implements output strategies
- Core modules MUST be independently importable and testable without CLI dependencies
- No CLI-specific code (Typer, argument parsing) in core modules

**Rationale**: Enables testing without CLI overhead, supports future GUI/API interfaces, maintains
single responsibility.

### II. CLI-First Interface

All features MUST be accessible via command-line interface.

- Every user capability has a corresponding CLI command or option
- Commands follow Unix conventions: `holiday-card <command> [options]`
- Output supports both human-readable (default) and machine-readable (--format json) modes
- Errors written to stderr with actionable messages
- Exit codes follow conventions (0=success, non-zero=error types)

**Rationale**: CLI enables scripting, automation, and integration with other tools.
Print workflows benefit from batch processing capabilities.

### III. Configuration-Driven Design

Templates and themes MUST be stored as YAML configuration, not hardcoded.

- Card templates defined in `templates/<occasion>/<name>.yaml`
- Color themes defined in `themes/<occasion>.yaml`
- YAML schema enforced via Pydantic model validation
- Users can create custom templates without modifying source code
- Configuration changes require no rebuild

**Rationale**: Non-developers can create and modify templates. Enables community contributions
and personal customization without Python knowledge.

### IV. Print Accuracy

Measurements MUST be precise for reliable printed output.

- All internal measurements use inches as primary unit
- Conversion to PDF points (72 pts/inch) happens only at render time
- Safe margin of 0.25" MUST be enforced on all edges
- Fold lines MUST be positioned within 1mm tolerance of specified locations
- Images MUST maintain minimum 150 DPI for print quality
- Page size fixed at 8.5" x 11" (US Letter)

**Rationale**: Inaccurate measurements result in misaligned folds, cut-off content, and wasted
paper/toner. Print output must be reliable without manual adjustment.

### V. Simplicity

Minimize dependencies and complexity. Prefer simple solutions.

- No database required - filesystem storage only (YAML files, images, PDFs)
- Offline operation - no network dependencies for core functionality
- Minimal runtime dependencies: ReportLab, Pillow, Typer, PyYAML, Pydantic
- YAGNI (You Aren't Gonna Need It) - implement only what's specified
- Avoid abstractions until third use case proves necessity

**Rationale**: Greeting card generation is a simple domain. Over-engineering introduces
maintenance burden and barriers to contribution.

### VI. Visual Testing

PDF output MUST be validated through visual regression testing.

- Use pdf2image + imagehash for visual comparison against reference outputs
- Unit tests validate models and calculations
- Integration tests verify end-to-end card generation
- Reference PDFs stored in `tests/fixtures/reference_cards/`
- Property-based testing (Hypothesis) for edge case discovery
- Tests run via pytest with coverage reporting

**Rationale**: PDF rendering correctness cannot be verified by structure alone.
Visual comparison catches font, color, positioning, and layout issues.

## Technology Stack

**Language**: Python 3.11+

**Core Dependencies**:
- ReportLab 4.0+ (PDF generation)
- Pillow 10.0+ (image processing)
- Typer 0.9+ (CLI framework)
- PyYAML 6.0+ (configuration parsing)
- Pydantic 2.0+ (model validation)

**Development Dependencies**:
- pytest 7.0+ (testing)
- pytest-cov (coverage)
- hypothesis (property-based testing)
- pdf2image (visual regression)
- imagehash (image comparison)
- mypy (type checking)
- ruff (linting)

**Project Structure**:
```
src/holiday_card/     # Source code (src/ layout)
templates/            # YAML template definitions
themes/               # YAML theme definitions
tests/                # Test suite
output/               # Generated PDFs (gitignored)
```

## Development Workflow

**Agent Support**: The uncle-duke-python agent is available for Python development guidance,
code reviews, and best practice consultation during implementation.

**Code Quality Gates**:
- All code MUST pass ruff linting
- All code MUST pass mypy type checking
- All tests MUST pass before merge
- Visual regression tests MUST not show unexpected differences

**Commit Practices**:
- Commit after each completed task or logical unit
- Commit messages describe what changed and why
- No commits of generated PDFs (gitignored)

**Review Process**:
- Complexity additions MUST be justified in PR description
- New dependencies MUST be justified against Simplicity principle
- Print accuracy changes MUST include visual test updates

## Governance

This constitution supersedes all other development practices for this project.

**Compliance**:
- All PRs MUST verify compliance with Core Principles
- Constitution violations require explicit justification and approval
- Unjustified violations block merge

**Amendments**:
- Amendments require documentation of rationale
- Version increments follow semantic versioning:
  - MAJOR: Principle removal or incompatible redefinition
  - MINOR: New principle or significant expansion
  - PATCH: Clarification or wording refinement
- Amendment date updated on each change

**Version**: 1.0.0 | **Ratified**: 2025-12-25 | **Last Amended**: 2025-12-25
