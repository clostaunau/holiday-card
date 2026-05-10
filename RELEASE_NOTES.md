# 🎀 Holiday Card Generator - Valentine's Day Edition Release Notes

**Release Date:** February 14, 2026 (Valentine's Day!)
**Version:** 2.0.0 - "Love is in the Air"

---

## 🌟 What's New

We're thrilled to release a major update to the Holiday Card Generator, perfectly timed for Valentine's Day! This release transforms the tool from a Christmas-focused card maker into a comprehensive greeting card platform with powerful new features for creating stunning, personalized Valentine's Day cards (and cards for any occasion).

---

## 🎯 Three Major Features

### 1. 💝 Complete Valentine's Day Support Package

**Never miss Valentine's Day again!** We've added comprehensive Valentine's Day support with everything you need to create beautiful romantic cards.

#### What's Included:

**New Occasion Type:**
- Added `valentine` to the OccasionType enum
- Fully integrated with template discovery and filtering

**Three Valentine's Themes:**
- **Classic Romance** - Traditional Valentine's reds and pinks (Crimson #DC143C, Light Pink #FFB6C1)
- **Soft Blush** - Gentle blush and rose gold tones (Old Rose #DE8F94, Dusty Rose #B86E78)
- **Elegant Burgundy** - Rich burgundy and gold for a sophisticated look (Burgundy #800020, Dark Gold #D4AF37)

**Four Heart-Themed Decorative Elements:**
- `heart_simple` - Geometric heart composed of circles and triangles
- `heart_outline` - Elegant SVG path heart outline
- `arrow_heart` - Cupid's arrow piercing through a heart
- `love_birds` - Two stylized birds facing each other with a heart between them

**Three Ready-to-Use Templates:**
- **Valentine Hearts** (`valentine-hearts`) - Romantic card with cascading hearts
- **Cupid's Arrow** (`valentine-cupid`) - Playful design with arrow and love birds
- **Elegant Valentine** (`valentine-elegant`) - Sophisticated burgundy and gold with minimalist border

#### Usage Example:

```bash
# List all Valentine's templates
holiday-card templates --occasion valentine

# Create a Valentine's card
holiday-card create valentine-hearts \
  -m "Be Mine Forever!" \
  --inside-message "Every moment with you is precious" \
  -o my-valentine-card.pdf

# Create with a custom theme
holiday-card create valentine-cupid \
  -t valentine-blush \
  -m "You Make My Heart Smile" \
  -o romantic-card.pdf
```

---

### 2. 📸 Enhanced Photo Features with Heart-Shaped Clipping

**Make your cards truly personal** with advanced photo capabilities perfect for romantic Valentine's cards.

#### New Capabilities:

**Heart-Shaped Photo Clipping:**
- Clip your favorite photos into perfect heart shapes
- Adjustable size and positioning
- Smooth Bezier curves for professional results

**Image Effects:**
- **Grayscale** - Classic black & white romantic look
- **Sepia** - Vintage, nostalgic tone
- **Vignette** - Dramatic edge darkening (0.0-1.0 intensity)
- **Blur** - Soft focus effects (0-10 pixel radius)

**Photo Frame Styles:**
- **Simple** - Clean border around photos
- **Rounded** - Soft rounded corners
- **Shadow** - Subtle drop shadow for depth
- **Polaroid** - Instant camera aesthetic with white border and bottom caption space

#### Usage in Templates:

```yaml
panels:
  - position: front
    image_elements:
      - id: couple_photo
        source_path: "photos/us-together.jpg"
        x: 1.0
        y: 2.0
        width: 2.5
        height: 2.5
        # Heart-shaped clipping!
        clip_mask:
          type: heart
          center_x: 1.25
          center_y: 1.25
          size: 2.5
        # Apply romantic effects
        effects:
          sepia: true
          vignette: 0.4
        # Polaroid frame for vintage look
        frame_style: polaroid
        frame_color: "#FFFFFF"
        frame_width: 0.02
        z_index: 50
```

#### Supported Clip Mask Types:

Now includes: `circle`, `rectangle`, `ellipse`, `star`, `svg_path`, and **`heart`** (new!)

---

### 3. ✍️ Custom Font Support for Romantic Typography

**Elevate your cards with beautiful custom fonts** - perfect for romantic script and elegant typography.

#### Features:

**Font Embedding:**
- Full support for TTF and OTF font files
- Automatic font registration with ReportLab
- Graceful fallback to built-in fonts if custom fonts fail

**Bundled Fonts Directory:**
- Place custom fonts in the `fonts/` directory at project root
- Automatic discovery and resolution
- Support for subdirectories and organization

**Font Validation:**
- Validates font file formats (.ttf, .otf)
- Clear error messages for debugging
- Safe handling of missing or corrupted fonts

#### Usage in Templates:

```yaml
text_elements:
  - id: greeting
    content: "With All My Love"
    x: 2.125
    y: 0.8
    width: 3.5
    font_family: "GreatVibes"
    font_file: "GreatVibes-Regular.ttf"  # Resolved from fonts/
    font_size: 32
    font_style: normal
    alignment: center
    color:
      r: 0.5
      g: 0.0
      b: 0.13
```

#### Programmatic Usage:

```python
from holiday_card.core.models import TextElement

text = TextElement(
    content="Forever Yours",
    x=1.0,
    y=2.0,
    width=4.0,
    font_family="PlayfairDisplay",
    font_file="fonts/PlayfairDisplay-Regular.ttf",
    font_size=28,
    font_style="normal"
)
```

#### Recommended Fonts (Open Source):

For romantic Valentine's cards, we recommend these free, open-source fonts:

1. **Great Vibes** - Elegant script font (SIL OFL license)
2. **Playfair Display** - Sophisticated serif (SIL OFL license)
3. **Lora** - Elegant serif for body text (SIL OFL license)

Download from [Google Fonts](https://fonts.google.com/) and place in the `fonts/` directory.

---

## 🔧 Technical Details

### Modified Files:

1. **`src/holiday_card/core/models.py`**
   - Added `VALENTINE` to `OccasionType` enum
   - Added `HeartClipMask` model
   - Updated `ClipMask` discriminated union
   - Added `ImageEffectType`, `ImageEffects`, `PhotoFrameStyle` enums/models
   - Extended `ImageElement` with `effects`, `frame_style`, `frame_color`, `frame_width`
   - Extended `TextElement` with `font_file` field

2. **`src/holiday_card/renderers/clipping_renderer.py`**
   - Added `create_heart_path()` method with Bezier curve implementation
   - Updated `apply_clip_mask()` to handle heart type

3. **`src/holiday_card/renderers/reportlab_renderer.py`**
   - Added `_render_photo_frame()` method for frame rendering
   - Added `_register_custom_font()` for TTF/OTF font embedding
   - Added `_resolve_bundled_font()` for font discovery
   - Updated `_get_font_name()` to accept `font_file` parameter
   - Updated `render_image()` to apply effects and frames

4. **`src/holiday_card/renderers/image_effects.py`** (NEW)
   - Image processing pipeline using Pillow
   - `apply_grayscale()`, `apply_sepia()`, `apply_blur()`, `apply_vignette()`

### New Files:

**Themes:**
- `themes/valentine.yaml` - 3 Valentine's color themes

**Decorative Elements:**
- `decorative_elements/valentine/heart_simple.yaml`
- `decorative_elements/valentine/heart_outline.yaml`
- `decorative_elements/valentine/arrow_heart.yaml`
- `decorative_elements/valentine/love_birds.yaml`

**Templates:**
- `templates/valentine/hearts.yaml`
- `templates/valentine/cupid.yaml`
- `templates/valentine/elegant.yaml`

**Fonts Directory:**
- `fonts/` - Directory for custom font files

---

## ✅ Backward Compatibility

**100% Backward Compatible!** All changes are additive:

- Existing templates, themes, and decorative elements work unchanged
- New enum values don't break existing code
- New model fields have sensible defaults (`effects=None`, `frame_style="none"`, `font_file=None`)
- Custom font loading fails gracefully to built-in fonts
- All existing CLI commands continue to work

---

## 📊 Quality Assurance

**All files validated:**
- ✓ All Python files compile without syntax errors
- ✓ All YAML templates are valid and well-formed
- ✓ All decorative elements use correct schema
- ✓ All themes follow established patterns
- ✓ Model validation works correctly
- ✓ Type hints preserved throughout

---

## 🎨 Design Philosophy

This release follows three key principles:

1. **Extensibility** - Valentine's support demonstrates the pattern for adding any occasion
2. **User Experience** - Beautiful defaults that just work, with power when you need it
3. **Quality** - Every feature is production-ready with proper error handling and validation

---

## 💡 Quick Start Guide

### Create Your First Valentine's Card:

```bash
# 1. List available templates
holiday-card templates --occasion valentine

# 2. Generate a card with your message
holiday-card create valentine-hearts \
  -m "Happy Valentine's Day!" \
  --inside-message "You mean the world to me" \
  -o valentine.pdf

# 3. Open and print!
open valentine.pdf
```

### Add Your Photo:

Create a custom template with a heart-shaped photo:

```yaml
id: my-valentine
name: "My Valentine Photo Card"
occasion: valentine
fold_type: half_fold
default_theme_id: valentine-classic

panels:
  - id: front
    position: front
    x: 4.25
    y: 0
    width: 4.25
    height: 5.5

    image_elements:
      - source_path: "my-photo.jpg"
        x: 0.875
        y: 1.5
        width: 2.5
        height: 2.5
        clip_mask:
          type: heart
          center_x: 1.25
          center_y: 1.25
          size: 2.5
        effects:
          vignette: 0.3
        frame_style: shadow
```

---

## 🚀 What's Next?

This release lays the groundwork for:
- More occasion types (Easter, Mother's Day, Father's Day, etc.)
- Additional decorative element libraries
- More advanced photo effects
- Font pairing suggestions
- Template customization UI

---

## 🙏 Credits

Special thanks to:
- The Pydantic team for excellent validation
- ReportLab for powerful PDF generation
- Pillow for image processing capabilities
- The open-source font community

---

## 📝 License

This software is provided as-is. Font licenses vary - please check individual font licenses when using custom fonts.

---

## 📧 Support

Issues? Feature requests? Visit the GitHub repository and open an issue!

---

**Happy Valentine's Day! May your cards bring joy and love to everyone who receives them.** ❤️

---

*Generated with ❤️ by Claude Code on February 14, 2026*
