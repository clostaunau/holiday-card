# holiday-card — Development Guidelines

Last updated: 2026-09-26. Wave 2 architecture refactor is **complete**.
Of the five industry-panel leapfrogs, **L1 (POD prepress), L2-engineering
(curated taste layer), L3 (AI imagery — authoring-time `ai-asset generate`
in its narrow, hard-railed form), L4 (cards-as-code identity), and L5
(template microsite) are shipped**; only L2-illustrator (needs a human
contractor) remains. Codebase is at v1.3.0 with all CI quality gates
blocking.

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
pipx install holiday-card           # canonical user install
uv sync --extra dev                 # hacking: locked deps from uv.lock (`pip install -e ".[dev]"` still works, unpinned)
holiday-card create christmas-classic -m "Merry Christmas!"     # writes a PDF
holiday-card create christmas-classic --format svg              # writes an SVG
holiday-card create christmas-classic --voice warm --seed 42    # picked-sentiment cover + inside
holiday-card create christmas-classic --inside-message-md letter.md   # Markdown letter mode
holiday-card create christmas-classic --salutation "Dear M," --signoff "Love," --signature "C" --ps "PS hi"   # structured letter
holiday-card create christmas-classic --export-for moo-a6 -o out/     # CMYK PDF/X-1a:2003 for MOO
holiday-card create christmas-family-photo -i me.jpg                 # your photo in the template's photo slot
holiday-card preview christmas-classic --voice warm             # PNG preview; takes every create content flag
uv run pytest                       # all 1201 tests, mypy-clean, ruff-clean
```

## Architecture

The Wave 2 refactor (PRs #4-#10) replaced a 1063-LOC monolithic
`ReportLabRenderer` with a three-layer pipeline:

1. **Domain layer** — `core/models.py`. Pydantic models for `Card`,
   `Template`, `Panel`, shapes, text, image, etc. Knows nothing about
   points, ReportLab, or rendering order.
2. **Compiler layer** — `core/compiler.py`. Pure function
   `compile_card(card) -> list[RenderCommand]`. Owns letter imposition
   (D6, `core/imposition.py`), z-sort, decorative
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
- openai 1.0+ (**optional** `[ai]` extra; only `core/ai_openai.py` imports it)

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
    card_request.py     # CardRequest + build_card / plan_output: the ONE owner of CLI precedence (D15)
    imposition.py       # letter_slot / impose_letter / panel_placements: where panels land on the sheet (D6, #58)
    errors.py           # UnsupportedFeatureError (re-exported by compiler.py)
    color_management.py # sRGB→CMYK conversion + ICC profile path resolution
    data_paths.py       # data_path(kind): the ONE resolver for bundled data (+ env overrides)
    ai_rails.py         # L3 hard category rails (occasion + prompt blocklists)
    ai_provenance.py    # L3 LicenseRecord sidecar + first-use consent gate
    ai_assets.py        # L3 POD-aware sizing + generate orchestration (injectable client)
    ai_openai.py        # L3 OpenAI image-client adapter (only module importing openai)
    images.py           # Template image path containment + PNG/JPEG content probe (D5)
    validators.py       # Domain validation helpers
  renderers/
    reportlab_backend.py  # IR → PDF (default; sRGB or CMYK mode)
    svg_backend.py        # IR → SVG (browser-openable)
    png_backend.py        # IR → PNG (powers `preview` command)
    pdfx_postprocess.py   # pikepdf-based PDF/X-1a:2003 upgrade
    image_effects.py      # Pillow effects (sepia/grayscale/vignette/blur)
  data/                 # Package data shipped in the wheel (no __init__.py);
                        #   resolved only via core/data_paths.data_path()
    templates/          # YAML card templates (21)
      christmas/        # 11 templates, all compile cleanly: classic, geometric, modern,
                        #   artist, festive-stripes, holiday-masterpiece, holly-wreath,
                        #   metallic-ornaments, photo-ornament, winter-sky, family-photo
      birthday/         # balloons + photo
      mothers_day/      # classic + photo
      hanukkah/, generic/   # 1 template each
      sympathy/, condolence/, miscarriage/, pet_loss/   # 1 "-spare" template each
    themes/             # Color theme YAML (4)
    sentiments/         # Curated greeting copy: {occasion}/{voice}/{role}.yaml — 70 files
                        #   covering 9 occasions × up-to-5 voices × 2 roles
    fonts/              # Liberation default font chain (PDF base-14 substitutes) + LICENSE, AUTHORS
      curated/          # 6 curated OFL fonts (Cormorant, Playfair, Lato, Inter, Caveat,
                        #   Comfortaa) + *-LICENSE.txt per family
    icc/                # GRACoL2013_CRPC6.icc (3.4MB; OutputIntent for --export-for moo-a6)
                        #   + NOTICE (verbatim redistribution terms)
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
                        # L3 AI imagery: test_ai_rails, test_ai_provenance, test_ai_assets
                        # Loader: test_templates_loading (extra="forbid", fail-loud keys)
                        # CLI seam: test_card_request (precedence rules 1-18, #78)
                        # Imposition: test_imposition (slot table, paper-fold oracle,
                        #   panel_placements, stale-coordinate loader check, #58)
    __snapshots__/      # JSON snapshots of compile_card() output per template (16 files)
  integration/          # test_full_generation, test_svg_backend, test_png_backend,
                        #   test_per_panel_output, test_voice_flag, test_md_inside,
                        #   test_ai_asset_cli (L3 ai-asset generate subcommand)
  visual/               # Perceptual-hash regression gate over all 17 shipped templates
                        #   (test_visual_regression.py); baselines in
                        #   fixtures/reference_cards/. Regenerate via
                        #   scripts/regenerate_visual_baselines.py.
LICENSE                 # MIT
scripts/                # Stand-alone helpers used by CI/Actions
                        #   render_changed_templates.py — powers .github/workflows/render-cards.yml
                        #   build_microsite.py — Leapfrog 5 template-gallery generator
                        #   make_placeholder_photo.py — regenerates the CC0 placeholder-photo.jpg
.github/workflows/      # CI: ci.yml (lint/type/test → build → smoke of the installed wheel)
                        #     render-cards.yml (PR-comment card previews)
                        #     microsite.yml (build + deploy gallery to GitHub Pages)
specs/                  # Historical spec-kit feature plans (001-004; some describe deleted features)
docs/industry-review/   # Six critic personas + consensus docs that drive the roadmap
```

