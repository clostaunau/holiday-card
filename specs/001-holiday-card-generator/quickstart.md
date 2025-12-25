# Quickstart Guide: Holiday Card Generator

**Feature**: 001-holiday-card-generator
**Date**: 2025-12-25

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Color laser printer (for printing cards)

---

## Installation

### 1. Clone and Setup

```bash
cd holiday-card
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Verify Installation

```bash
holiday-card --version
# Output: holiday-card 1.0.0

holiday-card templates
# Should list available templates
```

---

## Quick Start

### Create Your First Card

```bash
# Create a simple Christmas card
holiday-card create christmas-classic --message "Merry Christmas!"

# Output: Card created: ./output/christmas-classic-2025-12-25.pdf
```

### Preview Before Printing

```bash
# Generate a preview image
holiday-card preview christmas-classic --message "Season's Greetings"

# Opens: ./output/christmas-classic-preview.png
```

### Print the Card

1. Open the generated PDF in your preferred viewer
2. Print on 8.5" x 11" paper (Letter size)
3. Fold along the dashed fold lines
4. Your card is ready!

---

## Common Use Cases

### Birthday Card with Photo

```bash
holiday-card create birthday-balloons \
  --message "Happy Birthday!" \
  --image ./photos/birthday-photo.jpg \
  --output birthday-2025.pdf
```

### Custom Theme

```bash
# List available themes
holiday-card themes

# Apply a different theme
holiday-card create christmas-classic \
  --theme winter-blue \
  --message "Warm Winter Wishes"
```

### Quarter-Fold Card (Smaller Size)

```bash
holiday-card create christmas-modern \
  --fold-type quarter_fold \
  --message "Joy to You"
```

---

## Fold Types Explained

| Type | Folded Size | Best For |
|------|-------------|----------|
| half_fold | 5.5" x 8.5" | Standard greeting cards |
| quarter_fold | 4.25" x 5.5" | Compact cards, gift tags |
| tri_fold | 3.67" x 8.5" | Brochure-style cards |

### Folding Instructions

**Half-Fold**:
1. Fold paper in half along horizontal dashed line
2. Front panel faces outward

**Quarter-Fold**:
1. Fold paper in half horizontally
2. Fold again vertically
3. Front panel is bottom-right quadrant

**Tri-Fold**:
1. Fold left panel inward
2. Fold right panel over left
3. Creates accordion-style card

---

## Template Customization

### View Template Details

```bash
holiday-card templates --format json | jq '.templates[0]'
```

### Create Custom Template

```bash
# Initialize new template
holiday-card init my-custom-card --occasion birthday

# Edit the generated file
# ./templates/my-custom-card.yaml
```

### Template Structure

```yaml
id: "my-custom-card"
name: "My Custom Card"
occasion: "birthday"
fold_type: "half_fold"
default_theme_id: "birthday-pastel"

panel_layouts:
  - position: "front"
    text_zones:
      - id: "greeting"
        x: 0.5          # inches from left
        y: 2.0          # inches from bottom
        width: 4.5      # max text width
        default_content: "Happy Birthday!"
```

---

## Troubleshooting

### "Template not found"

```bash
# List available templates
holiday-card templates

# Check template path
ls ./templates/
```

### "Image file not supported"

Supported formats: PNG, JPG, JPEG

```bash
# Convert image if needed
convert input.webp output.png
```

### Print Quality Issues

- Use 300 DPI for best results
- Ensure printer is set to "Letter" (8.5" x 11")
- Select "Actual Size" (no scaling)

---

## Next Steps

1. Browse all templates: `holiday-card templates`
2. Explore themes: `holiday-card themes`
3. Create custom templates: `holiday-card init`
4. Read full documentation: `holiday-card --help`

---

## Development Setup

For contributors:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=holiday_card --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/
```
