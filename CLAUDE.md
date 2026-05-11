# holiday-card — Development Guidelines

Last updated: 2026-05-10. Wave 2 architecture refactor is **complete**;
Leapfrog 1 (POD prepress) is **complete**; the codebase is at v1.1.0
with all CI quality gates blocking.

## TL;DR for a fresh session

This is a Python 3.11+ CLI that produces print-ready greeting cards in
**three output formats** (PDF, SVG, PNG) from YAML templates. The core
architecture is a backend-neutral `RenderCommand` IR:

```
YAML template → Card (Pydantic) → compile_card() → list[RenderCommand] → Renderer → file
```

Three renderers consume the same IR: `IRReportLabRenderer` (PDF, default),
`SVGRenderer`, `PNGRenderer`. Adding a fourth backend is the same pattern.

```bash
pipx install holiday-card           # canonical user install (or `pip install -e ".[dev]"` for hacking)
holiday-card create christmas-classic -m "Merry Christmas!"     # writes a PDF
holiday-card create christmas-classic --format svg              # writes an SVG
holiday-card create christmas-classic --voice warm --seed 42    # picked-sentiment cover + inside
holiday-card create christmas-classic --inside-message-md letter.md   # Markdown letter mode
holiday-card create christmas-classic --salutation "Dear M," --signoff "Love," --signature "C" --ps "PS hi"   # structured letter
holiday-card create christmas-classic --export-for moo-a6 -o out/     # CMYK PDF/X-1a:2003 for MOO
holiday-card preview christmas-classic                          # writes a PNG and opens it
pytest                              # all 601 tests, mypy-clean, ruff-clean
```

## Architecture