## Commands

### Quality gates (run all of these — they're the CI blocking gates too)

```bash
uv sync --extra dev                      # Install locked deps (uv.lock); `pip install -e ".[dev]"` still works
uv lock --check                          # Lockfile in sync with pyproject.toml (CI lint job)
uv run ruff check src/ tests/ scripts/   # Lint — must be clean
uv run mypy src/                         # Type-check — must be clean (strict mode, runs on py3.11 in CI)
uv run pytest                            # All 1201 tests pass
```

After changing dependencies in `pyproject.toml`, run `uv lock` and commit
`uv.lock`. `[tool.uv] constraint-dependencies` pins `numpy<2.5` because
numpy 2.5's stubs use the Python 3.12 `type` statement, which mypy rejects
while `python_version = "3.11"`. The weekly `latest-deps.yml` workflow
ignores the lock and the constraint; a red run means bump the lock or lift
a constraint.

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
holiday-card validate src/holiday_card/data/templates/christmas/classic.yaml  # validate a template

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
Circle, Triangle, Star, Line, **SVGPath**) with **solid fills, linear
gradients, radial gradients, and patterns (stripes / dots / grid /
checkerboard)**, text with left/center/right alignment + Markdown
rich text (paragraphs + **bold** + *italic* + ***bold-italic***)
+ structured letter parts
(salutation / signoff / signature / P.S.), **photo images** (PNG/JPEG
only, content-probed; template `source_path` is relative to the YAML
file — absolute, `..` and symlink escapes are load errors, D5) with
circle / rectangle / ellipse / star clip masks, fold lines, identity
or rotation-only group transforms, and **bleed extension** on edges
that touch the page trim (default 0.125", set per Card via
`card.bleed` or per Panel via `panel.bleed`). **All 21 shipped
templates currently compile cleanly:**

```
christmas-classic         christmas-geometric        christmas-modern
christmas-artist          christmas-photo-ornament   christmas-holly-wreath
christmas-winter-sky      christmas-metallic-ornaments
christmas-festive-stripes christmas-holiday-masterpiece
christmas-family-photo
birthday-balloons         birthday-photo
hanukkah-menorah          generic-celebration
mothers-day               mothers-day-photo
sympathy-spare            condolence-spare
miscarriage-spare         pet-loss-spare
```

Remaining gaps (out-of-scope features, each raises
`UnsupportedFeatureError` rather than silently dropping content):
SVG path **arc** commands (`A`/`a` — no shipped template uses arcs),
photo `effects` / `frame_style`, panel `background_image`, text
`font_file`; an unknown `font_family` raises `UnknownFontError` (a
subclass). **Fail loud, not silent** is the convention.

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

CMYK output is already shipped as a backend mode rather than a separate
renderer: `IRReportLabRenderer(color_space="cmyk")` plus the pikepdf-based
`renderers/pdfx_postprocess.py` produce DeviceCMYK PDF/X-1a:2003 when
`--export-for moo-a6` is used. Beyond the panel's roadmap, speculative
future backends: HTML/Canvas streaming over a websocket for live
template editing; a JSON "render plan" backend for downstream tooling.

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

- **Out-of-scope compiler features (genuinely deferred, not bugs):**
  SVG path arc commands (`A`/`a` — no shipped template uses arcs),
  photo `effects` / `frame_style`, and `ImageElement` auto-sizing
  (width/height = None). All raise `UnsupportedFeatureError` at
  compile time — the "fail loud, not silent" convention.
- **L2 illustrator commission is the outstanding strategic item:**
  Not a code task — the panel's recommendation in
  `consensus-general.md` is to commission ~30 hand-illustrated SVG
  motifs in one opinionated voice and migrate the shipped templates
  to use them. Needs a contractor, not a PR.

## Recent changes

