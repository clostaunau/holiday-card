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
      generators.py       # Card generation orchestration
      templates.py        # YAML template loading/discovery
      themes.py           # Theme definitions
      text_utils.py       # Text measurement primitives
      text_fitting.py     # Overflow strategies (extracted Wave 2 Step 2a)
      render_ir.py        # RenderCommand IR — backend-neutral seam (Wave 2 Step 1)
      compiler.py         # Card → list[RenderCommand] (Wave 2 Step 2b)
    renderers/
      base.py             # Legacy renderer protocol (slated for replacement)
      reportlab_renderer.py  # Legacy ReportLab renderer (default today)
      reportlab_backend.py   # IR-driven ReportLab renderer (Wave 2 Step 3)
      shape_renderer.py   # Legacy vector shape rendering
      clipping_renderer.py  # Clipping masks
      image_effects.py    # Pillow effects (sepia, grayscale, vignette, blur)
      preview_renderer.py # PNG preview generation
    cli/
      commands.py         # Typer CLI commands
    utils/
      measurements.py     # inch ↔ point conversions
      validators.py       # Input validation
tests/
  unit/                   # Unit tests (incl. test_render_ir, test_compiler, test_cli)
  integration/            # Integration tests (incl. test_ir_parity)
  visual/                 # Reserved for visual regression (no tests yet)
templates/                # Card template YAML files
  christmas/              # 11 templates (classic, modern, geometric, ...)
  hanukkah/               # 1 template
  birthday/               # 1 template
  generic/                # 1 template
themes/                   # Color theme definitions (christmas, hanukkah, birthday, generic)
fonts/                    # Custom TTF/OTF fonts (drop here, reference by font_file)
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

- **Wave 2 architecture refactor (in progress, 2026-05)**: Introduced a
  backend-neutral `RenderCommand` IR sitting between `Card` and the
  renderer. New `core/render_ir.py`, `core/compiler.py`,
  `renderers/reportlab_backend.py`. `core/text_fitting.py` extracted
  from the legacy renderer. The legacy `ReportLabRenderer` is still the
  default code path; cutover is the next PR.
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

**Decorative Elements** (deprecated; not supported by the Wave 2 compiler):
Pre-built shape compositions used to live in `decorative_elements/`. The
library was removed during the Wave 2 IR migration; the Python loader
(`core/decorative.py`) and the `DecorativeElement` model remain only
because the legacy renderer still references them, and will be deleted
in the Wave 2 Step 5 PR.

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
- `src/holiday_card/renderers/shape_renderer.py`: Legacy shape rendering
- `src/holiday_card/core/compiler.py`: IR-based shape compilation (Wave 2)
- `specs/003-vector-graphics-and/`: Original feature specification

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