The Wave 2 refactor (PRs #4-#10) replaced a 1063-LOC monolithic
`ReportLabRenderer` with a three-layer pipeline:

1. **Domain layer** — `core/models.py`. Pydantic models for `Card`,
   `Template`, `Panel`, shapes, text, image, etc. Knows nothing about
   points, ReportLab, or rendering order.
2. **Compiler layer** — `core/compiler.py`. Pure function
   `compile_card(card) -> list[RenderCommand]`. Owns z-sort, decorative
   expansion, text-overflow strategy, font resolution, the single
   inches→points conversion. The decision layer.
3. **Backend layer** — `renderers/{reportlab,svg,png}_backend.py`. Each
   implements `render(commands, output_path)` — a visitor over the
   discriminated union of 11 commands. No semantic decisions; every
   command has one obvious translation.

The IR (`core/render_ir.py`) is the seam. 11 frozen Pydantic command
types: `BeginPage`, `EndPage`, `SetMetadata`, `BeginGroup`, `EndGroup`,
`BeginClip`, `EndClip`, `DrawShape`, `DrawText`, `DrawImage`,
`DrawFoldLine`. Coordinate space is **points (1/72 inch) with origin at
page bottom-left** (matches PDF). Every backend converts to its own
coord system per element.

## Active technologies

- Python 3.11, 3.12, 3.13 (CI matrix on Ubuntu + macOS)
- ReportLab 4.0+ (PDF backend)
- Pillow 10.0+ (PNG backend + image effects)
- Pydantic 2.0+ (domain models + IR)
- Typer 0.9+ (CLI)
- PyYAML 6.0+ (template loading)
- pikepdf 8.0+ (PDF/X-1a post-processing for `--export-for moo-a6`)

## Project layout

```text
src/holiday_card/
  core/
    models.py           # Pydantic domain models
    generators.py       # CardGenerator orchestration (Card → IR → backend)
    templates.py        # YAML template loading/discovery
    themes.py           # Theme definitions
    text_utils.py       # Text measurement primitives
    text_fitting.py     # Overflow strategies (extracted Wave 2 Step 2a)
    render_ir.py        # The 11-command IR (Wave 2 Step 1)
    compiler.py         # Card → list[RenderCommand] (Wave 2 Step 2b)
    export_targets.py   # Named print targets for --export-for
    per_panel.py        # Per-panel rendering helpers (POD layouts)
    sentiments.py       # Sentiment library loader for --voice
    markdown.py         # Tiny Markdown subset for --inside-message-md
    letter.py           # LetterContent model for --salutation/--signoff/--signature/--ps
    color_management.py # sRGB→CMYK conversion + ICC profile path resolution
    validators.py       # Domain validation helpers
  renderers/
    reportlab_backend.py  # IR → PDF (default; sRGB or CMYK mode)
    svg_backend.py        # IR → SVG (browser-openable)
    png_backend.py        # IR → PNG (powers `preview` command)
    pdfx_postprocess.py   # pikepdf-based PDF/X-1a:2003 upgrade
    image_effects.py      # Pillow effects (sepia/grayscale/vignette/blur)
assets/icc/             # Bundled ICC profiles
  GRACoL2013_CRPC6.icc  # 3.4MB; OutputIntent for --export-for moo-a6
  cli/
    commands.py         # Typer CLI: create, preview, templates, themes, validate
  utils/
    measurements.py     # inch ↔ point conversions; page constants
    svg_parser.py       # SVG path parser (preserved for future IR support)
    validators.py       # Input validation (image format, etc.)
tests/
  unit/                 # Wave 2 core: test_render_ir, test_compiler, test_cli, test_text_fitting,
                        #   test_text_utils, test_models, test_clipping_masks,
                        #   test_gradient_models, test_pattern_models,
                        #   test_svg_models, test_svg_parser, test_validators,
                        #   test_measurements, test_font_registry
                        # Curation/POD/markdown additions: test_sentiments, test_export_targets,
                        #   test_per_panel, test_markdown, test_render_changed
    __snapshots__/      # JSON snapshots of compile_card() output per template (8 files)
  integration/          # test_full_generation, test_svg_backend, test_png_backend,
                        #   test_per_panel_output, test_voice_flag, test_md_inside
  visual/               # Reserved for future visual regression (no tests yet)
templates/              # YAML card templates
  christmas/            # 10 templates: 4 compile (classic, geometric, modern, artist);
                        #   6 demos still need gradient/pattern/SVGPath compiler support
                        #   (festive-stripes, holiday-masterpiece, holly-wreath,
                        #    metallic-ornaments, photo-ornament, winter-sky)
  birthday/, hanukkah/, generic/, mothers_day/   # 1 template each, all compile cleanly
themes/                 # Color theme YAML
sentiments/             # Curated greeting copy: {occasion}/{voice}/{role}.yaml — 50 files
                        #   covering 5 occasions × 5 voices × 2 roles, ~250 lines total
fonts/                  # Liberation default font chain (PDF base-14 substitutes)
  curated/              # 6 curated open-source fonts (Cormorant, Playfair, Lato, Inter, Caveat, Comfortaa)
scripts/                # Stand-alone helpers used by CI/Actions
                        #   render_changed_templates.py — powers .github/workflows/render-cards.yml
.github/workflows/      # CI: ci.yml (lint/type/test/smoke/build matrix)
                        #     render-cards.yml (PR-comment card previews)
specs/                  # Historical spec-kit feature plans (001-004; some describe deleted features)
docs/industry-review/   # Six critic personas + consensus docs that drive the roadmap
```

## Commands

### Quality gates (run all of these — they're the CI blocking gates too)

```bash
ruff check src/ tests/ scripts/   # Lint — must be clean
mypy src/                         # Type-check — must be clean (strict mode)
pytest                            # All 555 tests pass
```

### Card generation

```bash
holiday-card --help
holiday-card templates                                  # list templates
holiday-card themes --occasion christmas                # list themes
holiday-card create christmas-classic -o out/card.pdf   # PDF (default)
holiday-card create christmas-classic --format svg      # SVG (opens in browser)
holiday-card create christmas-classic -o out/card.svg   # auto-detect from extension
holiday-card preview christmas-classic                  # 144 DPI PNG, opens in viewer
holiday-card preview christmas-classic --dpi 300 --no-open -o p.png
holiday-card validate templates/christmas/classic.yaml  # validate a template

# Per-panel POD output: --export-for emits one file per panel
holiday-card create christmas-classic --export-for moo-a6 -o out/moo-card/
# → out/moo-card/{front,back,inside-left,inside-right}.pdf at A6 trim + bleed
holiday-card create christmas-classic --export-for per-panel-pdf -o out/files/
# → out/files/{front,back,inside-left,inside-right}.pdf at panel-native trim + bleed

# Sentiment library: --voice picks a curated cover + inside in that register
holiday-card create christmas-classic --voice warm        # heartfelt
holiday-card create christmas-classic --voice witty       # playful
holiday-card create christmas-classic --voice spare       # minimal
holiday-card create christmas-classic --voice devotional  # religious
holiday-card create christmas-classic --voice irreverent  # dry / anti-saccharine
holiday-card create christmas-classic --voice warm --seed 42  # reproducible pick
holiday-card create christmas-classic --voice warm --blank-inside  # cover only
```

### Hidden / dev flags

```bash
holiday-card create christmas-classic --debug-emit-ir   # print compiled IR as JSON
                                                        # (skips PDF; for IR debugging)
```

## Currently supported template subset

The compiler supports backgrounds, borders, basic shapes (Rectangle,
Circle, Triangle, Star, Line) with **solid fills only**, text with
left/center/right alignment + Markdown rich text (paragraphs +
**bold**), fold lines, identity or rotation-only group transforms,
and **bleed extension** on edges that touch the page trim (default
0.125", set per Card via `card.bleed` or per Panel via `panel.bleed`).
**8 of the 14 shipped templates currently compile cleanly:**

```
christmas-classic     christmas-geometric    christmas-modern
christmas-artist      birthday-balloons      hanukkah-menorah
generic-celebration   mothers-day
```

Templates using gradients, patterns, clip masks, decorative elements,
SVG paths, or image elements raise `UnsupportedFeatureError`. **Fail
loud, not silent** is the convention — silent feature drop would let
half-rendered PDFs ship.

To support a new feature: extend `core/compiler.py` to lower the
relevant `Card` field into IR commands, then make sure each backend
either handles the new command-type combinations or raises
`NotImplementedError` with a clear message.

## How to add a new backend

The pattern that worked three times in PRs #7, #11, #12:

1. Create `src/holiday_card/renderers/{name}_backend.py` with a class
   exposing `render(commands, output_path) -> None`. Visitor over the
   discriminated union of 11 commands. Convert IR (points, bottom-left)
   to the backend's coordinate system per element.
2. For stateful drawing (groups with rotation, clipping), maintain a
   small stack and apply the IR's pivot-rotate idiom (translate; rotate;
   untranslate) on group close.
3. Strict on unknowns: anything you can't handle (e.g. gradient paints
   for the moment) raises `NotImplementedError` with a useful message.
