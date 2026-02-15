# holiday-card Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-25

## Active Technologies
- Python 3.11+ + ReportLab 4.0+ (PDF generation with path/gradient support), Pillow 10.0+ (image processing for masks), Pydantic 2.0+ (model validation) (004-vector-graphics-enhancement)
- Filesystem - YAML templates with new element types, SVG path data as strings (004-vector-graphics-enhancement)

- Python 3.11+ + ReportLab 4.0+, Pillow 10.0+, Typer 0.9+, PyYAML 6.0+, Pydantic 2.0+ (001-holiday-card-generator, 003-vector-graphics-and-decorative-elements)

## Project Structure

```text
src/
  holiday_card/
    core/
      models.py           # Pydantic models (Card, Template, Panel, shapes)
      generators.py       # Card generation logic
      templates.py        # Template loading/management
      themes.py           # Theme definitions
      decorative.py       # Decorative element library (NEW)
      text_utils.py       # Text rendering utilities
    renderers/
      base.py             # Renderer protocol
      reportlab_renderer.py  # ReportLab PDF renderer
      shape_renderer.py   # Vector shape rendering (NEW)
      preview_renderer.py # Preview image generation
    cli/
      commands.py         # Typer CLI commands
    utils/
      measurements.py     # Unit conversions
      validators.py       # Input validation
tests/
  unit/                   # Unit tests
  integration/            # Integration tests
  visual/                 # Visual regression tests
  fixtures/
    templates/            # Test templates
    reference_cards/      # Reference PDFs for visual regression
templates/                # Card template YAML files
  christmas/
    classic.yaml
    modern.yaml
    geometric.yaml        # NEW: Geometric tree design
  hanukkah/
  birthday/
  generic/
decorative_elements/      # NEW: Pre-built decorative element library
  christmas/
    geometric_tree.yaml
    traditional_tree.yaml
    ornament_bauble.yaml
    ornament_star.yaml
    star_topper.yaml
    wreath.yaml
    snowflake.yaml
  generic/
    gift_box.yaml
  hanukkah/
    menorah.yaml
    dreidel.yaml
```

## Commands

### Testing
```bash
cd src
pytest                          # Run all tests
pytest -v tests/unit/           # Run unit tests
pytest tests/integration/       # Run integration tests
```

### Linting
```bash
ruff check .                    # Run linter
ruff check . --fix              # Auto-fix issues
mypy src/                       # Type checking
```

### Card Generation
```bash
# Generate card from template
python -m holiday_card create christmas-geometric -o output/card.pdf

# List available templates
python -m holiday_card templates

# Validate template
python -m holiday_card validate templates/christmas/geometric.yaml
```

## Code Style

Python 3.11+: Follow standard conventions
- Type hints for all functions
- Pydantic models for data validation
- Docstrings for all public APIs
- Measurements in inches (converted to points at render time)

## Recent Changes
- 004-vector-graphics-enhancement: Added Python 3.11+ + ReportLab 4.0+ (PDF generation with path/gradient support), Pillow 10.0+ (image processing for masks), Pydantic 2.0+ (model validation)

- 001-holiday-card-generator: Added Python 3.11+ + ReportLab 4.0+, Pillow 10.0+, Typer 0.9+, PyYAML 6.0+, Pydantic 2.0+
- 003-vector-graphics-and-decorative-elements: Added vector graphics support with 5 shape types (Rectangle, Circle, Triangle, Star, Line), z-index layering, opacity/rotation/stroke styling, and decorative element library with 10 pre-built compositions

## Features

### Vector Graphics (003-vector-graphics-and-decorative-elements)

**Shape Types**:
- Rectangle: Positioned rectangles with fill, stroke, opacity, rotation
- Circle: Circles with center point and radius
- Triangle: Three-vertex polygons
- Star: Multi-pointed stars with configurable inner/outer radius
- Line: Straight line segments

**Styling Properties**:
- `fill_color`: Hex color (#RRGGBB) for shape fill
- `stroke_color`: Hex color for outline
- `stroke_width`: Stroke width in points
- `opacity`: 0.0 (transparent) to 1.0 (opaque)
- `rotation`: 0-360 degrees
- `z_index`: Layering order (higher = on top)

**Decorative Elements**:
Pre-built compositions of basic shapes. Available elements:
- Christmas: geometric_tree, traditional_tree, ornament_bauble, ornament_star, star_topper, wreath, snowflake
- Generic: gift_box
- Hanukkah: menorah, dreidel

**Usage in Templates**:
```yaml
panels:
  - position: front
    shape_elements:
      # Basic shape
      - type: rectangle
        x: 1.0
        y: 2.0
        width: 3.0
        height: 1.5
        fill_color: "#A8B5A0"
        opacity: 0.8
        z_index: 1

      # Decorative element
      - type: decorative_element
        name: geometric_tree
        x: 4.25
        y: 2.0
        scale: 1.0
        rotation: 0
        color_palette:
          tree_primary: "#A8B5A0"
          tree_accent: "#B85C50"
          ornament: "#D4AF37"
          star: "#FFD700"
```

**Key Files**:
- `src/holiday_card/core/models.py`: Shape model definitions
- `src/holiday_card/renderers/shape_renderer.py`: Shape rendering logic
- `src/holiday_card/core/decorative.py`: Decorative element library
- `decorative_elements/`: YAML definitions for decorative elements
- `specs/003-vector-graphics-and/`: Complete feature specification

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
