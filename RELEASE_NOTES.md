# Holiday Card Generator — Release Notes

## v1.3.0 — "AI as plumbing, hard-railed" — 2026-06-02

L3 ships — the last named leapfrog the panel endorsed, in the narrow
shape it actually signed off on. AI imagery is an **authoring-time**
\`ai-asset generate\` subcommand that bakes one image to disk with a
provenance sidecar and **never** runs in the render path, so cards stay
reproducible. It is opt-in three layers deep (an \`[ai]\` extras install,
an \`OPENAI_API_KEY\`, and a logged first-use consent) and refuses by
default in every category the panel called radioactive. Only the L2
illustrator commission (a human contractor task) now remains of the
panel's leapfrogs.

### What's new for users

**\`holiday-card ai-asset generate\`.** An authoring-time subcommand that
generates one image and writes it to disk as a PNG plus a sibling
\`<asset>.license.yaml\` provenance sidecar. The card render pipeline
never calls the model — you commit the asset + sidecar to git and the
same YAML renders the same card forever.

```bash
pip install holiday-card[ai]
export OPENAI_API_KEY=sk-...

holiday-card ai-asset generate \
  --subject "watercolor pine bough border, sage green and burgundy" \
  --reference fonts/curated/motif.png --style watercolor \
  --occasion christmas --export-for moo-a6 --out assets/ai/border.png