4. Add `tests/integration/test_{name}_backend.py`. **Include
   pixel-correctness checks**, not just structural validity — see the
   `test_png_christmas_classic_has_red_pixel_in_front_panel` test for
   how the PNG suite caught a transform bug the SVG suite missed.
5. (CLI integration) Either expose via the existing `--format` enum on
   `holiday-card create`, or via a new top-level command (like
   `preview` does for PNG).

Beyond the panel's roadmap, speculative future backends:
HTML/Canvas streaming over a websocket for live template editing; a
JSON "render plan" backend for downstream tooling. A pro-press
CMYK output (CMYK color space + GRACoL ICC profile + PDF/X-1a
metadata) is **not** a speculative idea — it's the next planned
slice of Leapfrog 1, sitting on top of the bleed and `--export-for`
work already shipped.

## Code style

- Type hints on every function; `mypy --strict` passes
- Pydantic models for domain validation (frozen for IR, mutable for
  Card so messages can be applied)
- Docstrings on public APIs; one-line comment max for private helpers
- Measurements in inches in YAML/Python; converted to points once in
  the compiler
- Imports organized by ruff (`I` rule); enforced in CI
- Exception chaining: `raise X from e` everywhere (`B904` is enforced)

## Known issues (good first tasks for a fresh session)

