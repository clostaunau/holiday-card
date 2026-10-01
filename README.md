# holiday-card

**Greeting cards as code.** A Python CLI that compiles YAML templates
into print-ready PDFs, browser-openable SVGs, and PNG previews — with
proper bleed, embedded fonts, distinct PDF box declarations, and
per-target POD output. One source of truth, version-controlled,
CI-rendered, reproducibly built.

```bash
pipx install holiday-card
holiday-card create christmas-classic --voice warm --seed 42
```

That picks a voiced greeting from the curated sentiment library,
renders it in Playfair Display + Cormorant, exports as a true 8.5×11
US Letter imposition (no bleed, so your print dialog never has to
"fit to page"), and saves a PDF you can drop on your home printer.
The `--export-for` POD targets carry the 0.125" bleed a press needs.

## Why this exists

Existing greeting-card tooling is a binary choice: either a SaaS
visual editor (Canva, Cricut, Hallmark Card Studio) where the design
lives in a vendor's database, or rolling your own PDF in a 200-line
Python script every December. Neither version-controls. Neither
diff-reviews. Neither reproduces.

This project is the third option:

* **Templates are YAML** — diff-reviewable, fork-able, schema-validated
* **Output is rendered** — PDF for print, SVG for the web, PNG for preview, all from the same compiler
* **Bleed and trim are first-class** — the output PDF declares
  distinct `/MediaBox`, `/TrimBox`, `/BleedBox`, `/ArtBox`; passes
  POD preflight on first upload
* **PDF/X-1a:2003 CMYK on demand** — `--export-for moo-a6` emits
  DeviceCMYK PDFs with embedded GRACoL2013 ICC profile, XMP metadata,
  and PDF/X-1a:2003 conformance; ready to drop into MOO's ingester
* **Curated typography ships with the project** — six SIL OFL fonts
  (Cormorant, Playfair, Lato, Inter, Caveat, Comfortaa), embedded in
  every PDF
* **Voiced greetings ship with the project** — 300+ hand-tagged
  sentiments across 5 voices and 9 occasions (5 celebratory +
  4 sympathy-class), picked via `--voice`

## Install

```bash
pipx install holiday-card        # the canonical install
# or, for development (installs the exact locked versions from uv.lock):
uv sync --extra dev
# plain pip still works, but resolves unpinned latest versions:
pip install -e ".[dev]"
```

## Six things you can do today

```bash
# 1. Pick a voice and let the sentiment library write your card
holiday-card create christmas-classic --voice irreverent --seed 7

# 2. Set your own message; pick the typeface via the template
holiday-card create christmas-classic -m "Merry Christmas, Sarah" \
  --inside-message "Hope this year is gentle to you both."

# 3. Export per-panel files for a POD service
holiday-card create christmas-classic --export-for moo-a6 -o ./moo/
# → ./moo/{front,back,inside-left,inside-right}.pdf at A6 trim + 0.125" bleed
#   Each panel is scaled to fill the A6 trim and the overflow is cropped; text
#   that crosses the 0.25" safe zone prints a `Warning:` (exit 0).
#   `--panel-fit letterbox` fits the whole panel instead (white bands top/bottom).

# 4. Skip the printer dialog — preview as PNG
holiday-card preview christmas-classic --voice spare

# 5. Render a card from a template you wrote yourself
holiday-card create ./my-template.yaml -o my-card.pdf

# 6. Christmas-letter mode: write the inside as Markdown
holiday-card create birthday-balloons --inside-message-md letter.md
# Where letter.md contains paragraphs with **bold**, *italic* and
# ***bold-italic*** spans and hard line breaks. Renders into the inside
# panel with proper paragraph spacing.
#   Or build the letter from parts: --salutation / --signoff / --signature / --ps
```

## What ships in the box

