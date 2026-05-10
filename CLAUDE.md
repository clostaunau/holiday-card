# holiday-card Development Guidelines

Last updated: 2026-05-10. Wave 2 architecture refactor in progress; see
the "Architecture (Wave 2)" section below for the IR seam.

## Active Technologies
- Python 3.11+
- ReportLab 4.0+ (PDF generation with path/gradient support, TTF/OTF font embedding)
- Pillow 10.0+ (image processing for masks and effects)
- Pydantic 2.0+ (model validation, including the RenderCommand IR)
- Typer 0.9+, PyYAML 6.0+

## Project Structure

```text
src/
  holiday_card/
    core/
      models.py           # Pydantic domain models (Card, Template, Panel, shapes)
      generators.py       # Card generation orchestration (Card → IR → PDF)
      templates.py        # YAML template loading/discovery
      themes.py           # Theme definitions
      text_utils.py       # Text measurement primitives
      text_fitting.py     # Overflow strategies (Wave 2 Step 2a)
      render_ir.py        # RenderCommand IR — backend-neutral seam (Wave 2 Step 1)
      compiler.py         # Card → list[RenderCommand] (Wave 2 Step 2b)
    renderers/
      reportlab_backend.py  # The renderer: IR → PDF (Wave 2 Steps 3-5)
      image_effects.py      # Pillow effects (sepia, grayscale, vignette, blur)
      preview_renderer.py   # PNG preview generation (separate path)
    cli/
      commands.py         # Typer CLI commands
    utils/
      measurements.py     # inch ↔ point conversions
      svg_parser.py       # SVG path parser (kept for future IR support)
      validators.py       # Input validation
tests/
  unit/                   # Unit tests (test_render_ir, test_compiler, test_cli, ...)
  integration/            # Integration tests (test_full_generation)
  visual/                 # Reserved for visual regression (no tests yet)
templates/                # Card template YAML files
  christmas/              # Templates (classic, modern, geometric, ...)
  hanukkah/, birthday/, generic/
themes/                   # Color theme definitions
fonts/                    # Custom TTF/OTF fonts
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

- **Wave 2 architecture refactor (complete, 2026-05)**: A backend-neutral
  `RenderCommand` IR sits between `Card` and the renderer. New
  `core/render_ir.py`, `core/compiler.py`, `renderers/reportlab_backend.py`.
  `core/text_fitting.py` extracted from the legacy renderer. The legacy
  `ReportLabRenderer` (1063 LOC) and its dependent modules
  (`shape_renderer`, `clipping_renderer`, `gradient_renderer`,
  `pattern_renderer`, `decorative.py`) were deleted in Step 5 — about
  3000 LOC removed. Mypy errors dropped from 29 to 10 as a side effect.
- **Wave 1 DevEx audit (2026-05)**: Real CI on every push (lint + matrix
  test + smoke + build); `requirements.txt` deleted (10 phantom deps);
  pre-commit + ruff format config; 22 B904 exception-chain bugs and 10
  null-deref defects fixed. CLI surface (556 LOC, was 0% covered) now at
  ~58% via `tests/unit/test_cli.py` using `typer.testing.CliRunner`.
- **Valentine deprecation (2026-05)**: The 2026-02 Valentine release
  (`valentine` occasion + 3 templates + decorative-element library +
  `HeartClipMask`) was removed when Wave 2 made decorative-element
  expansion non-trivial to port. The dead code (decorative.py,
  HeartClipMask, etc.) will be cleaned up in the Wave 2 Step 5 PR.

## Features

### Image Features

**Image Effects**:
- `grayscale`: Convert to black & white
- `sepia`: Apply vintage sepia tone
- `vignette`: Edge darkening (0.0-1.0 intensity)
- `blur`: Gaussian blur (0-10 pixel radius)

**Photo Frames**:
- `simple`: Clean border
- `rounded`: Rounded corners
- `shadow`: Drop shadow effect
- `polaroid`: Instant camera aesthetic with white border

**Usage in Templates**:
```yaml
image_elements:
  - source_path: "photo.jpg"
    x: 1.0
    y: 2.0
    width: 2.5
    height: 2.5
    clip_mask:
      type: circle
      center_x: 1.25
      center_y: 1.25
      radius: 1.25
    effects:
      sepia: true
      vignette: 0.4
    frame_style: polaroid
    frame_color: "#FFFFFF"
    frame_width: 0.02
```

**Supported Clip Mask Types**:
- `circle`, `rectangle`, `ellipse`, `star`, `svg_path`

### Custom Font Support (2026-02-14 Release)

**TTF/OTF Font Embedding**:
- Full support for TrueType and OpenType fonts
- Automatic registration with ReportLab
- Graceful fallback to built-in fonts on error

**Font Discovery**:
- Place fonts in `fonts/` directory at project root
- Supports subdirectories for organization
- Relative paths resolved automatically

**Usage in Templates**:
```yaml
text_elements:
  - content: "With All My Love"
    x: 2.125
    y: 0.8
    width: 3.5
    font_family: "GreatVibes"
    font_file: "GreatVibes-Regular.ttf"  # From fonts/ directory
    font_size: 32
    font_style: normal
```

**Recommended Fonts** (open source, free to use):
- Great Vibes - Elegant script (SIL OFL)
- Playfair Display - Sophisticated serif (SIL OFL)
- Lora - Elegant serif (SIL OFL)

Download from [Google Fonts](https://fonts.google.com/) and place in `fonts/` directory.

**Key Files**:
- `src/holiday_card/core/models.py`: TextElement.font_file field
- `src/holiday_card/renderers/reportlab_renderer.py`: Font registration logic

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

**Decorative Elements** (removed):
Pre-built shape compositions lived in `decorative_elements/` and were
expanded by `core/decorative.py`. Both were removed during Wave 2
(the YAML library in PR #8, the Python loader in Step 5). To re-add
support, port `DecorativeElement` lowering into `core/compiler.py`.

**Usage in Templates**:
```yaml
panels:
  - position: front
    shape_elements:
      - type: rectangle
        x: 1.0
        y: 2.0
        width: 3.0
        height: 1.5
        fill_color: "#A8B5A0"
        opacity: 0.8
        z_index: 1
```

**Key Files**:
- `src/holiday_card/core/models.py`: Shape model definitions
- `src/holiday_card/core/compiler.py`: Card → RenderCommand lowering
- `src/holiday_card/renderers/reportlab_backend.py`: IR → PDF
- `specs/003-vector-graphics-and/`: Original feature specification

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
