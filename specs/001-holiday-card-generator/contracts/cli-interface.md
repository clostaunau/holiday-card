# CLI Interface Contract: Holiday Card Generator

**Feature**: 001-holiday-card-generator
**Date**: 2025-12-25
**Version**: 1.0.0

## Overview

The Holiday Card Generator provides a command-line interface for creating printable greeting cards. All commands follow Unix conventions for arguments and output.

---

## Global Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --help | -h | flag | - | Show help message |
| --version | -V | flag | - | Show version number |
| --verbose | -v | flag | false | Enable verbose output |
| --quiet | -q | flag | false | Suppress non-error output |
| --output-dir | -o | path | ./output | Default output directory |

---

## Commands

### `holiday-card create`

Create a new card from a template.

**Usage**:
```bash
holiday-card create <template> [options]
```

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| template | Yes | Template name or path to template YAML |

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --message | -m | string | - | Greeting message text |
| --theme | -t | string | - | Theme name (overrides template default) |
| --fold-type | -f | enum | template | half_fold, quarter_fold, tri_fold |
| --output | -o | path | auto | Output PDF file path |
| --preview | -p | flag | false | Generate preview image instead of PDF |
| --image | -i | path | - | Add image (repeatable) |
| --name | -n | string | auto | Card name for identification |

**Exit Codes**:
| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid template |
| 3 | Invalid theme |
| 4 | File I/O error |
| 5 | Invalid image file |

**Examples**:
```bash
# Create Christmas card with default settings
holiday-card create christmas-classic -m "Merry Christmas!"

# Create card with custom theme and output path
holiday-card create christmas-classic \
  --message "Happy Holidays!" \
  --theme winter-blue \
  --output ./cards/holiday-2025.pdf

# Create quarter-fold birthday card with image
holiday-card create birthday-fun \
  --fold-type quarter_fold \
  --message "Happy Birthday!" \
  --image ./photos/party.jpg \
  --output birthday-card.pdf
```

**Output (stdout)**:
```
Card created: ./output/christmas-classic-2025-12-25.pdf
  Template: christmas-classic
  Theme: christmas-red-green
  Fold: half_fold
  Size: 8.5" x 11"
```

---

### `holiday-card templates`

List available templates.

**Usage**:
```bash
holiday-card templates [options]
```

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --occasion | -o | enum | all | Filter by occasion type |
| --fold-type | -f | enum | all | Filter by fold type |
| --format | | enum | table | Output format: table, json, yaml |

**Examples**:
```bash
# List all templates
holiday-card templates

# List Christmas templates only
holiday-card templates --occasion christmas

# List as JSON
holiday-card templates --format json
```

**Output (table format)**:
```
NAME                OCCASION    FOLD TYPE      DESCRIPTION
christmas-classic   christmas   half_fold      Traditional Christmas with holly
christmas-modern    christmas   quarter_fold   Modern minimalist design
hanukkah-menorah    hanukkah    half_fold      Classic menorah design
birthday-balloons   birthday    quarter_fold   Fun balloon theme
```

**Output (JSON format)**:
```json
{
  "templates": [
    {
      "id": "christmas-classic",
      "name": "Classic Christmas",
      "occasion": "christmas",
      "fold_type": "half_fold",
      "description": "Traditional Christmas with holly border"
    }
  ]
}
```

---

### `holiday-card themes`

List available color themes.

**Usage**:
```bash
holiday-card themes [options]
```

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --occasion | -o | enum | all | Filter by occasion type |
| --format | | enum | table | Output format: table, json, yaml |

**Examples**:
```bash
# List all themes
holiday-card themes

# List Christmas themes as JSON
holiday-card themes --occasion christmas --format json
```

**Output**:
```
NAME                OCCASION    COLORS
christmas-red-green christmas   Red (#CC1111), Green (#228B22)
christmas-gold      christmas   Gold (#FFD700), Burgundy (#800020)
winter-blue         christmas   Ice Blue (#B0E0E6), Silver (#C0C0C0)
hanukkah-blue       hanukkah    Blue (#0000CD), White (#FFFFFF)
```

---

### `holiday-card preview`

Generate a preview image of a card design.

**Usage**:
```bash
holiday-card preview <template> [options]
```

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| template | Yes | Template name or path |

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --message | -m | string | - | Greeting message |
| --theme | -t | string | - | Theme override |
| --format | | enum | png | Output format: png, jpg |
| --dpi | | int | 150 | Preview resolution |
| --output | -o | path | auto | Output file path |
| --show-guides | -g | flag | true | Show fold/cut lines |

**Examples**:
```bash
# Preview card design
holiday-card preview christmas-classic --message "Season's Greetings"

# High-resolution preview
holiday-card preview christmas-classic --dpi 300 --output preview.png
```

---

### `holiday-card validate`

Validate a template or card configuration.

**Usage**:
```bash
holiday-card validate <path> [options]
```

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| path | Yes | Path to template YAML or card config |

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --strict | -s | flag | false | Enable strict validation |

**Exit Codes**:
| Code | Description |
|------|-------------|
| 0 | Valid |
| 1 | Invalid with errors |
| 2 | Valid with warnings |

**Output**:
```
Validating: custom-template.yaml
  [PASS] Schema valid
  [PASS] Colors within valid range
  [PASS] Panel dimensions correct
  [WARN] Image zone exceeds recommended size
Result: VALID (1 warning)
```

---

### `holiday-card init`

Initialize a new custom template.

**Usage**:
```bash
holiday-card init <name> [options]
```

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| name | Yes | Name for the new template |

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --occasion | -o | enum | generic | Occasion type |
| --fold-type | -f | enum | half_fold | Fold type |
| --output-dir | -d | path | ./templates | Where to create template |

**Examples**:
```bash
# Create new Christmas template
holiday-card init my-christmas --occasion christmas --fold-type quarter_fold
```

**Output**:
```
Created template: ./templates/my-christmas.yaml
Edit this file to customize your template design.
```

---

## Standard Input/Output

### stdin Support

Commands that accept `--message` also support stdin for multi-line content:

```bash
echo "Wishing you joy and happiness!" | holiday-card create christmas-classic --message -
```

### JSON Output Mode

All commands support `--format json` for machine-readable output:

```bash
holiday-card create christmas-classic --format json
```

```json
{
  "status": "success",
  "output_path": "./output/christmas-classic-2025-12-25.pdf",
  "template": "christmas-classic",
  "theme": "christmas-red-green",
  "fold_type": "half_fold",
  "dimensions": {
    "width": 8.5,
    "height": 11,
    "unit": "inches"
  }
}
```

---

## Error Output

Errors are written to stderr with consistent format:

```
Error: Invalid template 'nonexistent'
  Available templates: christmas-classic, christmas-modern, birthday-fun
  Run 'holiday-card templates' to see all options.
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| HOLIDAY_CARD_TEMPLATES | Path to templates directory | ./templates |
| HOLIDAY_CARD_OUTPUT | Default output directory | ./output |
| HOLIDAY_CARD_THEME | Default theme | - |
| NO_COLOR | Disable colored output | - |