| Layer | What's in it |
|---|---|
| **Templates** | 21 ship-quality templates across Christmas (11, incl. 1 family photo), Birthday (2, incl. 1 photo), Hanukkah, Mother's Day (2, incl. 1 photo), Generic, and 4 sympathy-class (sympathy, condolence, miscarriage, pet loss) — all compile cleanly |
| **Voices** | warm, witty, spare, devotional, irreverent — pick via `--voice` |
| **Sentiments** | 303 hand-tagged copy lines across 9 occasions × up-to-5 voices × 2 roles. Sympathy-class occasions ship a curated voice subset ("absent rather than wrong" — witty + irreverent never appear for grief contexts) |
| **Fonts** | 6 curated SIL OFL families (Cormorant Garamond, Playfair Display, Lato, Inter, Caveat, Comfortaa) embedded in every PDF, and as glyph subsets in every SVG |
| **Photo cards** | `ImageElement` + circle / rectangle / ellipse / star clip masks; render a portrait into a styled frame |
| **POD targets** | `letter` (single imposed 8.5×11 sheet for home printing, no bleed), `per-panel-pdf` (native trim per panel + 0.125" bleed), `moo-a6` (A6 + 0.125" bleed, art scaled to fill the trim and cropped — `--panel-fit letterbox` to fit it whole — + DeviceCMYK PDF/X-1a:2003 + GRACoL2013 ICC) |
| **Output formats** | PDF (default), SVG (self-contained: fonts are embedded as glyph subsets, photos as data URIs, so it renders the same on any machine) from `create`; PNG from `preview` (`create --format png` is refused) |
| **Quality gates** | ruff + mypy strict + pytest (branch-coverage floor 92%) + a CI-run check that every `holiday-card` example in this README exits 0 + per-panel 144 DPI visual-regression gate (PNG and PDF rasters) across all 21 templates + a smoke job that installs the built wheel and runs it outside any checkout, covering each voice and the CMYK export |

### Where data lives / env overrides

Templates, themes, sentiments, fonts, and the GRACoL2013 ICC profile
ship **inside the package** under `src/holiday_card/data/` (installed as
`holiday_card/data/`), so a plain `pipx install holiday-card` works from
any directory. Two catalogs can be swapped out with an environment
variable, which **replaces** the bundled directory (it does not merge
with it):

| Variable | Replaces |
|---|---|
| `HOLIDAY_CARD_THEMES` | `holiday_card/data/themes/` |
| `HOLIDAY_CARD_SENTIMENTS` | `holiday_card/data/sentiments/` |

