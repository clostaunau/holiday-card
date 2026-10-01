# holiday-card — Development Guidelines

Last updated: 2026-09-30. Wave 2 architecture refactor is **complete**.
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
                                    # PDF: < 300 PPI warns, < 150 PPI exits 2 (--allow-low-res: proofs only)
holiday-card preview christmas-classic --voice warm             # PNG preview; takes every create content flag
uv run pytest                       # full suite, mypy-clean, ruff-clean, coverage ≥ 92%
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
   inches→points conversion. The decision layer. It measures text
   through an injected `TextMeasurer` Protocol (`core/text_measure.py`;
   `CompileContext.measurer`, else the default the package `__init__`
   registers lazily); the ReportLab measurer lives in
   `renderers/reportlab_measurer.py`. No `core/*.py` imports ReportLab or
   `holiday_card.renderers`, except `generators.py` (function-local only,
   #75).
3. **Backend layer** — `renderers/{reportlab,svg,png}_backend.py`. Each
   implements `render(commands, output_path)` — a visitor over the
   discriminated union of 11 commands. No semantic decisions; every
   command has one obvious translation.

The IR (`core/render_ir.py`) is the seam. 11 frozen Pydantic command
types: `BeginPage`, `EndPage`, `SetMetadata`, `BeginGroup`, `EndGroup`,
`BeginClip`, `EndClip`, `DrawShape`, `DrawText`, `DrawImage`,
`DrawFoldLine`. Coordinate space is **points (1/72 inch) with origin at
page bottom-left** (matches PDF). Every backend converts to its own
coord system per element. The paint union `PaintU` is `SolidPaint`,
`LinearGradientPaint`, `RadialGradientPaint`; there is no pattern paint,
because the compiler lowers pattern fills to a clip plus solid
primitives (#74, D13).

## Active technologies

- Python 3.11, 3.12, 3.13 (CI matrix on Ubuntu + macOS)
- ReportLab 4.0+ (PDF backend)
- Pillow 10.3+ (PNG backend, image probing, ICC via ImageCms)
- Pydantic 2.0+ (domain models + IR)
- Typer 0.9+ (CLI)
- PyYAML 6.0+ (template loading)
- pikepdf 8.0+ (PDF/X-1a post-processing for `--export-for moo-a6`)
- fontTools 4.47+ (`fontTools.subset` only: glyph subsets embedded in SVG output, #76)
- openai 1.0+ (**optional** `[ai]` extra; only `core/ai_openai.py` imports it)
- OpenRouter `POST /images` over stdlib `urllib` (no extra; `core/ai_openrouter.py` is the
  only `urllib.request` importer)

## Project layout

```text
src/holiday_card/
  core/
    models.py           # Pydantic domain models
    generators.py       # CardGenerator orchestration (Card → IR → backend)
    templates.py        # Template search path (env → XDG user → builtin) + resolve_template (#79)
    themes.py           # Theme definitions
    text_utils.py       # Text measurement primitives
    text_fitting.py     # Overflow strategies (extracted Wave 2 Step 2a)
    text_measure.py     # TextMeasurer Protocol + default registry: the compiler's only font-metrics seam (#75)
    render_ir.py        # The 11-command IR (Wave 2 Step 1)
    compiler.py         # Card → list[RenderCommand] (Wave 2 Step 2b)
    export_targets.py   # Named print targets for --export-for
    per_panel.py        # Per-panel card + CompileContext (native panel; the compiler fits it, #73)
    sentiments.py       # Sentiment library loader for --voice
    markdown.py         # Tiny Markdown subset for --inside-message-md
    letter.py           # LetterContent model for --salutation/--signoff/--signature/--ps
    card_request.py     # CardRequest + build_card / plan_output: the ONE owner of CLI precedence (D15)
    imposition.py       # letter_slot / impose_letter / panel_placements: where panels land on the sheet (D6, #58)
    errors.py           # UnsupportedFeatureError (re-exported by compiler.py)
    flatten.py          # PDF/X transparency flattening against a known solid backdrop (D10, #71)
    color_management.py # CMYKConverter (ICC sRGB→GRACoL2013, 300% ink cap, black rules) + ICC path resolution
    data_paths.py       # data_path(kind): the ONE resolver for bundled data (+ env overrides)
    ai_errors.py        # ProviderError (refused/environment/usage/transient) + redact / sanitize (stdlib only, #142)
    ai_rails.py         # L3 hard category rails (occasion + prompt blocklists)
    ai_provenance.py    # L3 provider-neutral LicenseRecord + per-provider consent (#147); the AI
                        #   PNG marker and require_sidecar: the one provenance check (#144)
    ai_providers.py     # AIProvider registry (key var + default model), resolve_model / supports_seed,
                        #   make_image_client: the ONE client factory (#146; stdlib-only imports);
                        #   list_models / model_listing_payload for `ai-asset models` (#152)
    ai_assets.py        # L3 POD-aware sizing, MODEL_SIZE_POLICIES (#87), PixelSize / AspectSize request shapes
                        #   + provider-neutral ImageClient (#146), generate orchestration,
                        #   decode_b64_image / open_generated_image: model bytes as untrusted input (#141)
    ai_openai.py        # L3 OpenAI image-client adapter (only module importing openai)
    ai_openrouter_models.py  # L3 curated OpenRouter image allowlist: pinned endpoint, capabilities,
                        #   pricing, upstream terms (stdlib only, #148); cited --max-cost bounds (#151)
    ai_cost.py          # L3 offline upper-bound price for --max-cost (#151): estimate_max_cost from
                        #   the allowlist rows + bounds; NoPriceOnRecordError / CostCapExceededError
    ai_openrouter.py    # L3 OpenRouter `/images` client over stdlib urllib (#149): the only
                        #   `urllib.request` importer; no redirects, capped read, split timeouts;
                        #   wired to the CLI as `--provider openrouter` (#150)
    images.py           # Template image path containment + PNG/JPEG content probe (D5)
                        #   + effective-PPI print check on the IR (#66)
    template_checks.py  # check_template: fonts, bounds, default theme, compile smoke (#57)
    template_schema.py  # template_json_schema: model JSON Schema + AliasChoices names (#57)
  renderers/
    reportlab_backend.py  # IR → PDF (default; sRGB or CMYK mode)
    reportlab_measurer.py # ReportLabTextMeasurer: pdfmetrics widths/ascent + the font catalog (#75)
    svg_backend.py        # IR → SVG (browser-openable, self-contained: fonts embedded as glyph subsets)
    svg_fonts.py          # fontTools subset → `@font-face` data URI per font_id + GENERIC_FAMILY (#76)
    png_backend.py        # IR → PNG (powers `preview`); clips/dashes/text alpha honoured, bundled TTFs only
    pdf_metadata.py       # build_xmp: the ONE XMP builder (PDF/X + AI disclosure) + write_disclosure_xmp
                          #   (non-PDF/X PDFs with AI imagery); pikepdf function-local (#145)
    pdfx_postprocess.py   # pikepdf-based PDF/X-1a:2003 upgrade (XMP via pdf_metadata.build_xmp)
    pdfx_preflight.py     # Rule-based PDF/X-1a:2003 checker (D11; veraPDF has no PDF/X)
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
    commands.py         # Typer CLI: create, preview, templates, themes, validate,
                        #   ai-asset generate / models (curated, offline listing, #152)
    exit_codes.py       # ExitCode (0-7) + the root --help epilog (#80)
  utils/
    measurements.py     # inch ↔ point conversions; page constants
    svg_parser.py       # SVG path parser used by the compiler's `_compile_svg_path`
tests/
  unit/                 # One test_<module>.py per src module, plus policy tests:
                        #   test_core_purity / test_ai_import_confinement (AST import rules),
                        #   test_test_isolation (key scrub + socket guard), test_workflow_policy,
                        #   test_dependency_policy, test_packaging_metadata, test_docs_counts
    __snapshots__/      # JSON snapshots of compile_card() output per template (16 files)
  integration/          # End-to-end CLI and backend tests; test_readme_examples runs every
                        #   README `holiday-card` line (#88); test_ai_asset_cli_openrouter drives
                        #   the real factory + client over a FakeTransport (#150)
  visual/               # Per-panel pixel gate (#68): 21 templates × {png, pdf} × 4 panels at
                        #   144 DPI; baselines in fixtures/reference_cards/{png,pdf}/, generated
                        #   on Ubuntu by the visual-baselines workflow; eyeball before commit
  conformance/          # Cross-backend conformance vs the SVG oracle (#67, D12); regenerate
                        #   docs/conformance-matrix.md from capabilities.py
  live/                 # Opt-in paid smoke (live_ai): skipped unless HOLIDAY_CARD_LIVE_OPENROUTER=1
                        #   + OPENROUTER_API_KEY; never in CI (#150)
  fixtures/openrouter/  # Recorded OpenRouter responses (scripts/make_openrouter_fixtures.py)
  ai_fixtures.py        # bake_fake_ai_asset: a real marked asset + sidecar, no network (#144)
  rasterize.py          # Shared pypdfium2 PDF rasterizer (conformance + visual gate)
  ast_imports.py        # The one AST import walker
LICENSE                 # MIT
scripts/                # Stand-alone helpers used by CI/Actions
                        #   render_changed_templates.py — powers .github/workflows/render-cards.yml
                        #   check_release_version.py — release.yml's tag == __version__ check + notes (#86)
                        #   build_microsite.py — Leapfrog 5 template-gallery generator (thumbnails
                        #     via build_card; voices from available_voices; -i on photo-slot pages)
                        #   make_placeholder_photo.py — regenerates the CC0 placeholder-photo.jpg
                        #   refresh_openrouter_models.py — OpenRouter allowlist drift table / entries
                        #     from the public catalogue (dev-only; never in CI, #148)
                        #   make_openrouter_fixtures.py — writes the image-bearing OpenRouter
                        #     response fixtures + golden request deterministically (dev-only, #149)
.github/workflows/      # CI: ci.yml (lint/type/test → build → smoke of the installed wheel;
                        #     `audit` = pip-audit of the uv.lock export, fails on any known CVE)
                        #     render-cards.yml (PR-comment card previews; job summary on fork PRs)
                        #     microsite.yml (build + deploy gallery to GitHub Pages)
                        #     latest-deps.yml (weekly unpinned canary + weekly lock audit)
                        #     release.yml (tag vX.Y.Z → build/check/smoke → PyPI via OIDC → GitHub Release, #86)
                        #   Every `uses:` is pinned to a 40-hex SHA + `# vX.Y.Z` comment and
                        #   every workflow declares `permissions:` (tests/unit/test_workflow_policy.py).
.github/dependabot.yml  # Weekly grouped PRs for the action pins and uv.lock (#85)
specs/                  # Historical spec-kit feature plans (001-004; some describe deleted features)
docs/industry-review/   # Six critic personas + consensus docs that drive the roadmap
docs/template-authoring.md  # Template authoring guide (coords, shapes, fills, fonts, validate loop)
docs/template-schema.json   # Generated by `holiday-card schema`; a test keeps it in sync
```

## Commands

### Quality gates (run all of these — they're the CI blocking gates too)

```bash
uv sync --extra dev                      # Install locked deps (uv.lock); `pip install -e ".[dev]"` still works
uv lock --check                          # Lockfile in sync with pyproject.toml (CI lint job)
uv run ruff check src/ tests/ scripts/   # Lint — must be clean
uv run mypy src/                         # Type-check — must be clean (strict mode, runs on py3.11 in CI)
uv run pytest                            # Full suite must pass (PNG visual gate needs raqm: see tests/visual)
uv run pytest --cov=holiday_card         # + branch-coverage floor: fail_under = 92 in pyproject.toml (CI runs this)
uv run pytest -m pdfx                    # PDF/X-1a preflight (needs pdffonts + gs; CI job pdfx-preflight)
```

Actions are SHA-pinned: Dependabot bumps the SHA and its `# vX.Y.Z` comment
weekly. For a manual bump, look the SHA up (never from memory) with
`gh api repos/<owner>/<repo>/commits/<tag> --jq .sha` and update the comment.

After changing dependencies in `pyproject.toml`, run `uv lock` and commit
`uv.lock`. `[tool.uv] constraint-dependencies` pins `numpy<2.5` (nothing
pulls numpy in since imagehash was dropped in #68, but the pin stays) because
numpy 2.5's stubs use the Python 3.12 `type` statement, which mypy rejects
while `python_version = "3.11"`. The weekly `latest-deps.yml` workflow
ignores the lock and the constraint; a red run means bump the lock or lift
a constraint.

### Releasing

The version lives only in `src/holiday_card/__init__.py` (`__version__`;
`pyproject.toml` reads it via `[tool.hatch.version]`). A release is a tag:

1. Bump `__version__` in `src/holiday_card/__init__.py`.
2. Add a `## vX.Y.Z — "…" — YYYY-MM-DD` section to `RELEASE_NOTES.md`
   (its body becomes the GitHub Release notes).
3. Merge the PR to `main`.
4. `git tag vX.Y.Z && git push --tags`
5. Approve the `pypi` environment when `release.yml` asks.

`release.yml`'s `build` job fails if the tag isn't exactly `v` +
the installed wheel's `--version`, if `RELEASE_NOTES.md` has no section
for the tag, if `twine check --strict` fails, or if the installed wheel
can't render christmas-classic outside the checkout. `publish` uses PyPI
trusted publishing (OIDC, no token, attestations on); `github-release`
attaches `dist/*` to a GitHub Release.

**One-time owner setup (Claude cannot do either):** on PyPI, add a
*pending* trusted publisher for project `holiday-card`: owner
`clostaunau`, repository `holiday-card`, workflow `release.yml`,
environment `pypi`. In the GitHub repo settings, create the `pypi`
environment with required reviewers (and optionally restrict it to
`v*` tags).

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
                                        # every problem as `  - <path>: <message>`, exit 2 if any
holiday-card schema -o docs/template-schema.json   # regenerate the committed JSON Schema

# Per-panel POD output: --export-for emits one file per panel
holiday-card create christmas-classic --export-for moo-a6 -o out/moo-card/
# → out/moo-card/{front,back,inside-left,inside-right}.pdf at A6 trim + bleed,
#   art scaled to fill the trim and cropped (--panel-fit letterbox: fit whole)
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
checkerboard, lowered by the compiler to clip + solid primitives)**, text with left/center/right alignment + Markdown
rich text (paragraphs + **bold** + *italic* + ***bold-italic***)
+ structured letter parts
(salutation / signoff / signature / P.S.), text **`font_style`**
(bold / italic / bold_italic, resolved to the registered variant) and
text **rotation**, **photo images** (PNG/JPEG
only, content-probed; template `source_path` is relative to the YAML
file — absolute, `..` and symlink escapes are load errors, D5) with
circle / rectangle / ellipse / star clip masks, a panel
**`background_image`** (cover-fit over the background rect, bleed
included, under every element, #153), fold lines, identity
or rotation-only group transforms, and **bleed extension** on edges
that touch the page trim (`card.bleed` / `panel.bleed` default to
0.125", capped at the page geometry's bleed: the default `letter`
page has **no bleed** so nothing extends, while the POD targets carry
0.125", D7 / #59). **All 21 shipped templates currently compile
cleanly:**

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
photo `effects` / `frame_style`, text
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
2. For stateful drawing (groups, clipping), maintain a small stack and
   apply group transforms with `Transform.to_matrix()` (conjugated into
   the backend's coordinate system); the formula is in the `Transform`
   docstring.
3. Strict on unknowns: anything you can't handle (e.g. gradient paints
   for the moment) raises `NotImplementedError` with a useful message.
4. Add `tests/integration/test_{name}_backend.py`. **Include
   pixel-correctness checks**, not just structural validity — see the
   `test_png_christmas_classic_has_red_pixel_in_front_panel` test for
   how the PNG suite caught a transform bug the SVG suite missed.
5. Add a column to `tests/conformance/capabilities.py` (extend the
   `Backend` literal, give every case a `match` / `raises` /
   `known_diff` status from the observed results), teach
   `render_backend` in `test_conformance.py` to render it, and
   regenerate `docs/conformance-matrix.md`.
6. (CLI integration) Either expose via the existing `--format` enum on
   `holiday-card create`, or via a new top-level command (like
   `preview` does for PNG).

CMYK output is already shipped as a backend mode rather than a separate
renderer: `IRReportLabRenderer(color_space="cmyk")` (every colour through
one ICC `CMYKConverter`, with a text / stroke / fill role) plus the
pikepdf-based `renderers/pdfx_postprocess.py` produce DeviceCMYK
PDF/X-1a:2003 when `--export-for moo-a6` is used. Beyond the panel's roadmap, speculative
future backends: HTML/Canvas streaming over a websocket for live
template editing; a JSON "render plan" backend for downstream tooling.

## Code style

- Type hints on every function; `mypy --strict` passes
- Pydantic models for domain validation (frozen for IR, mutable for
  Card so messages can be applied) with `validate_assignment=True`;
  use reassignment, not list mutation (`panel.text_elements =
  [*panel.text_elements, t]`, never `.append`), so the validators run
- Docstrings on public APIs; one-line comment max for private helpers
- Measurements in inches in YAML/Python; converted to points once in
  the compiler
- Imports organized by ruff (`I` rule); enforced in CI
- Exception chaining: `raise X from e` everywhere (`B904` is enforced)
- Tests never see `OPENAI_API_KEY` / `OPENROUTER_API_KEY` and cannot open
  non-loopback sockets unless marked `live_ai` (autouse guard in
  `tests/conftest.py`, #143)

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

## Gotchas (rules that bite)

- Tests that hand-place a panel must pass `CompileContext(impose=False)`;
  otherwise imposition moves a `front` panel to the bottom-right (#58).
- `replace(entry, resolutions=…)` on a shipped OpenRouter entry must also
  clear its tier-keyed `--max-cost` bounds (`_UNBOUNDED` in
  `test_ai_assets.py`), or `OpenRouterModel.__post_init__` refuses it (#151).
- Tests that exercise bleed must pass an explicit
  `PageGeometry.us_letter(bleed_in=0.125)`: the default `letter` page has
  no bleed (#59).
- Models validate on assignment: reassign lists, never `.append` /
  `.extend` / item-assign (an AST test scans `generators.py` and
  `card_request.py`, #81).
- Any new `except Exception` in the CLI must let `BrokenPipeError`
  through (`except (typer.Exit, BrokenPipeError): raise`, #92).
- Exit with `ExitCode.*`, never `typer.Exit(<digit>)` (a test greps for
  it, #80). Codes: 0 OK, 1 ERROR, 2 USAGE, 3 CONSENT_REQUIRED,
  4 ENVIRONMENT, 5 RAIL_REFUSED, 6 PROVIDER_REFUSED, 7 PROVIDER_ERROR.
- Goldens are regenerated only on purpose, via their env var
  (`HOLIDAY_CARD_REGEN_LETTER_CONTENT_GOLDEN=1`,
  `HOLIDAY_CARD_REGEN_PDF_ALPHA_GOLDEN=1`); visual baselines only via the
  `visual-baselines` workflow on Ubuntu, and eyeballed before commit.
- PNG text depends on Pillow's raqm (libfribidi); PNG visual baselines
  are Ubuntu/raqm renders (#68).
- Hatch sdist `include` entries are gitignore patterns: anchor them with
  `/` or `README.md` also matches every `.claude/**/README.md` (#86).
- In the OpenRouter transport, read with `read1`, not `read(n)`, or a
  trickling server never hits the deadline (#149). Only
  `core/ai_openrouter.py` may import `urllib.request`; only
  `core/ai_openai.py` may import `openai`, and only function-locally (#143).
- Provider switches use `match` + `assert_never`, so a new `AIProvider`
  member is a mypy error until it is wired everywhere (#146).
- Translucency over anything but a containing solid fill is refused on
  PDF/X targets (moo-a6) (#71).
- An AI asset (marked PNG, or any file with a sibling `.license.yaml`)
  renders only with an intact sidecar and never in a photo slot; the
  checks live in `compiler.embedded_ai_assets` and `fill_photo_slots`,
  both through `ai_provenance.require_sidecar` (#144). Tests bake one with
  `tests/ai_fixtures.bake_fake_ai_asset`.

## Engineering log

Per-PR detail (what changed, why, what was regenerated, which tests
guard it) lives in [`docs/engineering-log.md`](docs/engineering-log.md),
newest first; grep it by issue number. **Add new entries there, not
here**: CLAUDE.md gets at most a one-line pointer, and a new rule of
the "this will bite you" kind goes in Gotchas above. User-facing notes
go in `RELEASE_NOTES.md`.

In flight: the OpenRouter image-provider program (tracker #139); #141,
#142, #143, #144, #145, #146, #147, #148, #149, #150, #151, #152, #153 and #168
have landed (OpenRouter is usable; its default model is provisional until
#140); panel `background_image` is #153 in the log. **Legacy-read deadline (O7):** delete the
`LicenseRecord` `openai_policy_url` reader (`# LEGACY(v1.3.0 sidecar…)`)
in the first release after the one that ships #147.

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
  exactly that narrow shape — see the 2026-06-02 entry in
  `docs/engineering-log.md` and the
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
- **A second AI provider (OpenRouter) was an owner decision** (spec
  `docs/specs/2026-09-30-openrouter-image-provider.md` §2), not a
  re-opening of the panel's verdict: every rail above applies to it
  unchanged.

If you want to evaluate a new feature proposal not covered above,
spin up a fresh panel — the prompts are reproducible. Ask: "spin up
the industry panel to evaluate [proposal]" and the workflow will
fire 6 critic agents + a synthesis moderator.

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
