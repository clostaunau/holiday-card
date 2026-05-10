# holiday-card Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-14 (Valentine's Day Release!)

## Active Technologies
- Python 3.11+ + ReportLab 4.0+ (PDF generation with path/gradient support, TTF/OTF font embedding), Pillow 10.0+ (image processing for masks and effects), Pydantic 2.0+ (model validation), Typer 0.9+, PyYAML 6.0+
- Filesystem - YAML templates with valentine occasion, image effects, photo frames, custom fonts
- Valentine's Day 2026 Release: Added valentine occasion, heart clipping, image effects, photo frames, custom font support

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
      reportlab_renderer.py  # ReportLab PDF renderer (with custom fonts)
      shape_renderer.py   # Vector shape rendering
      clipping_renderer.py  # Clipping masks (including heart)
      image_effects.py    # Image effects (NEW: sepia, grayscale, vignette, blur)
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
    geometric.yaml
  hanukkah/
  birthday/
  generic/
  valentine/              # NEW: Valentine's Day templates
    hearts.yaml           # Classic hearts design
    cupid.yaml            # Cupid's arrow theme
    elegant.yaml          # Elegant burgundy & gold
decorative_elements/      # Pre-built decorative element library
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
  valentine/              # NEW: Valentine's decorative elements
    heart_simple.yaml     # Geometric heart
    heart_outline.yaml    # SVG path heart outline
    arrow_heart.yaml      # Cupid's arrow through heart
    love_birds.yaml       # Two birds with heart
themes/                   # Color theme definitions
  christmas.yaml
  hanukkah.yaml
  birthday.yaml
  generic.yaml
  valentine.yaml          # NEW: 3 Valentine's themes
fonts/                    # NEW: Custom font directory
  # Place TTF/OTF fonts here for custom typography
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
- **2026-02-14 Valentine's Day Release (v2.0.0)**:
  - Added VALENTINE occasion type with 3 templates and 3 themes
  - Added heart-shaped photo clipping masks
  - Added image effects (grayscale, sepia, vignette, blur)
  - Added photo frame styles (simple, rounded, shadow, polaroid)
  - Added custom font support (TTF/OTF embedding)
  - Created 4 Valentine's decorative elements (hearts, cupid arrow, love birds)

- 004-vector-graphics-enhancement: Added Python 3.11+ + ReportLab 4.0+ (PDF generation with path/gradient support), Pillow 10.0+ (image processing for masks), Pydantic 2.0+ (model validation)
- 003-vector-graphics-and-decorative-elements: Added vector graphics support with 5 shape types (Rectangle, Circle, Triangle, Star, Line), z-index layering, opacity/rotation/stroke styling, and decorative element library with 10 pre-built compositions
- 001-holiday-card-generator: Added Python 3.11+ + ReportLab 4.0+, Pillow 10.0+, Typer 0.9+, PyYAML 6.0+, Pydantic 2.0+

## Features

### Valentine's Day Support (2026-02-14 Release)

**Occasion Type**: `valentine`

**Themes** (in `themes/valentine.yaml`):
- `valentine-classic`: Traditional reds and pinks (Crimson #DC143C)
- `valentine-blush`: Soft blush and rose gold tones (Old Rose #DE8F94)
- `valentine-burgundy`: Rich burgundy and gold (Burgundy #800020)

**Templates**:
- `valentine-hearts`: Romantic cascading hearts design
- `valentine-cupid`: Playful Cupid's arrow with love birds
- `valentine-elegant`: Sophisticated burgundy and gold with minimalist border

**Decorative Elements**:
- `heart_simple`: Geometric heart (circles + triangle composition)
- `heart_outline`: SVG path heart with clean curves
- `arrow_heart`: Cupid's arrow piercing through heart
- `love_birds`: Two birds facing each other with heart accent

**Usage**:
```bash
# List Valentine's templates
python -m holiday_card templates --occasion valentine

# Create Valentine's card
python -m holiday_card create valentine-hearts \
  -m "Be Mine!" \
  --inside-message "You make my heart smile" \
  -o valentine.pdf
```

### Enhanced Photo Features (2026-02-14 Release)

**Heart-Shaped Clipping**:
- New `HeartClipMask` type for heart-shaped photo clipping
- Uses cubic Bezier curves for smooth, professional results
- Adjustable center position and size

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
      type: heart          # Heart-shaped clipping!
      center_x: 1.25
      center_y: 1.25
      size: 2.5
    effects:
      sepia: true
      vignette: 0.4
    frame_style: polaroid
    frame_color: "#FFFFFF"
    frame_width: 0.02
```

**Supported Clip Mask Types**:
- `circle`, `rectangle`, `ellipse`, `star`, `svg_path`, `heart` (NEW!)

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