- **Pending-compiler-support models in `models.py`:**
  `LinearGradientFill`, `RadialGradientFill`, `PatternFill`,
  `SVGPath`, `DecorativeElement`, and the clip-mask types are
  imported by `core/templates.py` + `core/validators.py` and back
  six shipped christmas demo YAMLs (`festive-stripes`,
  `holiday-masterpiece`, `holly-wreath`, `metallic-ornaments`,
  `photo-ornament`, `winter-sky`) plus the `clip_mask` field on
  `ImageElement`. The compiler refuses them at render time
  (`UnsupportedFeatureError`), so they look "dead" from a
  user-visible perspective — but the data layer is load-bearing
  groundwork. The right next step is wiring compiler support, not
  pruning.
- **Compiler feature gaps:** Adding `ImageElement` support would
  re-enable photo cards (and is the prerequisite for Leapfrog 3 AI
  imagery). Adding gradient + pattern fills would unlock the six
  demo templates above.
- **`tests/visual/` is empty:** A perceptual SSIM gate against a
  committed baseline PNG per template would catch layout regressions
  the structural tests miss. The PNG backend produces deterministic
  output, so this is tractable.

## Recent changes

- **2026-05-11 — Structured inside letter: salutation / signoff / signature / P.S. (Leapfrog 2, slice 4)**:
  Four new CLI flags (`--salutation`, `--signoff`, `--signature`, `--ps`)
  plus `--signature-font` for the handwritten-feel override. New
  `LetterContent` Pydantic model (`core/letter.py`, frozen) carries
  the five structured parts (salutation, body, signoff, signature,
  postscript). `TextElement.letter_content` is the new authoring
  surface; a model-level validator forbids it co-existing with
  `rich_content` (Markdown) since they're two different layout passes.
  Compiler emits per-part `DrawText` commands with conventional
  vertical gaps (`_LETTER_GAP_*` constants in `compiler.py`); P.S.
  renders at 85% of body size, signature accepts a font override.
  Letter parts compose freely with `--voice` / `--inside-message` /
  `--blank-inside` (those just supply the body); refuse the combo
  with `--inside-message-md` since Markdown has its own structure.
  Generator helper: `apply_inside_letter`. 33 new tests. Closes the
  engineering side of the panel's "first-class fields" item in
  `consensus-general.md:156`. Illustrator commission remains the
  outstanding piece of Leapfrog 2.
- **2026-05-10 — CMYK + ICC + PDF/X-1a:2003 (Leapfrog 1 complete)**:
  `--export-for moo-a6` now emits DeviceCMYK PDFs (k/K operators,
  no RGB), with the GRACoL2013_CRPC6 ICC profile embedded as the
  OutputIntent's `/DestOutputProfile`, an XMP metadata stream
  declaring `GTS_PDFXVersion="PDF/X-1:2001"` /
  `GTS_PDFXConformance="PDF/X-1a:2003"`, `/Info /Trapped` set to
  `/False`, and the PDF header forced to 1.4. Implementation:
  `core/color_management.py` (naive sRGB→CMYK conversion + ICC
  path resolution), `renderers/pdfx_postprocess.py` (pikepdf-based
  OutputIntent + XMP injection), `IRReportLabRenderer(color_space=
  "cmyk")` for the CMYK emission path. `ExportTarget` gained
  `color_space` + `pdfx` fields; the generator dispatches a
  CMYK-mode renderer and the post-processor when the target asks.
  New dependency: `pikepdf>=8.0`. Bundled asset:
  `assets/icc/GRACoL2013_CRPC6.icc` (3.4MB, ICC CGATS21 reference,
  freely redistributable). Color accuracy is deferred to the
  printer's RIP via the embedded OutputIntent — standard PDF/X-1a
  practice. 13 new tests in `tests/integration/test_pdfx_moo_a6.py`.
  Clears the prerequisite for AI-imagery Leapfrog 3.