An override that isn't an existing directory is an error. Templates are
different: `HOLIDAY_CARD_TEMPLATES` **adds** directories in front of the
bundled ones (see [Your own templates](#your-own-templates)). If
`holiday-card templates` (no filter) finds no bundled template, or
`holiday-card themes` finds nothing, it exits 1 with `installation is
missing bundled data` rather than printing an empty list.

### Your own templates

```bash
holiday-card init my-card                    # writes ~/.local/share/holiday-card/templates/generic/my-card.yaml
holiday-card create my-card -o my-card.pdf   # found by id on the search path
holiday-card create ./my-template.yaml       # or pass any file path
holiday-card validate ./my-template.yaml
```

A template reference is either a **path** or an **id**. It is a path when
it ends in `.yaml`/`.yml`, contains a `/`, or starts with `.` or `~`; the
file is loaded directly and a missing file is `Template not found:
<path>` (exit 2). Anything else is an id, looked up (by `id:`, then by
file name) in these layers, earliest first:

1. each directory in `HOLIDAY_CARD_TEMPLATES`, split on `:` (`;` on
   Windows) like `PATH`;
2. the user dir `$XDG_DATA_HOME/holiday-card/templates` (default
   `~/.local/share/holiday-card/templates`);
3. the bundled templates.

Directories that don't exist are skipped. Templates can sit at any depth
in a layer; the occasion comes from the YAML's `occasion:` field, not the
folder. A template whose id matches one in a later layer shadows it:
`holiday-card templates --format json` lists it once, with `"source":
"user"` (or `"env"`) and `"shadows": "builtin"`.

`init` writes to the user dir by default (`--output DIR` to put it
elsewhere), refuses an `--occasion` that isn't a known occasion, refuses
to overwrite an existing file without `--force`, and prints the `create`
command to run next. Image paths in a template resolve against the
template file, so a template directory with its images is portable.

#### Authoring templates

[`docs/template-authoring.md`](docs/template-authoring.md) covers the
coordinate system, every shape and fill type with a YAML example, and the
font IDs. `holiday-card validate` is the pre-flight check: it lists every
problem at once (unknown keys, unknown fonts, elements outside their panel,
a missing default theme, anything the compiler refuses) and exits 2.
`holiday-card schema -o template-schema.json` writes the JSON Schema
([`docs/template-schema.json`](docs/template-schema.json)) for editor
completion via `# yaml-language-server: $schema=…`.

### Images in templates

A template's `image_elements[].source_path` is resolved **relative to
the template YAML file**, never the current directory. The rules:

- Relative paths only. An absolute path is a load error, and so is any
  `..` component or a symlink that points outside the template's
  directory. Put the image next to the YAML (or in a subdirectory).
- PNG or JPEG only, checked from the file's bytes rather than its
  extension; truncated files and images over 50 megapixels are refused.
- A bad path fails `holiday-card validate`; a bad image fails `create` /
  `preview` with `Error: …` and exit 2.

A panel's `background_image` follows the same rules. It is drawn cover-fit
under everything else on the panel, into the bleed, so baked art can sit
behind vector text (see the
[template authoring guide](docs/template-authoring.md#panel-background-image)).

### Your own photos: `-i/--image`

The photo templates (`christmas-photo-ornament`, `christmas-family-photo`,
`christmas-holiday-masterpiece`, `birthday-photo`, `mothers-day-photo`)
ship a grey placeholder in each photo slot. `-i` swaps in your photo:

```bash
holiday-card create christmas-family-photo -i ~/me.jpg -o card.pdf
# christmas-photo-ornament has 5 slots: cover, star, three circles.
holiday-card create christmas-photo-ornament -i cover.jpg -i star.jpg -o card.pdf
```

The first `-i` fills slot `photo` (the cover), the second fills
`photo-2`, and so on. Slots you don't fill keep the placeholder. Your
photo takes the slot's position, size, clip shape and layering, and it
is fitted inside the slot without cropping. More `-i` values than the
template has slots, or any `-i` on a template with no slots, is an error
(exit 2) rather than being dropped.

`--image` may point anywhere on disk. It goes through the same content
check (a PNG or JPEG, whatever the extension says).

Template authors mark a replaceable image with `slot:`. Several
elements may share a slot, and they all show the same photo:

```yaml
image_elements:
  - source_path: "placeholder-photo.jpg"
    slot: "photo"          # photo, photo-2 … photo-9
    x: 0.65
    y: 1.75
    width: 2.95
    height: 2.95
```

The shipped `placeholder-photo.jpg` (1200×1200 px, CC0) is generated by
`scripts/make_placeholder_photo.py`.

#### Print quality: 300 PPI recommended, 150 PPI minimum

PDF output checks every photo's effective resolution at the size it is
placed on the finished card (including the moo-a6 fill scale). Below
**300 PPI** you get a warning on stderr; below **150 PPI** `create`
refuses with exit 2 and writes nothing:

```text
Warning: me.jpg is 237 PPI at its placed size (300 recommended; need ≥ 885×885 px)
```

`--allow-low-res` turns the refusal into a warning. Use it for proofs
only: the print will be soft. SVG output and `preview` are screen
formats and are not checked.

### When something goes wrong

Bad or contradictory input fails with exit 2 and an `Error: …` line.
Nothing is written. For example: an unknown `--theme`, a `--voice` the
occasion doesn't ship (sympathy cards have no `witty`), `--seed` without
`--voice`, `--signature-font` without `--signature`, `--blank-inside`
together with an inside message, a `--fold-type` that doesn't match the
template's panels, an `-o` extension other than `.pdf`/`.svg`, a file
`-o` for a per-panel `--export-for` target, a template font that isn't
bundled, or a photo below 150 PPI in PDF output (see "Print quality"
above).

An unexpected error exits 1 and prints one line. Re-run with `--debug`
(or set `HOLIDAY_CARD_DEBUG=1`) to get the full traceback:

```bash
holiday-card --debug create christmas-classic -o card.pdf
```

### Exit codes

Scripts can branch on these; `holiday-card --help` lists them too.

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected internal error (re-run with `--debug` for a traceback) |
| 2 | Usage: bad or conflicting flags, unknown template / theme / file, invalid template |
| 3 | `ai-asset`: first-use consent missing (`--accept-ai-terms`) |
| 4 | Environment: missing optional extra or API key, or output path not writable |
| 5 | `ai-asset`: refused by the hard category rails |
| 6 | `ai-asset`: the AI provider refused the request (content policy) |
| 7 | `ai-asset`: provider or network error, timeout or invalid response (retryable) |

`-o` always means `--output`. `templates` and `themes` take `--occasion`
with no short flag, and their first column is the ID that `create`,
`preview`, `validate` and `--theme` accept.

## Hacking on it

```bash
git clone https://github.com/clostaunau/holiday-card.git
cd holiday-card
uv sync --extra dev            # locked deps from uv.lock (or: pip install -e ".[dev]")

uv run pytest                            # full suite, a few minutes
uv run ruff check src/ tests/ scripts/   # lint (zero warnings)
uv run mypy src/                         # strict-mode type-check (zero errors)

uv run holiday-card create christmas-classic --voice warm
```

CI installs from the committed `uv.lock` (`uv sync --locked`), so every
run tests the same dependency versions. After editing dependencies in
`pyproject.toml`, run `uv lock` and commit the updated lockfile — CI's
`uv lock --check` fails otherwise. A weekly `latest-deps` workflow
ignores the lock and tests the newest release of everything, so
upstream breakage shows up there rather than in feature PRs.

CI runs all three gates on every push across Python 3.11/3.12/3.13 ×
Ubuntu/macOS, plus a smoke job that renders one template per occasion.
All gates are blocking.

A second workflow (`.github/workflows/render-cards.yml`) renders PNG
previews of templates affected by every PR and posts them as a sticky
PR comment. Reviewers see what the change does to the actual cards
before merging — the "cards-as-code" identity move from Leapfrog 4
of the panel review.

## AI imagery (optional, personal use)

> **AI image generation is intended for personal use. We do not
> recommend AI imagery for cards you intend to sell. AI-generated assets
> may inadvertently contain protected material. You are responsible for
> what you print and sell.**

AI imagery is an **authoring-time** step that bakes one image to disk —
it never runs inside the render pipeline, so your cards stay
reproducible (commit the PNG + its `.license.yaml` sidecar to git).
Install the extra and set a key:

```bash
pip install holiday-card[ai]
export OPENAI_API_KEY=sk-...

holiday-card ai-asset generate \
  --subject "watercolor pine bough border, sage green and burgundy" \
  --reference path/to/reference.png \
  --style watercolor \
  --occasion christmas \
  --export-for moo-a6 \
  --output assets/ai/pine-bough-border.png

holiday-card ai-asset models   # the curated image models this version supports (no network)
```

A baked image can go in a template's `image_elements`, or be a panel's
`background_image`: cover-fit art under vector text, which stays vector.

### OpenRouter (optional second provider)

[OpenRouter](https://openrouter.ai) reaches a curated list of image
models from other vendors. It needs no install extra, only a key:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...

holiday-card ai-asset generate --provider openrouter \
  --model google/gemini-3-pro-image \
  --subject "watercolor pine bough border, sage green and burgundy" \
  --reference path/to/reference.png \
  --occasion christmas --export-for moo-a6 \
  --output assets/ai/pine-bough-border.png
```

Set `HOLIDAY_CARD_AI_PROVIDER=openrouter` to make it your default
(`openai` stays the default otherwise). What is different:

* **The upstream provider is pinned; there are no fallbacks.** Each
  model goes to exactly one vendor endpoint (e.g. Google AI Studio), and
  only reviewed models are allowed (an unknown `--model` exits 2 and
  lists them).
* **Sizing is an aspect ratio + resolution tier**, then cropped and
  resampled to trim+bleed at 300 PPI. Many models come in below 300 PPI
  at A6; the CLI warns and the sidecar records `native_ppi`.
* **Retention and training are an OpenRouter *account* setting.** The
  image endpoint has no per-request opt-out: review
  <https://openrouter.ai/workspaces/default/settings> before you send a
  private reference image.
* **Output ownership follows the upstream vendor's terms**, not
  OpenRouter's; the vendor's terms URL is recorded in each sidecar.
* **Reference images are not screened** for trademarks or likenesses;
  only the prompt goes through the rails. You are responsible for what
  you upload.
* `--seed` works only for models that take one (e.g.
  `black-forest-labs/flux.2-pro`).
* **Cost cap** — `--max-cost USD` (opt-in) estimates an *upper bound*
  for the call **offline**, from the curated price list and its cited
  vendor bounds, and refuses with exit 2 before any call when the
  estimate is above the cap (equal passes). If the provider then reports
  a higher charge, the CLI warns (the money is already spent) and keeps
  the asset. There is no prompt and no default cap. A model with no
  recorded price or bound (every OpenAI model today, and
  `openai/gpt-image-2` via OpenRouter) exits 2 with `--max-cost`. The
  default model on `moo-a6` with a reference bounds at $0.1355:

  ```bash
  holiday-card ai-asset generate --provider openrouter --max-cost 0.15 \
    --subject "watercolor pine bough border, sage green and burgundy" \
    --reference path/to/reference.png --occasion christmas -o assets/ai/border.png
  ```

The model list and the API behaviour it relies on are recorded in
[`docs/industry-review/openrouter-image-api-snapshot.md`](docs/industry-review/openrouter-image-api-snapshot.md).

Guardrails that ship on by default (see
`docs/industry-review/consensus-ai-feature.md`):

* **First-use consent** — a one-time acknowledgement **per provider**,
  recorded under your config dir; pass `--accept-ai-terms` to record it
  non-interactively. A consent recorded by v1.3.0 still counts for
  OpenAI.
* **Image-reference mode default** — `--reference` is required (the
  style anchor); `--unsafe-no-style-anchor` opts out (discouraged).
* **POD-aware sizing** — the baked PNG is exactly the `--export-for`
  target's trim + 2×bleed at 300 PPI (1314×1824 px for `moo-a6`), tagged
  sRGB IEC61966-2.1 with `dpi=300`. The request is what each provider
  accepts: OpenAI is asked for pixels (`gpt-image-2` by default: the
  target rounded up to 16-px multiples; legacy fixed-size models get
  their closest aspect); OpenRouter is asked for the nearest aspect
  ratio and the smallest resolution tier that covers the target (`3:4`
  at `2K` for `moo-a6`). Either way the result is centre-cropped and
  resampled to the target. If the model's output is below 300 PPI at
  print size the CLI warns and the sidecar records `native_ppi`.
* **Provider and model** — `--provider openai|openrouter` (default
  `openai`, or `$HOLIDAY_CARD_AI_PROVIDER`; never inferred from the
  model id) and `--model` (default `gpt-image-2` for OpenAI,
  `google/gemini-3-pro-image` for OpenRouter) pick what is called; an
  unknown model exits 2 and lists the known ones. `--seed` is refused
  (exit 2) for models that take no seed, which includes every OpenAI
  model.
* **Hard category rails** — sympathy / condolence / miscarriage /
  pet_loss occasions, religious iconography, trademarked brands, and
  recognizable-likeness / photo-replacement prompts **refuse by
  default**. Override with `--i-know-what-im-doing` (it prints every
  reason first).
* **Provenance sidecar** — every asset gets a sibling
  `<asset>.license.yaml` recording the prompt, model, seed, timestamp,
  the cost the provider reported (or `unknown` when it reports none;
  the reported cost is never estimated; with `--max-cost` the sidecar
  also records `cost_cap_usd` and the `cost_estimate_usd` it was checked
  against), and the provider's and upstream vendor's
  policy URLs in force at generation time. It also names the `provider`, the `requested_model`
  next to the `model` actually called, the `request_shape` sent, the
  `media_type` the model returned, and, for a routing provider, the
  provider route and `generation_id`. The PNG itself is marked as AI-generated, and a
  card that places it refuses to render (exit 2) once the sidecar is
  missing or belongs to another file.
* **Never a photo** — `create` / `preview -i` refuse any AI asset (exit 2,
  rail 8: no photo replacement), even one that only has a sidecar; place
  it as a template image element instead.
* **Untrusted output, checked inputs** — the model's image is decoded
  only as PNG, JPEG or WebP (one frame, at most 50 MP), or refused with
  exit 7 and nothing written; `--reference` must be a readable PNG or
  JPEG, checked before anything is uploaded.
* **Disclosed in every file** — a card that embeds AI imagery says so in
  its metadata, naming the model from the asset's sidecar: the PDF
  `/Subject` (`Contains AI-generated imagery (gpt-image-2)`; an
  OpenRouter model reads `<model> via openrouter`) and XMP
  (`dc:description`, `hc:aiModels`, the IPTC `DigitalSourceType`), the
  SVG `<desc>` and RDF `<metadata>`, and the PNG preview's
  `Description`. In `--export-for` per-panel output only the panels that
  embed AI imagery are marked. The artwork itself is unchanged.

## What this is not

* **Not a Canva replacement.** If you want a visual editor with 600
  fonts and a drag-and-drop photo crop, use Canva. Canva is good at
  what it does. This project is for people who want to commit
  a `family-2026.yaml` template, push to GitHub, and have CI
  render the same card every time.
* **Not a Canva-style preview tool.** Output is print artifacts (PDF /
  SVG / PNG previews), not an interactive editor. The browser-openable
  SVG and the `preview` command's PNG are the inspection surfaces.
* **Not finished.** The architecture is solid; the artifact catches
  up template by template, voice by voice, font by font.

## Roadmap

The project's direction is informed by an industry-panel review (six
critics across design, copy, prepress, retail merchandising, POD, and
DIY craft). Read `docs/industry-review/` for the consensus and per-
critic breakdowns. Recent work targets the panel's "1-month" and
"1-quarter" recommendations:

* ✅ Bleed support + `Sheet/Trim/Bleed/Safe` abstraction (Agreement 2)
* ✅ `--export-for` per-panel POD output (Leapfrog 1, slice 1)
* ✅ Sentiment library + `--voice` (Leapfrog 2, slice 1)
* ✅ Curated fonts shipped + every template migrated (Leapfrog 2, slices 2 + 3)
* ✅ `--with-fold-marks` gate, README persona rewrite, etc. (panel cleanups)
* ✅ Markdown mode for inside panel (`--inside-message-md`) (Leapfrog 4, slice 1)
* ✅ GitHub Action: render-on-PR with sticky comment (Leapfrog 4, slice 2)
* ✅ CMYK + GRACoL2013 ICC + PDF/X-1a:2003 for `--export-for moo-a6` (Leapfrog 1 complete)
* ✅ Structured inside letter: `--salutation` / `--signoff` / `--signature` / `--ps` (Leapfrog 2, slice 4)
* ✅ Photo cards: ImageElement compiler support + clip masks (Circle / Rectangle / Ellipse / Star) — unblocks photo-ornament
* ✅ Gradient + pattern fills (linear / radial / stripes / dots / grid / checkerboard) — unblocks 3 more christmas templates
* ✅ SVG path support — unblocks holly-wreath + holiday-masterpiece
* ✅ Template-gallery microsite (Leapfrog 5) — static page per template with a copy-paste CLI command builder; deployed to GitHub Pages
* ✅ 3 new photo-card templates — `christmas-family-photo` (rectangle clip + Inter/Lato), `mothers-day-photo` (ellipse clip + Playfair/Caveat cameo), `birthday-photo` (circle clip + Comfortaa/Caveat). **All shipped templates compile cleanly.**
* ✅ Visual-regression perceptual-hash gate across every shipped template (auto-discovered, so new templates need a baseline before merge)
* ✅ PNG backend true alpha-blending — semi-transparent shapes now compose over panel backgrounds correctly (was an RGB-canvas alpha-drop bug)
* ✅ Sympathy-class occasion taxonomy: 4 new occasions (sympathy / condolence / miscarriage / pet_loss), 4 restrained templates, 20 hand-curated sentiment files with explicit voice gating (witty + irreverent never ship for grief contexts; devotional limited to adult-loss). Completes the panel's L2 prerequisite for the L3 hard-rails (consensus-ai-feature.md:109)
* ✅ Microsite Celebrations / Sympathy category split — sympathy cards no longer interleaved with cake-and-balloons cards
* ⏳ Illustrator commission: ~30 hand-drawn SVG path assets (Leapfrog 2 final slice — needs a human)
* ✅ Italic Markdown — `*x*` / `_x_` / `***bold-italic***` parse and thread through the compiler to italic font_ids. Helvetica/Times/Courier render real italic via Liberation; Cormorant and Playfair render real italic via bundled italic TTFs (Inter/Caveat/Comfortaa still fall back to regular)
* ✅ Bold Markdown for curated editorial serifs — `**bold**` and `***bold-italic***` on `Cormorant` / `PlayfairDisplay` resolve to bundled static Bold + BoldItalic TTFs (instanced from the variable masters at weight=700). Closes the bold-fallback documented limitation for the two editorial-serif families
* ⏳ Multi-panel spill for long Markdown letters
* ⏳ Father's Day templates (calendar-driven SKU expansion)
* ✅ AI imagery (Leapfrog 3) — authoring-time `ai-asset generate` subcommand that bakes one image to disk with a provenance sidecar (never runs at render time). Image-reference-mode default, POD-aware sizing (exact trim+bleed at 300 PPI, model-supported request sizes), sRGB-tagged, first-use consent, trademark blocklist, and hard category rails (sympathy / religious iconography / likeness / photo replacement refuse by default). Opt-in via `pip install holiday-card[ai]` + `OPENAI_API_KEY`, or via OpenRouter as a second provider (`--provider openrouter` + `OPENROUTER_API_KEY`, no extra; pinned upstream vendor, no fallbacks). See "AI imagery" below
* ❌ Render-time AI fill, AI-generated copy, panel/photo replacement — deliberately out of scope per the AI-feature consensus doc

## Architecture

`Card → compile_card → list[RenderCommand] → Renderer → file`. Three
backends share the same compiler: `IRReportLabRenderer` (PDF, default),
`SVGRenderer`, `PNGRenderer`. Adding a fourth backend is the same
~330-LOC pattern. See [CLAUDE.md](CLAUDE.md) for the architectural
walkthrough.

## License

MIT (see [LICENSE](LICENSE)). Bundled fonts in
`src/holiday_card/data/fonts/curated/` are SIL OFL 1.1 — the license for
each family ships next to its TTFs (`*-LICENSE.txt`); the Liberation
fonts' `LICENSE` and `AUTHORS` ship in `data/fonts/`. The GRACoL2013 ICC
profile's redistribution terms are in `data/icc/NOTICE`.