```

**Hard category rails, default-on refusal.** Sympathy / condolence /
miscarriage / pet_loss occasions, religious iconography, trademarked
brands, and recognizable-likeness / photo-replacement prompts refuse by
default. Override with \`--i-know-what-im-doing\` — it prints every reason
first and records the overridden reasons into the sidecar. Refusals exit
with distinct codes (rail-blocked 5, consent-missing 3, missing
key/extra 4 — a clean error, never a traceback).

**Image-reference mode is the default.** \`--reference\` is required (the
style anchor that keeps output from being voiceless ChatGPT slop);
\`--unsafe-no-style-anchor\` opts out and is discouraged. AI never renders
text and never replaces a photo slot or a whole panel.

**POD-aware sizing + sRGB tagging.** The \`--export-for\` target's
trim+bleed geometry sizes the image at 300 DPI rounded to 16-px
multiples (so an A6 card gets 1312×1824, not a soft 1024²). Output is
tagged sRGB IEC61966-2.1.

**First-use consent.** A one-time acknowledgement (OpenAI usage policy,
IP responsibility, POD-disclosure obligation) logged under
\`$XDG_CONFIG_HOME/holiday-card/ai-consent.json\`. Record it
non-interactively with \`--accept-ai-terms\`.

**Personal-use positioning.** Per the panel: *AI image generation is
intended for personal use. We do not recommend AI imagery for cards you
intend to sell.* The README carries the full paragraph.

### What's new for the codebase

**Four new \`core/ai_*.py\` modules, each TDD'd.** \`ai_rails.py\` (occasion
gate + trademark / religious-iconography / likeness prompt blocklists →
\`RailViolation\` list), \`ai_provenance.py\` (\`LicenseRecord\` sidecar +
consent gate), \`ai_assets.py\` (POD-aware \`build_ai_request\` +
\`generate_ai_asset\` orchestration over an **injectable** \`ImageClient\`
Protocol), and \`ai_openai.py\` (the only module that imports \`openai\`,
lazily, behind the extra). The injected client is what lets the entire
feature be tested with no network and no API key.

**New \`[ai]\` optional dependency** (\`openai>=1.0\`). The project remains
fully functional without it; \`openai\` is never imported on any default
code path.

**46 new tests** (rails 23, provenance 7, assets 9, CLI 7); suite at
831 passing, ruff + mypy --strict clean.

### What this release deliberately does NOT ship

Per \`docs/industry-review/consensus-ai-feature.md\`, all out of scope:
render-time AI fill, AI-generated copy, whole-panel or photo
replacement, and free text-to-image as a default. AI is plumbing for
authoring, not a render-path dependency.

### Strategic items remaining

* **L2 illustrator commission** — ~30 hand-drawn SVG path motifs in one
  opinionated voice. Needs a contractor, not a PR. The last open
  leapfrog.

---

## v1.2.0 — "Template library complete + curation layer" — 2026-05-16

If v1.1.0 was the architecture, v1.2.0 fills the artifact. Every
shipped template compiles. Every leapfrog the industry panel
endorsed for v1 ships except L3 (AI imagery, deferred by the
panel itself). Prepress is production-grade — \`--export-for moo-a6\`
emits DeviceCMYK PDF/X-1a:2003 with embedded GRACoL2013 ICC,
ready to drop into MOO's ingester. The PNG backend now alpha-
blends correctly so the visual-regression gate can protect what
actually ships.

### What's new for users

**Templates — 8 → 17, all compile cleanly.** Six dormant Christmas
demos (festive-stripes, holiday-masterpiece, holly-wreath,
metallic-ornaments, photo-ornament, winter-sky) revive as the
compiler grows up; three new photo cards ship (christmas-family-
photo, mothers-day-photo, birthday-photo). Mother's Day and
Birthday occasions both double in template count.

**Voiced greetings — \`--voice\`.** Pick from \`warm\`, \`witty\`,
\`spare\`, \`devotional\`, \`irreverent\` and the CLI fills the cover
+ inside slots from a 250-line hand-tagged sentiment library.
\`--seed N\` makes the pick reproducible; \`--blank-inside\` skips
the inside-message override.

**Structured inside letter.** Four new flags compose a personal
note: \`--salutation "Dear M,"\`, \`--signoff "Love,"\`,
\`--signature "C"\`, \`--ps "PS hi"\`. Add \`--signature-font Caveat\`
for the handwritten override.

**Christmas-letter Markdown mode.** \`--inside-message-md letter.md\`
turns the inside panel into a "letter" surface: paragraphs, hard
line breaks, \`**bold**\` spans, proper paragraph spacing, bold-
aware font fallback.

**POD prepress — \`--export-for moo-a6\`.** DeviceCMYK PDF/X-1a:2003
output: each panel emitted at its A6 trim + 0.125" bleed, with
the GRACoL2013_CRPC6 ICC profile embedded as the OutputIntent,
XMP metadata declaring PDF/X-1a:2003 conformance,
\`/Info /Trapped /False\`, and the PDF header forced to 1.4. The
moo-a6 target produces files that pass MOO's preflight on first
upload.

**Curated typography.** Six SIL OFL families ship in
\`fonts/curated/\` — Cormorant Garamond (editorial serif),
Playfair Display (display serif), Lato (geometric sans, with
bold), Inter (modern variable sans), Caveat (handwritten script),
Comfortaa (rounded display). Every shipped template is migrated;
zero Helvetica/Times-Roman references remain in \`templates/\`.

**Photo cards.** \`ImageElement\` compiler support with circle,
rectangle, ellipse, and star clip masks. Backends compose the
image through the mask correctly — base64-embedded in SVG,
DrawImage in PDF, Pillow \`ImageChops\` mask in PNG.

**Gradient and pattern fills.** Linear gradients, radial gradients,
and patterns (stripes / dots / grid / checkerboard) lower into
per-backend paint resources. CMYK propagates through gradient
stops so \`--export-for moo-a6\` produces CMYK gradients.

**SVG path shapes.** \`SVGPath\` lowers to bezier-flattened
polylines (cubic + quadratic sampling at 16 samples/segment) in
the PNG backend; native path in SVG and PDF. Smooth-reflection
shortcuts (\`S\`, \`T\`) and \`H\`/\`V\` shortcuts work. Arc commands
(\`A\`/\`a\`) raise \`UnsupportedFeatureError\` — no shipped template
uses them.

**Bleed support.** \`Card.bleed\` / \`Panel.bleed\` configure the
bleed extension (default 0.125"); backgrounds extend past the
trim on edges touching the page boundary. PDFs declare distinct
\`/MediaBox\` / \`/TrimBox\` / \`/BleedBox\` / \`/ArtBox\`.

**Cards-as-code identity.** A new \`.github/workflows/render-cards.yml\`
detects affected templates on every PR (direct YAML touch →
that template; indirect src/fonts/sentiments/themes touch →
the full shipping set), renders PNG previews at 144 DPI,
uploads them as a workflow artifact, and posts a sticky PR
comment with the list. Reviewers see what the change does to
the actual cards.

**Template-gallery microsite.** \`scripts/build_microsite.py\`
generates one HTML page per template with a form that builds a
copy-paste-ready \`holiday-card create ...\` command, plus a
gallery index grouped by occasion. Deployed to GitHub Pages on
every push to main via \`.github/workflows/microsite.yml\`.

**\`--with-fold-marks\` gate.** Fold lines are now opt-in/opt-out
with per-target defaults (\`letter\` ON, \`per-panel\` OFF).

### What's new for the codebase

**711 tests** (was 555 at v1.1.0). Coverage spans all 17
templates across snapshot, integration, and visual suites.

**Visual-regression perceptual-hash gate** in \`tests/visual/\` —
\`imagehash.phash\` Hamming-distance comparison against committed
baseline PNGs (one per template, 72 DPI). Threshold 5. Tighter
than SSIM at this resolution; robust to anti-aliasing variation
across platforms. Regenerate with
\`python scripts/regenerate_visual_baselines.py\`.

**PNG backend true alpha-blending.** Shapes with \`opacity < 1.0\`
or sub-unit color alpha now render through a temp RGBA layer +
\`Image.alpha_composite\` onto the canvas instead of Pillow's
default \`ImageDraw\` pixel-replace behavior. Fixes a long-standing
issue where opacity < 1.0 silently rendered as fully opaque on
the (previously RGB) canvas — and protected by baselines that
captured the wrong rendering as the new "truth."

**IR snapshot tests over 12 templates** (was 7 at v1.1.0). Photo-
bearing templates are excluded because their compiled IR carries
machine-absolute image source paths; they have coverage via
PNG + SVG + visual suites instead.

**Compiler feature coverage.** \`compiler.py\` grew handlers for
\`ImageElement\` (\`_compile_image\`), gradient and pattern paints,
SVGPath bezier resolution, structured letter content,
RichTextContent (Markdown), and per-panel scaling for POD output.
All 14 IR command types still in the same discriminated union;
no new command types needed.

**Strict CI gates.** ruff + mypy + pytest matrix (Ubuntu + macOS
× py3.11/3.12/3.13) + smoke job + sdist/wheel build + render-cards
PR comment + microsite deploy. The smoke job now exercises every
\`--voice\` and validates the \`--export-for moo-a6\` PDF/X-1a header
on every push.

### Bug fixes worth calling out

* **photo-ornament rendered white silhouettes where photos should
  show.** Shipping bug: the template used
  \`fill_color: "#FFFFFF" + opacity: 0\` to mean "no fill, only
  stroke." But \`opacity\` multiplies both fill and stroke alpha,
  and the RGB canvas dropped the alpha channel anyway, so the
  white fill rendered solid on top of the clipped photo.
  Fixed first at the template level (PR #36 stripped the misuse
  pattern), then properly at the renderer (PR #41 made
  \`opacity: 0\` truly transparent via alpha-compositing).
* **\`christmas-holiday-masterpiece\` had the same hidden-photo bug.**
  Fixed automatically as a side effect of PR #41 — the template
  author's intent (transparent fill, visible stroke, photo
  showing through) now just works.
* **\`mothers-day\` inside-right message rendered off-page.** The
  template had \`y: 9.0\` for the message text — panel-relative
  coordinates on a 5.5" panel, so the compiled IR put the text
  at global y=14.5", off the 11" letter trim. Fixed by changing
  to \`y: 3.0\` matching the convention used by other templates.

### Known limitations

* SVG path arc commands (\`A\`/\`a\`) raise
  \`UnsupportedFeatureError\`. No shipped template uses arcs.
* Photo \`effects\` and \`frame_style\` not yet wired (deferred —
  the data model exists, no compiler path yet).
* Heart and SVGPath clip masks raise
  \`UnsupportedFeatureError\`. \`Circle\` / \`Rectangle\` / \`Ellipse\` /
  \`Star\` cover every shipped template.
* \`ImageElement\` requires explicit \`width\` / \`height\` — auto-
  sizing from the source image is not yet wired.
* AI-native authoring (panel Leapfrog 3) is **explicitly
  deferred** until the curation moat is wider. See
  \`docs/industry-review/consensus-ai-feature.md\`.

### Strategic items remaining

* **L2 illustrator commission** — ~30 hand-drawn SVG path motifs
  in one opinionated voice. Needs a contractor, not a PR.
* **L3 AI imagery** — deferred to Q1 2027 with hard rails on
  sympathy / bereavement / religious iconography / photo slots
  / recognizable likenesses.

---

## v1.1.0 — "Three backends on one IR" — 2026-05-10

The Wave 2 architecture refactor lands. The PDF-only renderer is
replaced by a backend-neutral pipeline: every template now compiles to
the same intermediate representation (IR), and three rendering backends
(PDF, SVG, PNG) consume that IR. Adding a fourth is a focused PR, not a
rewrite.

### What's new for users

- **`holiday-card create <id> --format svg`** — the same card design as
  a browser-openable SVG. Auto-detected from `-o card.svg`.
- **`holiday-card preview <id>`** — fast PNG render at 144 DPI that
  opens in your default image viewer. Useful for iterating on templates
  without round-tripping through a PDF reader.
- Configurable preview resolution (`--dpi`) and a `--no-open` flag for
  CI / scripting.
- Hidden `--debug-emit-ir` developer flag prints the compiled IR as
  JSON for debugging custom templates.
- All three output formats produce visually-equivalent output from the
  same source template.

### What's new for the codebase

- Three-layer architecture: **`Card` (Pydantic) → `compile_card()`
  (decisions) → `list[RenderCommand]` (the IR) → backend (visitor)**.
- The legacy 1063-LOC monolithic `ReportLabRenderer` plus its
  dependent modules (`shape_renderer`, `clipping_renderer`,
  `gradient_renderer`, `pattern_renderer`, `decorative.py`) are
  **deleted** — about 3,000 LOC removed. One renderer concern lives in
  one place now.
- 324 tests (was 253) including snapshot tests for the compiler output
  on 7 templates, parity-style structural tests for SVG and PNG, and
  pixel-correctness tests that catch backend bugs structural tests
  miss.
- All quality gates blocking on CI: ruff, mypy (strict mode, zero
  errors), the full test matrix on Ubuntu + macOS across Python
  3.11/3.12/3.13, smoke render + sdist/wheel build.

### Breaking changes (relative to the unreleased v2.0.0 Valentine work)

- Valentine occasion + 3 templates removed (`valentine-hearts`,
  `valentine-cupid`, `valentine-elegant`).
- `decorative_elements/` library removed; `core/decorative.py` removed.
- `--show-guides` and `--format jpg` flags on `preview` removed (PNG
  only; fold guides are always emitted as part of the IR).

### Known limitations

- The compiler currently supports a subset of features: backgrounds,
  borders, basic shapes (Rectangle/Circle/Triangle/Star/Line) with
  solid fills, text with three alignments, fold lines, and identity or
  rotation-only group transforms. Templates using gradients, patterns,
  clip masks, decorative elements, SVG paths, or image elements raise
  `UnsupportedFeatureError`.
- 7 of the 11 shipped Christmas templates compile cleanly. The other 4
  use unsupported features (or have an `id`-vs-filename mismatch in
  template discovery).
- Some Pydantic models in `models.py` (`HeartClipMask`,
  `DecorativeElement`, gradient/pattern fills, `SVGPath`) are kept for
  reference but not used by any backend.

### Numbers

- 13 PRs landed.
- ~6,950 LOC removed; ~3,800 LOC added (almost all in well-tested new
  modules).
- Mypy errors: 24+ → 0.
- Ruff errors: 56 → 0.
- Tests: 253 → 324.

---

# 🎀 Holiday Card Generator - Valentine's Day Edition Release Notes

> **Note (2026-05):** the features described below were removed in
> v1.1.0. The `valentine` occasion, decorative-element library, and
> `HeartClipMask` no longer ship. Kept here as historical context.

**Release Date:** February 14, 2026 (Valentine's Day!)
**Version:** 2.0.0 - "Love is in the Air" (never tagged; superseded by v1.1.0)

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