- **2026-05-10 — GitHub Action: render-on-PR + sticky comment (Leapfrog 4, slice 2)**:
  New `.github/workflows/render-cards.yml` triggers on PRs touching
  templates/sentiments/fonts/themes/src. Detects affected templates
  via `scripts/render_changed_templates.py` (direct template change →
  just that template; indirect change → full shipping set), renders
  PNG previews at 144 DPI, uploads as a workflow artifact, and posts
  a sticky PR comment with the list and artifact link. Completes
  Leapfrog 4 alongside the Markdown mode in PR #26 — together they
  realize the panel's "cards-as-code identity" thesis.
- **2026-05-10 — Markdown mode for inside panel (Leapfrog 4, slice 1)**:
  New `--inside-message-md path/to/letter.md` flag turns the inside
  panel into a "Christmas letter" surface — paragraphs, **bold** spans,
  and hard line breaks render with proper paragraph spacing and
  bold-aware font fallback. Adds `core/markdown.py` (tiny parser, no
  new deps), `RichTextContent` field on `TextElement`, `_compile_rich_text`
  pass in the compiler, and `apply_inside_rich_content` on
  `CardGenerator`. Bold spans use the registered Bold variant (Lato-Bold
  today; other curated families are variable fonts and fall back to
  regular until additional weights are registered).
