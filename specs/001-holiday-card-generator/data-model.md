# Data Model: Holiday Card Generator

**Feature**: 001-holiday-card-generator
**Date**: 2025-12-25
**Status**: Draft

## Entity Relationship Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Card     │────▶│   Template  │────▶│    Theme    │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│    Panel    │────▶│  TextElement│
└─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ImageElement │     │   Border    │
└─────────────┘     └─────────────┘
```

---

## Core Entities

### Card

The complete greeting card design containing all elements and configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier (UUID) |
| name | string | Yes | User-friendly name for the card |
| template_id | string | Yes | Reference to base template |
| fold_type | FoldType | Yes | half_fold, quarter_fold, tri_fold |
| theme_id | string | No | Override theme (uses template default if null) |
| panels | Panel[] | Yes | List of panel configurations |
| output_path | string | No | Target PDF file path |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last modification timestamp |

**Validation Rules**:
- name: 1-100 characters
- Must have at least 1 panel
- fold_type must be valid enum value

**State Transitions**:
- `draft` → `preview` → `generated`
- Can return to `draft` from any state for modifications

---

### FoldType (Enum)

| Value | Dimensions (folded) | Panels | Description |
|-------|---------------------|--------|-------------|
| half_fold | 5.5" x 8.5" | 4 | Single horizontal fold |
| quarter_fold | 4.25" x 5.5" | 4 | Two folds (horizontal + vertical) |
| tri_fold | 3.67" x 8.5" | 3 | Two vertical folds |

---

### Template

Pre-designed card layout with placeholder areas for customization.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| name | string | Yes | Display name |
| occasion | OccasionType | Yes | christmas, hanukkah, birthday, generic |
| fold_type | FoldType | Yes | Default fold type for template |
| default_theme_id | string | Yes | Reference to default theme |
| panel_layouts | PanelLayout[] | Yes | Panel configuration definitions |
| description | string | No | Template description |
| preview_image | string | No | Path to preview thumbnail |

**Validation Rules**:
- name: 1-50 characters
- Must have panel_layouts matching fold_type requirements

---

### OccasionType (Enum)

| Value | Description |
|-------|-------------|
| christmas | Christmas/winter holiday |
| hanukkah | Hanukkah celebration |
| birthday | Birthday celebration |
| generic | Generic/all-purpose |
| new_year | New Year celebration |
| thanksgiving | Thanksgiving |

---

### Theme

Coordinated color scheme for card design.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| name | string | Yes | Display name |
| occasion | OccasionType | Yes | Associated occasion |
| primary_color | Color | Yes | Main accent color |
| secondary_color | Color | Yes | Secondary accent |
| background_color | Color | Yes | Default background |
| text_color | Color | Yes | Default text color |
| accent_color | Color | No | Additional highlight color |

**Validation Rules**:
- All color values must be valid (RGB 0.0-1.0 or hex)

---

### Color (Value Object)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| r | float | Yes | Red component (0.0-1.0) |
| g | float | Yes | Green component (0.0-1.0) |
| b | float | Yes | Blue component (0.0-1.0) |

**Validation Rules**:
- All values must be between 0.0 and 1.0

---

### Panel

A distinct section of the card (front, back, inside panels).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| position | PanelPosition | Yes | front, back, inside_left, inside_right |
| x | float | Yes | X position in inches from page origin |
| y | float | Yes | Y position in inches from page origin |
| width | float | Yes | Panel width in inches |
| height | float | Yes | Panel height in inches |
| rotation | float | No | Rotation in degrees (for quarter-fold) |
| background_color | Color | No | Panel background color |
| background_image | string | No | Path to background image |
| text_elements | TextElement[] | No | Text content on panel |
| image_elements | ImageElement[] | No | Images on panel |
| border | Border | No | Optional border decoration |

**Validation Rules**:
- x, y must be >= 0 and within page bounds
- width, height must be > 0 and fit within page
- rotation must be 0, 90, 180, or 270

---

### PanelPosition (Enum)

| Value | Description |
|-------|-------------|
| front | Card front (visible when folded) |
| back | Card back |
| inside_left | Inside left panel |
| inside_right | Inside right panel |
| center | Center panel (tri-fold only) |

---

### TextElement

Text content with positioning and styling.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| content | string | Yes | Text content |
| x | float | Yes | X position relative to panel (inches) |
| y | float | Yes | Y position relative to panel (inches) |
| width | float | No | Max width for text wrapping |
| font_family | string | Yes | Font family name |
| font_size | int | Yes | Font size in points |
| font_style | FontStyle | No | normal, bold, italic |
| color | Color | No | Text color (uses theme default if null) |
| alignment | TextAlignment | No | left, center, right |
| rotation | float | No | Rotation in degrees |

**Validation Rules**:
- content: 1-1000 characters
- font_size: 6-144 points
- x, y must be within panel bounds respecting safe margin

---

### TextAlignment (Enum)

| Value | Description |
|-------|-------------|
| left | Left-aligned text |
| center | Center-aligned text |
| right | Right-aligned text |

---

### FontStyle (Enum)

| Value | Description |
|-------|-------------|
| normal | Regular weight |
| bold | Bold weight |
| italic | Italic style |
| bold_italic | Bold and italic |

---

### ImageElement

Imported graphic with positioning and scaling.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| source_path | string | Yes | Path to source image file |
| x | float | Yes | X position relative to panel (inches) |
| y | float | Yes | Y position relative to panel (inches) |
| width | float | Yes | Display width in inches |
| height | float | No | Display height (auto if null, preserves aspect) |
| preserve_aspect | bool | Yes | Whether to maintain aspect ratio |
| opacity | float | No | Opacity (0.0-1.0), default 1.0 |
| rotation | float | No | Rotation in degrees |

**Validation Rules**:
- source_path must be valid file path
- Supported formats: PNG, JPG, JPEG
- width must be > 0
- opacity must be 0.0-1.0
- Position must respect 0.25" safe margin from panel edges

---

### Border

Decorative frame for panels.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| style | BorderStyle | Yes | solid, dashed, dotted, decorative |
| width | float | Yes | Border width in points |
| color | Color | Yes | Border color |
| corner_radius | float | No | Rounded corner radius in points |
| pattern | string | No | Pattern name for decorative style |
| margin | float | No | Inset from panel edge in inches |

**Validation Rules**:
- width: 0.5-10 points
- margin must be >= 0.25" (safe zone)

---

### BorderStyle (Enum)

| Value | Description |
|-------|-------------|
| solid | Solid line border |
| dashed | Dashed line border |
| dotted | Dotted line border |
| decorative | Custom decorative pattern |
| none | No border |

---

## Measurement Constants

| Constant | Value | Description |
|----------|-------|-------------|
| PAGE_WIDTH | 8.5 inches | Letter paper width |
| PAGE_HEIGHT | 11 inches | Letter paper height |
| SAFE_MARGIN | 0.25 inches | Minimum margin from edges |
| POINTS_PER_INCH | 72 | PDF points per inch |
| FOLD_LINE_WIDTH | 0.5 points | Default fold line thickness |
| CUT_LINE_WIDTH | 1.0 points | Default cut guide thickness |
| MIN_DPI | 150 | Minimum image DPI for print |
| RECOMMENDED_DPI | 300 | Recommended image DPI |

---

## Fold Type Panel Layouts

### Half-Fold (5.5" x 8.5" folded)
```
┌───────────────────────────────┐
│  inside_left  │  inside_right │
│   (5.5x8.5)   │   (5.5x8.5)   │
├───────────────┼───────────────┤ ← fold line
│     back      │     front     │
│   (5.5x8.5)   │   (5.5x8.5)   │
└───────────────────────────────┘
```

### Quarter-Fold (4.25" x 5.5" folded)
```
┌───────────────┬───────────────┐
│  inside_left  │  inside_right │
│   (4.25x5.5)  │   (4.25x5.5)  │
│   (upright)   │   (upright)   │
├───────────────┼───────────────┤ ← horizontal fold
│     back      │     front     │
│  (4.25x5.5)   │  (4.25x5.5)   │
│  (inverted)   │   (upright)   │
└───────────────┴───────────────┘
        ↑ vertical fold