- **2026-09-29 — Letter imposition is computed from the fold type; inside
  panels land on the correct pages (expert-panel §P4 / D6, issue #58)**:
  Every shipped template placed `inside_left` top-left and `inside_right`
  top-right of the sheet. After the two folds the top-right quadrant is the
  back of the cover leaf, i.e. the *left* inside page, so every printed
  card had its inside pages swapped (christmas-modern also printed its back
  cover and inside-right upside down). New `core/imposition.py`:
  `letter_slot(fold_type, position) -> PanelSlot` (front→BR, back→BL,
  inside_left→**TR** r180, inside_right→**TL** r180), `impose_letter(panels,
  fold_type)` (model_copy of x/y/rotation) and the public
  `panel_placements(card) -> dict[PanelPosition, PanelPlacement]` (trim-
  relative rects in points; #68 crops with it). `tri_fold` and `center`
  raise `UnsupportedFeatureError`, which moved to `core/errors.py` (the
  compiler re-exports it). `CompileContext.impose: bool = True`;
  `compile_card` runs `impose_letter` before the bleed-edge pass, and
  `per_panel.build_per_panel_context` sets `impose=False`, so per-panel /
  MOO output is unchanged. **Tests that hand-place a panel must pass
  `CompileContext(impose=False)`**; otherwise a `front` panel lands in BR.
  `half_fold` is now a documented legacy alias of the 4-up `quarter_fold`:
  both emit **two** fold marks and `templates --fold-type half_fold` lists
  the same 21 templates as `quarter_fold`. Panel coordinates are derived:
  `Panel.x`/`y` default to 0.0, all 210 panel-level `x`/`y`/`rotation`
  lines were deleted from the 21 templates (all now say `quarter_fold`),
  and the `init` scaffold defaults to `quarter_fold` with no panel
  coordinates. A YAML that still sets them and disagrees with the computed
  slot raises `TemplateLoadError` naming the panel, both values and "delete
  x/y/rotation; imposition is computed from fold_type"; matching values are
  accepted. All 16 compile snapshots and all 21 visual baselines were
  regenerated and eyeballed (inside message now in the top half, upside
  down, on the side its panel maps to). Guarded by
  `tests/unit/test_imposition.py` (parametrized slot table, a paper-fold
  simulator as an independent oracle, placements == compiled background
  rects, loader checks, every shipped template), the two PNG pixel tests in
  `test_png_backend.py` (quadrant colours + a corner marker proving the
  180° rotation) and the fold-mark tests in `test_compiler.py` /
  `test_per_panel_output.py`. Letter bleed / MediaBox stays with #59.
- **2026-09-28 — `CardRequest` + `build_card` / `plan_output`: one pipeline
  behind `create`, `preview` and `--debug-emit-ir` (expert-panel §P14 /
  D15, issue #78)**: `create()` was a 437-line Typer function that owned
  every precedence rule; `preview` accepted only `-m/-o/--dpi/--open`
  (so `preview --voice spare` was `No such option`) and `_emit_ir_debug`
  forwarded 5 of ~20 inputs. New `core/card_request.py`: `CardRequest`
  (frozen, `extra="forbid"`; every `create` input minus the debug switch)
  refuses the flag conflicts in a `model_validator` in `create()`'s old
  order (unknown `--export-for` → unknown `--voice` → `--inside-message`
  + `--inside-message-md` → the #60 combos → letter part + Markdown →
  unparsable Markdown); `--fold-type` and `--format` are parsed by field
  validators with the old messages. `build_card_with_report(request,
  templates_dir=) -> (Card, BuildReport)` owns theme check, template
  load, voice picks (occasion read from `Template.occasion`, so a
  template in the wrong directory no longer gets `generic` copy),
  `--blank-inside`, letter / Markdown / plain inside modes, fold-type fit
  and photos; `build_card(r)` is `[0]`. `plan_output(request, now=) ->
  OutputPlan(target, output_format, path)` owns format inference, the
  timestamped default path and the `-o` checks. Errors are plain
  `ValueError`s (no `Error:` prefix); `validation_message` /
  `unwrap_validation_error` pull the original error out of a
  `ValidationError`. `CardGenerator.create_card` now delegates to a new
  `create_card_from_template(template, ...)`; the unreachable
  `front_message` kwarg is gone from `create_card` / `create_and_generate`.
  CLI: `create` = build request → `plan_output` → `build_card_with_report`
  → `generate` → summary; `preview` takes every content option (shared
  `_*_OPTION` objects, same short flags) and its docstring no longer
  claims WYSIWYG for inputs it ignored; `--debug-emit-ir` is
  `compile_card(build_card(request))`. `_exit_for_card_error` is the one
  error→exit mapping for both commands (`ValidationError` / `ValueError`
  → exit 2). Deleted from the CLI: `_template_occasion`,
  `_resolve_output_format`, `_check_flag_combinations`, `_pick_voice_line`,
  `_check_fold_type_fits`, `_validate_output_path`. Every exit-2 message
  is byte-identical to before, including the quoted `Error: "unknown
  export target …"` (a `KeyError` `str()` artifact, kept on purpose).
  One ordering change: a missing `--inside-message-md` file is now
  reported before other flag conflicts, because the CLI reads the file
  before it builds the request. Guarded by `tests/unit/test_card_request.py`
  (one test per precedence rule, 69 tests), `TestPipelineParity` in
  `tests/unit/test_cli.py` (the three entry points build the same request;
  `--debug-emit-ir` output equals the compiled `build_card`) and
  `TestPreviewVoiceFlag` in `tests/integration/test_voice_flag.py`.
- **2026-09-26 — `create`/`preview` fail loud on ignored or contradictory
  inputs; global `--debug` (expert-panel §P5 / D4, issue #60)**: Each of
  these used to exit 0 with the input ignored, or exit 1 with a bare
  `KeyError`. They now print `Error: …`, write nothing, and exit 2: unknown
  `--theme` (lists the sorted ids; the generator's `except
  ThemeNotFoundError: pass` is gone), a `--voice` the occasion doesn't ship
  (lists `sentiments.available_voices()`, with no library path; the two
  yellow warnings are gone), `--blank-inside` with `--inside-message` or
  `--inside-message-md`, `--seed` without `--voice`, `--signature-font`
  without `--signature`, a `--fold-type` whose panel set the template
  lacks (half/quarter need front/back/inside_left/inside_right, tri needs
  left/center/right), and bad `-o` paths via `_validate_output_path` (an
  extension other than `.pdf`/`.svg`, with a `preview` hint for `.png`; a
  `--format` / extension clash; a file path for a per-panel target). A
  suffix-less `-o` still gets `.pdf`/`.svg`. In the compiler, `_compile_panel`
  raises `UnsupportedFeatureError` for a panel `background_image` or a
  text `font_file`. It raises `UnknownFontError(UnsupportedFeatureError)`
  (via `_require_known_font`, before any measurement) for a `font_family`
  or `signature_font_family` outside `font_registry.known_font_ids()`, and
  names `<template>/<panel>/<element>`. The CLI maps
  `UnsupportedFeatureError` to exit 2. The generator now compiles before it
  creates any output dir, and `preview` / `create` no longer `mkdir output/`
  up front, so a failed run leaves nothing behind. The new root `--debug`
  option (`HOLIDAY_CARD_DEBUG`) makes every command's catch-all re-raise
  the original error. Without it, the one-line message ends with `(re-run
  with --debug for a traceback)`. Guarded by `TestCreateFailsLoud` /
  `TestDebugFlag` in `tests/unit/test_cli.py`, `TestFailLoud` in
  `test_compiler.py`, `test_generators_theme.py`, and new cases in
  `test_sentiments.py` / `test_font_registry.py`.
- **2026-09-26 — `-i/--image` fills the template's photo slots; 1200 px
  placeholder; PNG upscales photos (expert-panel §P8/§P6, issue #65)**:
  `create -i me.jpg` used to fail on every template (`ImageElement
  requires explicit width and height`). The CLI built a height-less
  element and `_apply_images` stacked it on the front panel over the
  placeholder. `ImageElement` gained `slot: str | None` (pattern
  `^photo(-[2-9])?$`). New `core/generators.fill_photo_slots(card,
  photos)` puts the k-th photo on **every** element whose slot is `photo`
  (k=1) or `photo-k`. Only `source_path` changes; geometry, clip and
  z-order stay the template's, and unfilled slots keep the placeholder.
  Each photo is checked with `probe_image` first. Too many photos, or any
  photo on a template without slots, raises `PhotoSlotError(ValueError)`.
  The CLI maps that to exit 2 and lists `templates_with_photo_slots()`
  (new, in `core/templates.py`). `CardGenerator.create_card(photos=…)`
  replaces `images=`. `_apply_images`, the CLI's stacking code and
  `utils.validators.validate_image_format` (extension-only) are deleted
  (D17). Slots: photo-ornament `photo`…`photo-5` (cover, star, three
  circles), holiday-masterpiece `photo` + `photo-2`, the other three just
  `photo`. The 400 px `sample_photo.jpg` copies became a 1200×1200
  `placeholder-photo.jpg` (CC0), generated by
  `scripts/make_placeholder_photo.py`. A test checks that all three copies
  are byte-identical. `png_backend._draw_image` now resizes to the fit
  scale up **or** down. `thumbnail` never enlarged, so photos were drawn
  at 42% size at 300 DPI. `probe_image` accepts Pillow `MPO` (dual-camera
  phone JPEGs) as `jpeg` and says `image file not found` for a missing
  path. The 5 photo-template visual baselines were regenerated and
  eyeballed. Compile snapshots are unchanged. Still to do: `preview -i`
  (#78) and PPI warnings (#66). Guarded by
  `tests/unit/test_generators_photo_slots.py`, `tests/unit/test_templates.py`,
  `test_image_rendering.py::TestCLIImageFillsPhotoSlot` and
  `test_png_backend.py::test_png_upscales_small_photo_to_fill_rect`.
- **2026-09-26 — Template images resolve against the template file;
  image bytes are probed before embedding (security, expert-panel §P8 /
  D5, issue #64)**: A template or `Card` whose `image_elements[].source_path`
  named any readable file (e.g. `secret.env`) got it base64-embedded into
  SVG output as `data:application/octet-stream`. New `core/images.py`:
  `resolve_template_image_path` rejects absolute paths, `..` components and
  symlink escapes; `probe_image` requires Pillow to read a whole PNG or
  JPEG (never trusts the extension; truncated, GIF, text and >50 MP files
  refused) and raises `ImageSourceError`. `load_template_from_file`
  rewrites every image `source_path` to an absolute path inside the
  template's dir (failures → `TemplateLoadError`, so `validate` fails too).
  `_compile_image` refuses relative paths (**no cwd fallback**), probes the
  file and puts `format` / `width_px` / `height_px` on `ImageRef` (#66
  consumes the pixel size). The SVG backend takes its MIME type from
  `ImageRef.format`; the extension map and `octet-stream` fallback are
  gone. `sample_photo.jpg` (now `placeholder-photo.jpg`, #65) ships next to the christmas / birthday /
  mothers_day templates, and the six `contextlib.chdir(tests/fixtures)`
  workarounds in scripts and tests are deleted. CLI `create` / `preview`
  map `ImageSourceError` to `Error: …` + exit 2. The CI smoke job renders
  `christmas-photo-ornament` to SVG from the installed wheel. Visual
  baselines and compile snapshots unchanged. Guarded by
  `tests/unit/test_images.py`, `tests/unit/test_templates_images.py`,
  `test_svg_backend.py::test_svg_refuses_non_image_source` and
  `test_image_rendering.py::TestShippedPhotoTemplateFromAnyCwd`.
- **2026-09-26 — Templates load via `Template.model_validate` with
  `extra="forbid"` (expert-panel §P3 / D3, issue #56)**: The hand-written
  YAML parsers in `core/templates.py` (`_parse_template` / `_panel` /
  `_text_element` / `_fill_style` / `_shape_element`) re-listed model
  fields and silently dropped the rest: SVGPath `x`/`y`, text `z_index` /
  `font_style` / `rotation`, panel `border`, Line `rotation`/`fill`. Unknown
  shape or fill types, and malformed shapes, became skipped `None`s. They
  are deleted (D17). `load_template_from_file` now calls
  `Template.model_validate` and raises `TemplateLoadError` listing every
  Pydantic error `loc` (e.g. `panels.0.text_elements.0.colr: Extra inputs
  are not permitted`). **Every domain model reachable from `Template`, plus
  `Card`, has `model_config = ConfigDict(extra="forbid")`**. A typo'd key
  is an error, and so is an unknown kwarg in Python (several test fixtures
  had been passing a non-existent `Card(occasion=…)`). YAML aliases live on
  the models via `validation_alias=AliasChoices(...)`: `Line`
  `x1/y1/x2/y2`, `PatternFill` `angle` → `rotation`. `default_content` is
  gone. With `x`/`y` honoured, holly-wreath and holiday-masterpiece paths
  escaped their panels (authored values were leaf centres, not path
  origins), so the template coordinates were fixed. The model semantics
  stayed as they were. Compiled IR is byte-identical for the other 19
  templates. Regenerated: `compile_card__christmas-holly-wreath.json` and
  both visual baselines (eyeballed). Guarded by
  `tests/unit/test_templates_loading.py` and the new
  `test_shipped_svg_path_bbox_inside_panel` in `test_compiler_svg_path.py`.
  The compiler still ignores text `font_style` / `rotation` (#63) and
  `font_file` (#60).
- **2026-09-26 — A closed stdout pipe exits 0 quietly (issue #92)**:
  `holiday-card themes | grep -q x` used to print `Error listing themes:
  [Errno 32] Broken pipe` plus interpreter flush noise and exit 1, which
  broke `pipefail` pipelines at random. The root group is now `_CLIGroup`
  (`typer.Typer(cls=…)` in `cli/commands.py`). It catches
  `BrokenPipeError` from any command or subcommand, points fd 1 at
  `/dev/null` and exits 0. The eager `--version` callback uses the same
  helper, and the per-command re-raise clauses are now `except
  (typer.Exit, BrokenPipeError)`. **A new command with an `except
  Exception` block must let `BrokenPipeError` through the same way.** The
  CI smoke job uses `cli | grep -q` again. Guarded by
  `tests/integration/test_cli_broken_pipe.py`, which gives the subprocess
  a pipe whose read end is already closed, so EPIPE happens every time.
- **2026-09-26 — Ship bundled data inside the wheel + smoke the installed
  wheel (expert-panel §P1 / D1, issue #55)**: `pipx install holiday-card`
  was completely broken — the wheel carried only the ICC profile, so
  `templates`/`themes` printed nothing (exit 0) and `create` died on
  `No such file or directory: 'templates'`. `templates/`, `themes/`,
  `sentiments/`, `fonts/` and `assets/icc/` were `git mv`-ed to
  `src/holiday_card/data/` (plain package data, no `__init__.py`); the
  hatch `force-include` table and `assets/` are gone. New
  `core/data_paths.py` is the single resolver: `data_path(kind)` honors
  `HOLIDAY_CARD_{TEMPLATES,THEMES,SENTIMENTS}` (replaces the bundled dir;
  a non-directory raises `DataPathError`), else
  `importlib.resources.files("holiday_card") / "data" / kind`. No
  `__file__` walking, no cwd fallback. `get_*_dir`, `FONT_DIR` and
  `default_cmyk_icc_path` all delegate to it. `templates` / `themes`
  with no filter and an empty catalog now exit 1 with `Error: no …
  found in <dir> — installation is missing bundled data` on stderr
  (a filter that matches nothing still exits 0). Added root `LICENSE`
  (MIT) and `data/icc/NOTICE` (verbatim ICC-registry terms). CI now runs
  `lint/type-check/test → build → smoke`; `smoke` has **no checkout**:
  it installs `dist/*.whl` into a fresh venv, checks the wheel listing
  (≥21 templates, ≥70 sentiments, ≥25 TTFs, LICENSE, ICC), and runs the
  CLI from `$RUNNER_TEMP`. Its grep calls read from files, because
  `cli | grep -q` makes the CLI die of EPIPE under `pipefail`.
  `scripts/render_changed_templates.py` now treats
  `src/holiday_card/data/templates/**.yaml` as direct hits. Guarded by
  `tests/unit/test_data_paths.py` plus CLI / ICC / font-registry tests.

- **2026-09-26 — Locked dependencies with `uv.lock` + green mypy gate
  (expert-panel §P2, issue #54)**: Committed a universal `uv.lock`; CI's
  lint / type-check / test jobs and the render-cards + microsite
  workflows now install with `uv sync --locked` and run tools via
  `uv run`, and the lint job runs `uv lock --check`. Root cause of the red
  mypy job: on py3.12 the resolver pulled numpy 2.5.3 (via imagehash),
  whose stubs use the `type` statement that mypy rejects under
  `python_version = "3.11"`. Fixed with `[tool.uv] constraint-dependencies
  = ["numpy<2.5"]` and by running `type-check` on Python 3.11. Floors
  raised: `Pillow>=10.3.0` (CVE-2024-28219), `typer>=0.12` (dropped the
  removed `[all]` extra). New weekly `.github/workflows/latest-deps.yml`
  tests unpinned latest deps on 3.11 + 3.13 (allowed to go red; its
  `uv pip install --no-config` is required — without it `uv pip` inside
  the project silently applies the numpy constraint). Pre-commit
  ruff/mypy are now `repo: local` hooks running `uv run …`, so they use the
  locked versions. A `[dependency-groups] dev` group re-exports the `dev`
  extra so bare `uv run pytest` keeps the dev tools installed. Added
  `.python-version` (3.12). Guarded by `tests/unit/test_dependency_policy.py`
  (6 tests).
- **2026-06-02 — L3 AI imagery: authoring-time `ai-asset generate`
  (narrow, hard-railed form)**: Ships the panel's recommended shape from
  `consensus-ai-feature.md` — an **authoring-time** subcommand that bakes
  one image to disk and **never** runs in the render path (preserves the
  reproducibility moat). Four new `core/ai_*.py` modules, each TDD'd:
  `ai_rails.py` (the hard category gates: sympathy-class occasions refuse
  by default via `ai_imagery_allowed`; trademark / religious-iconography /
  likeness prompt blocklists; `evaluate_rails` returns `RailViolation`s),
  `ai_provenance.py` (`LicenseRecord` → `<asset>.license.yaml` sidecar +
  first-use consent gate under `$XDG_CONFIG_HOME/holiday-card/`),
  `ai_assets.py` (POD-aware `build_ai_request` — trim+2×bleed at 300 DPI
  rounded to /16; `generate_ai_asset` orchestration over an **injectable**
  `ImageClient` Protocol, so the whole feature is testable with no network
  / no `OPENAI_API_KEY`; writes sRGB-tagged PNGs), and `ai_openai.py` (the
  only module importing `openai`, lazily, behind the `[ai]` extra).
  CLI: `holiday-card ai-asset generate` (typer sub-app) with `--subject`,
  `--reference` (required — image-reference mode is the default style
  anchor; `--unsafe-no-style-anchor` opts out), `--occasion` (drives the
  rails), `--export-for` (sizes the image), `--i-know-what-im-doing`
  (override that prints every rail reason first), and `--accept-ai-terms`
  (non-interactive consent). Refusals: rail-blocked → exit 5, consent
  missing → exit 3, missing key/extra → exit 4 (clean error, no
  traceback). New `[ai]` extra (`openai>=1.0`); project stays fully
  functional without it. README carries the panel's verbatim
  personal-use positioning paragraph. **What it deliberately does NOT
  do** (all out-of-scope per the consensus): render-time API calls,
  AI-generated copy, panel/photo replacement, free text-to-image as the
  default. 46 new tests (rails 23, provenance 7, assets 9, CLI 7).
  Completes L3; only the L2 illustrator commission (needs a human)
  remains of the panel's named leapfrogs.
- **2026-05-26 — Bold + BoldItalic TTFs for Cormorant + Playfair**:
  Mirrors the italic loop shipped in #48. The two editorial-serif
  families now have full Regular + Bold + Italic + BoldItalic statics
  in `fonts/curated/`. Static Bold and BoldItalic TTFs were instanced
  from the variable masters at weight=700 using
  `fontTools.varLib.instancer` (the upstream Google Fonts repos only
  ship variable masters; ReportLab and Pillow load variable fonts at
  the default weight, so instanced statics are what actually render
  bold). New `CURATED_FONTS` entries: `Cormorant-Bold`,
  `Cormorant-BoldItalic`, `PlayfairDisplay-Bold`,
  `PlayfairDisplay-BoldItalic`. Extends `markdown._BOLD_ITALIC_VARIANT`
  and `_KNOWN_BOLD_VARIANTS` / `_KNOWN_BOLD_ITALIC_VARIANTS`. After
  this PR all four style combinations (regular, bold, italic,
  bold-italic) render visibly on christmas-classic and the other
  9 templates that use Cormorant for inside body. Inter, Caveat,
  Comfortaa still fall back to regular for bold — documented
  limitation. Visual-eyeball confirmed: a Markdown letter on
  christmas-classic with mixed `*it*`, `**bold**`, `***both***`
  spans renders four distinct weights.
- **2026-05-25 — `--inside-message-md` / `--inside-message` panel
  targeting fix**: The three inside-content apply functions
  (`_apply_inside_message`, `apply_inside_letter`,
  `apply_inside_rich_content`) previously only searched the
  `inside_left` panel for a "message" target. But shipped templates
  put the "message" element on `inside_right` (10 of 21 templates do
  this; the rest ship no inside text). The functions hit the auto-add
  fallback every time and dropped a fresh `Lato` element onto
  `inside_left` — leaving the template's existing message untouched.
  Two simultaneous inside bodies (template's default in Cormorant +
  user's content in Lato) rendered on every `christmas-classic`
  Markdown letter. Extracted a shared `_find_or_add_inside_target`
  helper that searches `inside_right` first, then `inside_left`,
  then falls back to auto-add — and updated all three apply functions
  to use it. Side effect: italic Markdown now renders in the
  template's intended font (Cormorant-Italic on christmas-classic
  etc.) instead of falling back to Lato (which has no italic). 4 new
  integration tests pin the new targeting behavior.
- **2026-05-25 — Italic TTFs for Cormorant + Playfair (closes Italic
  Markdown loop)**: Bundles `CormorantGaramond-Italic.ttf` and
  `PlayfairDisplay-Italic.ttf` (both SIL OFL 1.1, variable-weight from
  Google Fonts) under `fonts/curated/`, registers them in `CURATED_FONTS`
  as `Cormorant-Italic` / `PlayfairDisplay-Italic`, extends
  `markdown._ITALIC_VARIANT` and `_KNOWN_ITALIC_VARIANTS` to route
  italic resolution to the new TTFs. Italic spans on the two editorial-
  serif families (the ones where italic matters most) now render real
  italic glyphs end-to-end. Inter/Caveat/Comfortaa/Lato still fall back
  to regular — same documented limitation as bold. 8 new tests
  (4 IR-level + 4 registry-coverage via the parametrized expected-set
  expansion).
- **2026-05-25 — Italic Markdown support**: `--inside-message-md` now
  parses `*italic*` and `_italic_` spans alongside the existing `**bold**`,
  plus `***bold-italic***` / `___bold-italic___` as a combined-style
  shorthand. `StyledRun` gained an `italic: bool` field. The parser
  shifted from a two-pass (bold-then-italic) regex to a recursive-
  descent walk over marker priority (triple > double > single) so
  ``***x***`` resolves cleanly without the lazy bold regex eating the
  inner asterisks. `font_id_for_run` accepts an `italic=` kwarg and
  maps to PDF base-14 conventions (`Helvetica-Oblique`, `Times-Italic`,
  `Courier-Oblique` for italic; `Helvetica-BoldOblique` and friends
  for bold-italic). Curated fonts fall back to regular — same
  documented limitation as bold — and lift once italic TTFs are added
  to `fonts/curated/`. Compiler's rich-text layout threads the italic
  flag through the wrapper (line-merge predicate now requires both
  bold AND italic to match). 14 new tests.
- **2026-05-25 — Sympathy-class occasion taxonomy (Leapfrog 2 finishing slice)**:
  Adds the four sympathy-class occasions the panel called out in
  `consensus-ai-feature.md:109` as a prerequisite for L3 AI imagery
  (so the hard-rails have categories to refuse against). New
  `OccasionType` values: `SYMPATHY`, `CONDOLENCE`, `MISCARRIAGE`,
  `PET_LOSS`. Each ships one restrained template (`sympathy-spare`,
  `condolence-spare`, `miscarriage-spare`, `pet-loss-spare`) plus
  a curated voice subset: `warm` + `spare` everywhere, plus
  `devotional` for sympathy/condolence only. Witty and irreverent
  are deliberately not shipped for any sympathy-class occasion
  ("absent rather than wrong"); devotional skipped for miscarriage
  and pet_loss because religious framing of those losses is delicate
  enough that absence beats getting it wrong. Asking the CLI for an
  un-shipped combination raises `SentimentNotFoundError` — fail
  loud. Sentiment lines are hand-curated, not v0/generated. 21 new
  templates shipping (was 17), 20 new sentiment files, +6 tests.
- **2026-05-11 — Leapfrog 5: template-gallery microsite + GitHub Pages**:
  Static site shipped: one HTML page per template (14 total) with a
  form that builds a copy-paste-ready `holiday-card create ...`
  command, plus a gallery index grouped by occasion. The Sandy
  persona escape hatch the panel endorsed in
  `docs/industry-review/consensus-general.md:163`. No backend, no
  WASM build, no in-browser PDF generation — the site is a showcase
  that surfaces the CLI's full surface (greeting / inside /
  --voice / --salutation / --signoff / --signature / --ps /
  --export-for moo-a6) as a friendly form. Vanilla CSS + JS only;
  no Jinja2, no Tailwind, no React. New file
  `scripts/build_microsite.py` generates the site; new workflow
  `.github/workflows/microsite.yml` deploys to GitHub Pages on
  every push to main. Photo-card templates render thumbnails via
  `contextlib.chdir(tests/fixtures)` so the bundled
  `sample_photo.jpg` is found at compile time. 10 new tests.
  Completes the panel's named leapfrogs 1, 2 (engineering side),
  4, and 5; only L3 (AI imagery — deferred per
  `consensus-ai-feature.md`) and the L2 illustrator commission
  (needs a human) remain.
- **2026-05-11 — SVGPath compiler support + 14/14 templates compile**:
  Closes the last two dead christmas templates (holly-wreath,
  holiday-masterpiece). `_compile_svg_path` parses the path's `d`
  string via `utils/svg_parser.SVGPathParser`, then converts each
  `PathCommand` to one or more `PathOp` entries via a new helper
  `_path_commands_to_ops` that resolves relative coords against the
  running cursor, reflects control points for `S` and `T`, applies
  `H`/`V` shortcuts, and re-emits `move` on `Z` close. `SVGPath` model
  gained `x` and `y` fields (panel-relative inches) — shipped
  templates were authoring them all along but the model was silently
  dropping the values. Arc commands (`A`/`a`) raise
  `UnsupportedFeatureError` (no shipped template uses arcs). PNG
  backend's `_draw_path` upgraded from "endpoints only" to proper
  cubic + quadratic Bezier sampling (16 samples per segment;
  `_sample_cubic_into` / `_sample_quadratic_into` helpers). 13 new
  tests covering path-op conversion (move/line/H/V/cubic/quadratic/
  smooth-reflection/close), `_compile_svg_path` (scale + offset +
  rotation wrap), arc rejection, and end-to-end compilation of both
  revived templates.
- **2026-05-11 — Gradient + pattern compiler support + 3 dead templates revived**:
  Linear gradients, radial gradients, and patterns (stripes / dots /
  grid / checkerboard) now render across all three backends. Compiler
  conversions in `core/compiler.py`: `_linear_gradient_to_paint` uses
  the shape bbox to resolve angle into absolute start/end points;
  `_radial_gradient_to_paint` interprets center/radius as panel-relative
  inches (matching the convention shipped templates actually use; the
  previous "fraction of shape" semantic was contradicted by every
  template). `RadialGradientFill` model validators loosened: center
  and radius are now panel-relative inches with no upper bound.
  SVG backend gained `_register_linear_gradient` / `_register_radial_gradient`
  / `_register_pattern` that emit `<linearGradient>` / `<radialGradient>`
  / `<pattern>` into `<defs>` and reference them via `url(#id)`. PDF
  backend gained `_draw_shape_with_complex_fill` that uses ReportLab's
  `canvas.linearGradient` / `radialGradient` inside a shape clip;
  patterns tile manually as filled shapes. CMYK mode propagates to
  gradient stops via `rgb_to_cmyk` so `--export-for moo-a6` produces
  CMYK gradients. PNG backend renders gradients via per-pixel
  interpolation into a shape-bbox-sized RGBA image, then composites
  through a shape mask (Pillow `ImageChops.multiply`). Three previously
  dead templates now compile: `christmas-winter-sky` (linear),
  `christmas-metallic-ornaments` (radial), `christmas-festive-stripes`
  (pattern). `christmas-holiday-masterpiece` still needs SVGPath
  support; `christmas-holly-wreath` is SVGPath-only. 12 new tests.
- **2026-05-11 — ImageElement compiler support + photo cards**:
  Photo cards render end-to-end through all three backends.
  `_compile_image` in `core/compiler.py` converts an `ImageElement`
  into an optional `BeginGroup` (for rotation, pivot-rotate around
  image center), optional `BeginClip` (for `clip_mask`), `DrawImage`,
  matching `EndClip` / `EndGroup`. Clip-mask types in scope:
  Circle / Rectangle / Ellipse / Star (Star → `PolygonGeom` with the
  same angular convention as `_compile_star`). Heart and SVGPath
  clip masks raise `UnsupportedFeatureError`. `image.effects`,
  `image.frame_style`, and auto-sizing (width/height = None) are
  also deferred. Backends: SVG backend gained a real `_draw_image`
  that base64-embeds the source image as a `data:image/*` URI; PNG
  backend gained `_draw_image` + clip masking via `PIL.ImageChops`
  multiplication; PDF backend already had drawImage. `templates.py`
  now parses `image_elements` from YAML (was silently dropping
  them — a latent bug that hid the photo-ornament template).
  17 new tests covering compiler IR shape, all three backend renderers,
  and pixel-correctness inside/outside the clip on PNG output.
  `christmas-photo-ornament` left out of `SUPPORTED_SNAPSHOT_TEMPLATES`
  because the snapshot would carry a machine-absolute resolved source
  path; pixel-correctness integration test covers it instead.
  Clears one of the L3 (AI imagery) prerequisites — the AI workflow's
  baked PNGs now have a working IR pipeline to render through.
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
- `docs/industry-review/consensus-ai-feature.md` — verdict on the
  proposed OpenAI image generation feature (TL;DR: not in the broad
  proposed shape; ship narrowly after the prior leapfrogs land).
  **Shipped 2026-06-02** as the `ai-asset generate` subcommand in
  exactly that narrow shape — see the v1.3.0 changelog entry and the
  four `core/ai_*.py` modules. The doc remains the spec of record for
  what was deliberately left out.
- `docs/specs/2026-09-26-expert-panel-remediation.md` — the
  **engineering** panel's findings (packaging, loader, imposition,
  PDF/X, backend parity, CLI) + standing decisions D1–D17. It is the
  spec of record for the `expert-panel` GitHub issues; read the
  relevant §P section before working one of them.
- `docs/industry-review/critiques/` — 12 individual persona
  critiques (6 general + 6 AI-feature) with per-persona depth

**Key strategic decisions the panel has already informed:**

- **Audience: stay Tyler-first** (engineer-using-the-CLI). Sandy
  (the DIY-crafter persona) is well-served by Canva/Cricut. Don't
  pivot to a Canva-clone.
- **Sequencing: leapfrogs before features.** Bleed/CMYK, illustrator
  commission, and sentiment library all came BEFORE AI imagery — which
  is why L1 + L2-engineering shipped first and L3 only landed once they
  were in place. Hold the same line for any future big feature.
- **Hard rails on AI imagery (now enforced in code):** sympathy /
  bereavement / religious iconography / photo-card slots / recognizable
  likenesses default to refuse with a `--i-know-what-im-doing` override.
  Implemented in `core/ai_rails.py` (`evaluate_rails`); extend the
  blocklists there, not in the CLI.

If you want to evaluate a new feature proposal not covered above,
spin up a fresh panel — the prompts are reproducible. Ask: "spin up
the industry panel to evaluate [proposal]" and the workflow will
fire 6 critic agents + a synthesis moderator.

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
