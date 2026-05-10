# 🚀 Quick Setup & Usage Guide

## 1. Create Virtual Environment

```bash
# Create virtual environment (will be ignored by git)
python3 -m venv venv

# Activate it
source venv/bin/activate

# Your prompt should now show (venv) prefix
```

## 2. Install the Package

```bash
# Install holiday-card and all dev tools (single source of truth: pyproject.toml)
pip install -e ".[dev]"

# Verify the console entry point is on PATH
holiday-card --help
```

## 3. Generate Your First Valentine's Card!

```bash
# List available Valentine's templates
holiday-card templates --occasion valentine

# Create a Valentine's card
holiday-card create valentine-hearts \
  -m "Happy Valentine's Day!" \
  --inside-message "You mean the world to me" \
  -o output/my-valentine.pdf

# The card will be saved to output/my-valentine.pdf
```

## 4. Try Different Templates

```bash
# Cupid's arrow design
holiday-card create valentine-cupid \
  -m "Be My Valentine!" \
  --inside-message "Every love story is beautiful, but ours is my favorite." \
  -o output/cupid-card.pdf

# Elegant burgundy & gold
holiday-card create valentine-elegant \
  -m "With Love" \
  --inside-message "You are my today and all of my tomorrows." \
  -o output/elegant-card.pdf
```

## 5. Use Custom Themes

```bash
# List available themes
holiday-card themes --occasion valentine

# Create card with specific theme
holiday-card create valentine-hearts \
  -t valentine-blush \
  -m "You Make My Heart Smile" \
  -o output/blush-card.pdf
```

## 6. View All Available Commands

```bash
# See all commands
holiday-card --help

# Get help for specific command
holiday-card create --help
holiday-card templates --help
holiday-card themes --help
```

## 7. Check Your Output

```bash
# Open the generated card
open output/my-valentine.pdf

# Or on Linux:
# xdg-open output/my-valentine.pdf
```

## 8. Deactivate Virtual Environment When Done

```bash
deactivate
```

---

## 🎨 Advanced: Create Custom Cards

### Add Your Own Photo

1. Place your photo in the project directory (e.g., `my-photo.jpg`)
2. Create a custom template or use the CLI with image flag:

```bash
holiday-card create valentine-hearts \
  -i my-photo.jpg \
  -m "Our Love Story" \
  -o output/photo-card.pdf
```

### Use Custom Fonts

1. Download romantic fonts from [Google Fonts](https://fonts.google.com/)
   - Great Vibes (script)
   - Playfair Display (serif)
   - Lora (elegant serif)

2. Place TTF/OTF files in `fonts/` directory

3. Create a custom template referencing your fonts (see templates for examples)

---

## 🐛 Troubleshooting

**"No module named 'holiday_card'" / "command not found: holiday-card"**
- The package isn't installed in your active environment.
- Run `pip install -e ".[dev]"` from the repo root.

**"No module named 'reportlab'"**
- Your virtual environment isn't activated.
- Run `source venv/bin/activate` first, then `pip install -e ".[dev]"`.

**"Template not found"**
- Check spelling of template name.
- Run `holiday-card templates` to see available names.

---

Happy card making! 💝
