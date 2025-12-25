# Research: Holiday Card Generator

**Feature**: 001-holiday-card-generator
**Date**: 2025-12-25
**Status**: Complete

## Executive Summary

This research evaluates PDF generation libraries, template systems, project structure, and testing strategies for building a Python-based holiday card generator optimized for laser printing.

---

## PDF Library Selection

### Decision: ReportLab

**Rationale**: ReportLab provides the precise measurement control (points, inches, cm) essential for accurate fold lines and print margins. It's industry-proven for professional print workflows with 20+ years of production use.

**Alternatives Considered**:

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| **ReportLab** | Precise positioning, print-grade output, rich drawing API | Steeper learning curve | **Selected** |
| **WeasyPrint** | HTML/CSS templates, designer-friendly | Less precise control, external dependencies | Rejected - fold line precision issues |
| **fpdf2** | Simple API, pure Python | Limited features, less precise | Rejected - insufficient for print needs |
| **PyMuPDF** | Fast rendering | Designed for PDF manipulation, not generation | Rejected - wrong use case |

---

## Template System Design

### Decision: Data-Driven Templates with YAML Configuration

**Rationale**: Separating template definitions from code allows non-developers to create/modify templates. Python dataclasses provide type safety while YAML files enable easy editing.

**Alternatives Considered**:

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **YAML + Dataclasses** | Type-safe, editable, version-controllable | Requires schema validation | **Selected** |
| **Pure Python Templates** | Full flexibility | Hard to modify without coding | Rejected |
| **JSON Configuration** | Standard format | Less human-readable than YAML | Rejected |
| **HTML/CSS Templates** | Designer-friendly | Precision issues for print | Rejected |

---

## Project Structure

### Decision: src/ Layout with Domain Separation

**Rationale**: The src/ layout prevents accidental imports during testing and follows Python Packaging Guide best practices. Clear separation between core logic, CLI, and rendering allows for flexible backend changes.

**Structure**:
```
src/
└── holiday_card/
    ├── cli/          # CLI commands (Typer/Click)
    ├── core/         # Domain logic, models, generators
    ├── renderers/    # ReportLab renderer, preview
    ├── themes/       # Color schemes
    └── utils/        # Measurements, validators
templates/            # YAML template definitions
tests/               # Unit, integration, visual tests
```

---

## Testing Strategy

### Decision: Multi-Layered Testing Approach

**Rationale**: PDF output requires visual validation (not just structural). Combining visual regression, structure validation, and property-based testing catches different failure modes.

**Test Layers**:

| Layer | Purpose | Tools |
|-------|---------|-------|
| **Visual Regression** | Detect visual differences from reference | pdf2image, imagehash, Pillow |
| **PDF Structure** | Validate page size, content presence | PyPDF2 |
| **Property-Based** | Test edge cases automatically | Hypothesis |
| **Unit Tests** | Test individual components | pytest |

---

## Image Handling

### Decision: Pillow for Image Processing

**Rationale**: Pillow integrates well with ReportLab, provides necessary image manipulation (resize, format conversion), and is the standard Python imaging library.

**Key Considerations**:
- Minimum 150 DPI for print quality
- Automatic aspect ratio preservation
- Support for PNG (with transparency) and JPG

---

## CLI Framework

### Decision: Typer

**Rationale**: Typer provides modern CLI features with automatic type inference from Python type hints. Simpler than Click for basic use cases while remaining powerful.

**Alternatives Considered**:

| Framework | Pros | Cons | Verdict |
|-----------|------|------|---------|
| **Typer** | Type-hint based, auto docs | Newer, smaller ecosystem | **Selected** |
| **Click** | Mature, extensive plugins | More verbose | Good alternative |
| **argparse** | Standard library | Manual, verbose | Rejected |

---

## Dependencies Summary

### Core Dependencies
```
reportlab>=4.0       # PDF generation
Pillow>=10.0         # Image processing
PyYAML>=6.0          # Template configuration
typer>=0.9           # CLI interface
pydantic>=2.0        # Model validation (optional)
```

### Development Dependencies
```
pytest>=7.0          # Testing framework
pytest-cov>=4.0      # Coverage reporting
hypothesis>=6.0      # Property-based testing
pdf2image>=1.16      # PDF to image conversion
imagehash>=4.3       # Visual comparison
```

---

## References

- ReportLab User Guide: https://www.reportlab.com/docs/reportlab-userguide.pdf
- Python Packaging Guide: https://packaging.python.org/
- Pillow Documentation: https://pillow.readthedocs.io/
- pytest Documentation: https://docs.pytest.org/