```

### Tri-Fold (3.67" x 8.5" panels)
```
┌──────────┬──────────┬──────────┐
│   left   │  center  │   right  │
│ (3.67x11)│ (3.67x11)│ (3.67x11)│
└──────────┴──────────┴──────────┘
     ↑ fold    ↑ fold
```

---

## File Format Specifications

### Template YAML Schema
```yaml
id: "christmas-classic-01"
name: "Classic Christmas"
occasion: "christmas"
fold_type: "half_fold"
default_theme_id: "christmas-red-green"
description: "Traditional Christmas card with holly border"
panel_layouts:
  - position: "front"
    text_zones:
      - id: "greeting"
        x: 0.5
        y: 2.0
        width: 4.5
        default_content: "Merry Christmas"
    image_zones:
      - id: "main_image"
        x: 1.0
        y: 4.0
        width: 3.5
        height: 3.0
```

### Theme YAML Schema
```yaml
id: "christmas-red-green"
name: "Classic Christmas"
occasion: "christmas"
primary_color: {r: 0.8, g: 0.1, b: 0.1}
secondary_color: {r: 0.2, g: 0.5, b: 0.2}
background_color: {r: 1.0, g: 1.0, b: 1.0}
text_color: {r: 0.1, g: 0.1, b: 0.1}
accent_color: {r: 1.0, g: 0.84, b: 0.0}
```
