# Template authoring guide

A template is one YAML file. This guide covers the coordinate system, every
element, shape and fill type, the fonts you can name, and the
`validate` → `create` loop. The machine-readable contract is
[`template-schema.json`](template-schema.json), generated from the Pydantic
models (`holiday-card schema`); when this guide and the schema disagree, the
schema wins.

## The loop

```bash
holiday-card init my-card                        # scaffold ~/.local/share/holiday-card/templates/generic/my-card.yaml
$EDITOR ~/.local/share/holiday-card/templates/generic/my-card.yaml
holiday-card validate my-card                    # every problem at once, exit 2 if any
holiday-card preview my-card                     # look at it
holiday-card create my-card -o my-card.pdf       # print it
```

`validate` takes an id or a path (`./my-card.yaml`) and runs every check
before you render:

1. **Schema.** Unknown keys, wrong types and out-of-range values
   (`Extra inputs are not permitted` for a typo like `colr:`).
2. **Fonts.** Every `font_family` must be one of the [font IDs](#fonts).
3. **Bounds.** Each text anchor, shape bounding box and image rectangle
   must lie inside `[0, width] × [0, height]` of its panel. Shapes are
   checked unrotated, except SVG paths, which are checked as compiled
   (rotation included).
4. **Theme.** `default_theme_id`, when set, must name a theme from
   `holiday-card themes`.
5. **Compile.** The card is compiled once, so anything the renderer
   refuses (an SVG arc, an auto-sized image, a missing or non-image file)
   shows up here instead of at `create`.

```text
$ holiday-card validate bad.yaml
Template invalid: bad.yaml
  - panels[front].text_elements[greeting].font_family: unknown font 'NotAFont'. Available: Caveat, …
  - panels[front].text_elements[greeting]: text anchor (99, 2.75) in is outside the 4.25×5.5 in panel
```

Paths name panels by `position` and elements by their `id` when you wrote
one (by index otherwise). A file with schema errors reports those alone,
located by index (`panels[0].text_elements[0].colr`), because the other
checks need a loaded template. Fix those first, then run `validate` again.

## Editor support

Point the YAML language server (VS Code "YAML", Neovim `yamlls`, JetBrains)
at the schema for completion, hover docs and inline errors. Put this as the
first line of the template:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/clostaunau/holiday-card/main/docs/template-schema.json
```

To match your installed version exactly, write the schema locally and
point at that instead:

```bash
holiday-card schema -o ~/.local/share/holiday-card/template-schema.json
```

The schema is JSON Schema draft 2020-12, generated from the models (never
hand-written) and checked against the committed copy in CI. It lists the
loader's alias spellings too (`x1` for `start_x`, `angle` for `rotation`).

## Template skeleton

```yaml
id: my-card                 # what `create my-card` looks up
name: "My Card"             # 1–50 characters
occasion: generic           # christmas, hanukkah, birthday, generic, new_year, thanksgiving, valentine,
                            #   mothers_day, sympathy, condolence, miscarriage, pet_loss
fold_type: quarter_fold     # half_fold is a legacy alias of quarter_fold
default_theme_id: generic-neutral   # optional; must exist
description: "Optional one-liner"
panels:
  - id: front
    position: front         # front, back, inside_left, inside_right
    width: 4.25
    height: 5.5
    background_color: {r: 0.8, g: 0.1, b: 0.1}   # 0.0–1.0 per channel
    border: {style: solid, width: 2, color: {r: 1, g: 1, b: 1}}   # optional
    text_elements: []
    shape_elements: []
    image_elements: []
```

A quarter-fold template has exactly the four positions `front`, `back`,
`inside_left` and `inside_right`, each 4.25 × 5.5 in. `tri_fold` templates
don't render yet.

## Coordinates, imposition and z-order

- **Units are inches, relative to the panel.** `(0, 0)` is the panel's
  **bottom-left** corner and **y grows upward** (the PDF convention). On a
  4.25 × 5.5 in panel the top-right corner is `(4.25, 5.5)`.
- **Panels don't have coordinates.** Where each panel lands on the sheet,
  and whether it is printed upside down so it reads correctly after
  folding, is computed from `fold_type` (see
  [#58](https://github.com/clostaunau/holiday-card/issues/58) and
  `core/imposition.py`). Leave out panel `x` / `y` / `rotation`; a value
  that disagrees with the computed slot is a load error.
- **z_index** orders everything drawn on a panel: shapes default to `0`,
  text and images to `100`, and higher draws on top. Ties keep file order,
  with shapes first, then images, then text.
- **Bleed.** On the POD targets a background that touches the trim
  extends 0.125 in past it. Keep text 0.25 in inside the trim (the safe
  zone); `create --export-for moo-a6` warns when it isn't.

## Text

```yaml
text_elements:
  - id: greeting
    content: "Merry Christmas!"      # "\n" for hard line breaks
    x: 2.125                         # anchor; see alignment
    y: 2.75                          # baseline of the first line; later lines go down
    width: 3.75                      # wrap / shrink width (optional)
    font_family: PlayfairDisplay     # a font ID, see below
    font_size: 36                    # 6–144 pt
    font_style: normal               # normal, bold, italic, bold_italic
    color: {r: 1, g: 1, b: 1}        # optional; theme text colour otherwise
    alignment: center                # left (x is the left edge), center (x is the middle), right
    rotation: 0                      # degrees about the anchor
    overflow_strategy: shrink        # auto, shrink, wrap, truncate
    min_font_size: 12
    max_lines: 3                     # optional
    z_index: 100
```

`--message` fills the front element with id `greeting` (or the first front
text), and `--inside-message`, `--voice`, `--inside-message-md` and the
letter flags fill the inside element with id `message`.

## Fonts

`font_family` must be one of these IDs. `font_file` is not supported yet.

| Curated (SIL OFL, bundled) | Use it for |
|---|---|
| `PlayfairDisplay`, `PlayfairDisplay-Bold`, `PlayfairDisplay-Italic`, `PlayfairDisplay-BoldItalic` | display serif, cover greetings |
| `Cormorant`, `Cormorant-Bold`, `Cormorant-Italic`, `Cormorant-BoldItalic` | editorial serif, inside body |
| `Lato`, `Lato-Bold` | friendly sans |
| `Inter` | modern sans |
| `Caveat` | handwritten script |
| `Comfortaa` | rounded display |

The PDF base-14 names also work and render with the bundled Liberation
fonts: `Helvetica`, `Helvetica-Bold`, `Helvetica-Oblique`,
`Helvetica-BoldOblique`, `Times-Roman`, `Times-Bold`, `Times-Italic`,
`Times-BoldItalic`, `Courier`, `Courier-Bold`, `Courier-Oblique`,
`Courier-BoldOblique`.

Prefer `font_style` to a variant ID: `font_family: Cormorant` with
`font_style: italic` renders `Cormorant-Italic`. Inter, Caveat and
Comfortaa have no bold or italic, so those styles render regular.

## Shapes

Every shape takes `id`, `z_index`, `opacity` (0–1), `rotation` (degrees,
0 to under 360), `stroke_color`, `stroke_width` (points), and either
`fill_color: "#RRGGBB"` or a [`fill`](#fills).

```yaml
shape_elements:
  - type: rectangle          # bottom-left corner + size
    x: 0.25
    y: 0.25
    width: 3.75
    height: 5.0
    stroke_color: "#D4AF37"
    stroke_width: 2

  - type: circle
    center_x: 2.125
    center_y: 3.5
    radius: 0.75
    fill_color: "#C41E3A"

  - type: triangle           # three vertices
    x1: 1.0
    y1: 1.0
    x2: 3.25
    y2: 1.0
    x3: 2.125
    y3: 3.0
    fill_color: "#2E7D32"

  - type: star               # outer_radius is what the bounds check uses
    center_x: 2.125
    center_y: 4.8
    outer_radius: 0.3
    inner_radius: 0.12
    points: 5                # 3–20
    fill_color: "#FFD700"

  - type: line               # start_x/start_y/end_x/end_y, or the aliases x1/y1/x2/y2
    x1: 0.5
    y1: 0.5
    x2: 3.75
    y2: 0.5
    stroke_color: "#000000"
    stroke_width: 1

  - type: svg_path           # path units × scale = inches, origin at (x, y), y up
    path_data: "M 0 0 C 30 60 70 60 100 0 Z"
    scale: 0.02
    x: 1.125
    y: 2.0
    fill_color: "#2E7D32"
```

SVG paths support `M L H V C S Q T Z` (absolute and relative). Arcs (`A`)
are refused at compile time, so `validate` reports them.

## Fills

`fill` replaces `fill_color` and takes one of four `type`s.

```yaml
fill:
  type: solid
  color: "#C41E3A"
```

```yaml
fill:
  type: linear_gradient
  angle: 90                  # degrees, 0 = left→right, 90 = bottom→top
  stops:                     # 2–20 stops, positions 0–1
    - {position: 0.0, color: "#0B1D3A"}
    - {position: 1.0, color: "#3A6EA5"}
```

```yaml
fill:
  type: radial_gradient
  center_x: 2.125            # panel-relative inches
  center_y: 3.5
  radius: 0.8                # inches
  stops:
    - {position: 0.0, color: "#FFF4C2"}
    - {position: 1.0, color: "#D4AF37"}
```

```yaml
fill:
  type: pattern
  pattern_type: stripes      # stripes, dots, grid, checkerboard
  colors: ["#C41E3A", "#FFFFFF"]   # 1–4
  spacing: 0.25              # inches
  scale: 1.0
  rotation: 45               # alias: angle
```

A pattern is `colors[0]` as the background with `colors[1]` drawn on it
(any further colours are unused; a single colour fills solid). One
period is `spacing × scale`: stripes are bands half a period tall, dots
have a quarter-period radius, grid draws one 1 pt line each way per
period, and checkerboard squares are half a period. Tiles start at the
shape's top-left corner, and `rotation` turns the pattern
counter-clockwise about the shape's centre. A period under 2 pt
(`spacing × scale` < ~0.028") or a pattern that would need more than
20 000 tiles is refused. The compiler turns every pattern into a clip
plus plain shapes, so PDF, SVG and PNG all draw it the same way.

**Translucency on print targets.** `opacity` or colour alpha below 1 is
flattened for `--export-for moo-a6` only when the element sits entirely
over an opaque solid rectangle, circle or ellipse, or over bare paper.
Over anything else (a gradient, a pattern, a photo, a partial overlap) the
PDF/X export refuses it. Pre-blend the colour against its backdrop
instead.

## Images

```yaml
image_elements:
  - id: portrait
    source_path: placeholder-photo.jpg   # relative to this YAML file
    slot: photo                          # filled by `create -i`; photo, photo-2 … photo-9
    x: 0.65
    y: 1.6
    width: 2.95                          # width and height are required
    height: 2.95
    preserve_aspect: true
    fit: cover                           # cover (fill + crop) or contain; see below
    rotation: 0
    clip_mask:                           # optional; coordinates relative to the image
      type: circle                       # circle, rectangle, ellipse, star
      center_x: 1.475
      center_y: 1.475
      radius: 1.475
    z_index: 100
```

`source_path` must be a relative PNG or JPEG next to the template (no
absolute paths, no `..`). For print, give photos at least 300 PPI at their
placed size: a 2.95 in slot wants 885 px. `effects` and `frame_style` are
not supported yet and are refused at compile time.

`fit` picks how an aspect-preserving image meets its `width` × `height`
rect. `cover` scales it to fill the rect and crops the overflow (centred),
so a clip mask as large as the rect is always filled; `contain` fits the
whole image inside and can leave margins. Unset, a `slot` element is
`cover` (a user's photo rarely matches the slot's shape) and any other
image is `contain`. `fit` with `preserve_aspect: false` is a load error:
that stretches the image to the rect. PPI under `cover` is measured at the
covering size, so a square photo in a 2.6 × 3.4 in slot needs 1020 px.

### Panel background image

```yaml
background_color: {r: 0.97, g: 0.95, b: 0.91}   # optional; drawn first, under the art
background_image: art/front-bg.png             # relative to this YAML file
```

A panel's `background_image` is a PNG or JPEG drawn as the panel's
background layer: baked art under vector text and shapes, which stay
vector. The rules:

- **Cover, always.** The image fills the panel's background rect and the
  overflow is cropped, centred. There is no `fit` option.
- **Bleed.** It covers exactly the rect `background_color` covers, so it
  extends into the bleed wherever the background does (0.125 in on the POD
  targets, nothing on `letter`).
- **Under everything.** It is drawn over `background_color` and under the
  border and every element, whatever their `z_index`; nothing can go under
  it. It rotates with its panel, so on the letter sheet the inside panels'
  art is upside down, like their text.
- **Paths.** Same as `source_path`: relative to the template, no absolute
  paths, no `..`, no symlinks out of the template directory, and the file
  must really be a PNG or JPEG.
- **Resolution.** PPI is measured at the covering size. An asset baked by
  `ai-asset generate --export-for moo-a6` (1314 × 1824 px) prints at
  309 PPI on `letter`, but at 276 PPI on `moo-a6`, which scales the panel
  by 1.06 to fill the A6 trim; that warns. For 300 PPI on `moo-a6` give
  at least 1427 × 1824 px: `ai-asset generate --export-for moo-a6
  --for-panel-background` bakes exactly that (the panel as the target
  places it, fit scale and bleed included; `--panel-size WxH` for a panel
  other than 4.25 × 5.5 in), and it prints at 300 PPI or more on `letter`
  too. Below 150 PPI, `create` refuses.
- **PDF/X.** On `moo-a6` an image is not a solid backdrop, so a translucent
  element (opacity below 1) over the art is refused. Use opaque colours
  there; on `letter`, SVG and PNG, transparency over the art is fine. An
  image with an alpha channel is flattened against `background_color`, or
  against paper white when there is none.
- **AI art.** An `ai-asset generate` bake needs its `.license.yaml`
  sidecar next to it, or the card is refused; with it, the card's metadata
  discloses the model. A background is not a photo slot, so `create -i`
  never replaces it.

Use it as a background, never as the whole panel: keep the words and the
design in vector elements on top, and don't ship a panel whose only
content is the image.

## See also

- [`template-schema.json`](template-schema.json): every field, type, default
  and range.
- `holiday-card templates`: the 21 shipped templates, whose YAML lives in
  `src/holiday_card/data/templates/` and makes good starting points.
- README, "Your own templates": the template search path and `init`.
