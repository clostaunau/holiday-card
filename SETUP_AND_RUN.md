# Quick Setup & Usage Guide

## 1. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 2. Install the package

```bash
# Single source of truth: pyproject.toml
pip install -e ".[dev]"

# Verify the console entry point is on PATH
holiday-card --help
```

## 3. Generate your first card

```bash
holiday-card create christmas-classic \
  -m "Merry Christmas!" \
  --inside-message "Wishing you joy and happiness this holiday season." \
  -o output/my-card.pdf
```

The PDF lands at `output/my-card.pdf`.

## 4. Try other templates

```bash
# Geometric Christmas tree
holiday-card create christmas-geometric \
  -m "Happy Holidays!" \
  -o output/geometric.pdf

# Birthday card with balloons
holiday-card create birthday-balloons \
  -m "Happy Birthday!" \
  --inside-message "Hope your day is amazing." \
  -o output/birthday.pdf

# Hanukkah menorah
holiday-card create hanukkah-menorah \
  -m "Happy Hanukkah!" \
  -o output/hanukkah.pdf

# Generic celebration
holiday-card create generic-celebration \
  -m "Congratulations!" \
  -o output/celebration.pdf
```

## 5. Use a different theme

```bash
# List themes
holiday-card themes
holiday-card themes --occasion christmas

# Apply a theme
holiday-card create christmas-classic \
  -t christmas-red-green \
  -m "Merry Christmas!" \
  -o output/themed.pdf
```

## 6. View all available commands

```bash
holiday-card --help
holiday-card create --help
holiday-card templates --help
holiday-card themes --help
holiday-card validate --help
```

## 7. Open the output

```bash
open output/my-card.pdf       # macOS
xdg-open output/my-card.pdf   # Linux
```

## 8. Deactivate when done

```bash
deactivate
```

---

## Advanced: custom cards

### Add your own photo

Use the `--image` / `-i` flag to add a photo to a card. The image is
placed on the front panel.

```bash
holiday-card create christmas-classic \
  -i my-photo.jpg \
  -m "Season's Greetings" \
  -o output/photo-card.pdf
```

### Use custom fonts

1. Download a font (e.g. from [Google Fonts](https://fonts.google.com/)):
   - Great Vibes (script)
   - Playfair Display (serif)
   - Lora (elegant serif)
2. Drop the `.ttf` / `.otf` file in `fonts/`.
3. Reference it from a template's `font_file` field. See the existing
   templates in `templates/` for examples.

---

## Troubleshooting

**`No module named 'holiday_card'` / `command not found: holiday-card`**
- The package isn't installed in your active environment.
- Run `pip install -e ".[dev]"` from the repo root.

**`No module named 'reportlab'`**
- Your virtual environment isn't activated.
- Run `source venv/bin/activate`, then `pip install -e ".[dev]"`.

**`Template not found`**
- Check spelling. Run `holiday-card templates` to see available names.