- **2026-05-10 — Panel-review cleanups bundle**: Four small items that
  had been on the list since the panel review (PR #19). (1) Gated
  `DrawFoldLine` behind `--with-fold-marks` / `--no-fold-marks` with
  per-target defaults (`letter` ON, per-panel OFF). (2) Renamed the
  six underscore-named christmas templates to use hyphens for
  filename/id consistency (`holly_wreath.yaml` → `holly-wreath.yaml`
  etc.). (3) Updated `_apply_front_message` and `_apply_inside_message`
  auto-add fallback to use `Lato` instead of `Helvetica`. (4) Rewrote
  the README around Tyler-the-engineer per Agreement 5.
- **2026-05-10 — Migrate 7 templates to curated fonts (Leapfrog 2, slice 3)**:
  Every shipped template now uses curated fonts intentionally rather than
  Liberation defaults. Pairings: christmas-classic (Playfair + Cormorant),
  christmas-geometric/-modern (Inter), christmas-artist (Caveat + Cormorant),
  birthday-balloons (Comfortaa + Caveat + Lato), hanukkah-menorah
  (Lato + Cormorant), generic-celebration (Inter + Lato), mothers-day
  (Playfair + Caveat + Lato). Zero Helvetica/Times-Roman references remain
  in `templates/`. Snapshots regenerated.
- **2026-05-10 — Curated font shipment (Leapfrog 2, slice 2)**: Six SIL OFL
  open-source fonts in `fonts/curated/` — Cormorant Garamond (editorial
  serif), Playfair Display (display serif), Lato (friendly sans, regular +
  bold), Inter (modern variable sans), Caveat (handwritten script),
  Comfortaa (rounded display). `font_registry` consults a `CURATED_FONTS`
  map alongside the Liberation default chain; `christmas-classic` is
  updated as a demonstration (PlayfairDisplay cover + Cormorant body).
  Existing templates referencing Helvetica/Times-Roman/Courier continue
  to work unchanged.
- **2026-05-10 — Sentiment library + `--voice` flag (Leapfrog 2, slice 1)**:
  Curated greeting copy organized as `sentiments/{occasion}/{voice}/{role}.yaml`
  for the five panel-recommended voices (warm, witty, spare, devotional,
  irreverent). New CLI flags `--voice`, `--blank-inside`, `--seed` resolve
  occasion + voice + role into a picked sentiment that fills front
  greeting and inside message slots not already set explicitly. Ships
  with a v0 starter content set (50 files, ~250 lines); intended to be
  replaced with hand-curated copy by an actual copywriter.
- **2026-05-10 — `--export-for` CLI flag + per-panel POD output**:
  Three named export targets — `letter` (default, today's behavior),
  `per-panel-pdf` (each panel as its own file at native trim + bleed),
  and `moo-a6` (each panel at true A6 with content uniformly scaled to
  fit). Adds `core/export_targets.py` (registry) and `core/per_panel.py`
  (panel-content scaling helpers). Lays the rails for CMYK / ICC /
  PDF/X-1a (next slice of Leapfrog 1).
- **2026-05-10 — Bleed support + `PageGeometry` abstraction**: Backgrounds
  now extend past the trim edge by 0.125" (industry default) on edges that
  touch the page trim. `Card.bleed` and `Panel.bleed` configure it; the
  PDF declares distinct `MediaBox` / `TrimBox` / `BleedBox` / `ArtBox`;
  SVG `viewBox` and PNG canvas grow to include the bleed band. Lays the
  rails for `--export-for moo-a6` (Leapfrog 1) without shipping it yet.
- **2026-05-10 — Wave 2 complete + v1.1.0 release**: IR seam
  (PRs #4-#10), three rendering backends (PRs #7/#11/#12), working
  `preview` command (PR #12), version bump + zero mypy errors + strict
  CI gates (PR #13). Net: 12 PRs, ~6,950 LOC removed, ~3,800 added.
- **2026-05 — Wave 1 DevEx audit (PR #1)**: Real CI on every push,
  `requirements.txt` deleted, 22 B904 + 10 null-deref bugs fixed.
- **2026-05 — Valentine deprecation (PR #8)**: Removed the 2026-02
  Valentine release (templates + decorative-element library) when
  porting to the IR proved non-trivial. Dead model code (HeartClipMask,
  etc.) intentionally kept in `models.py` for now.
- **003-vector-graphics-and-decorative-elements** (specs/): Original
  spec for vector graphics. Decorative elements piece is no longer
  shipped (see Valentine deprecation).
- **001-holiday-card-generator** (specs/): Original spec.

## Strategic context — read before adding major features

Two industry-panel reviews live in `docs/industry-review/`. Read the
relevant consensus document **before** proposing or implementing a
new feature, a new template direction, or a new strategic pivot —
the panel has already weighed in on most of the obvious moves.

- `docs/industry-review/README.md` — overview, what these are, and
  the 6 personas
- `docs/industry-review/consensus-general.md` — overall project
  critique + 5 leapfrog moves the panel jointly endorsed (Q3 2026
  → `--export-for moo-a6`; Q4 → curated taste layer; etc.)
- `docs/industry-review/consensus-ai-feature.md` — verdict on
  proposed OpenAI image generation feature (TL;DR: not now; Q1 2027,
  in a much narrower form, after the prior leapfrogs land)
- `docs/industry-review/critiques/` — 12 individual persona
  critiques (6 general + 6 AI-feature) with per-persona depth

**Key strategic decisions the panel has already informed:**

- **Audience: stay Tyler-first** (engineer-using-the-CLI). Sandy
  (the DIY-crafter persona) is well-served by Canva/Cricut. Don't
  pivot to a Canva-clone.
- **Sequencing: leapfrogs before features.** Bleed/CMYK, illustrator
  commission, and sentiment library all come BEFORE AI imagery, web
  preview, or new occasion expansion at the current quality bar.
- **Hard rails on AI imagery:** sympathy / bereavement / religious
  iconography / photo-card slots / recognizable likenesses default
  to refuse with `--i-know-what-im-doing` override.

If you want to evaluate a new feature proposal not covered above,
spin up a fresh panel — the prompts are reproducible. Ask: "spin up
the industry panel to evaluate [proposal]" and the workflow will
fire 6 critic agents + a synthesis moderator.

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
