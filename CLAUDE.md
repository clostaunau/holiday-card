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
                                    # PDF: < 300 PPI warns, < 150 PPI exits 2 (--allow-low-res: proofs only)
holiday-card preview christmas-classic --voice warm             # PNG preview; takes every create content flag
uv run pytest                       # all 2678 tests, mypy-clean, ruff-clean, coverage ≥ 92%
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
- Pillow 10.0+ (PNG backend + image effects)
- Pydantic 2.0+ (domain models + IR)
- Typer 0.9+ (CLI)
- PyYAML 6.0+ (template loading)
- pikepdf 8.0+ (PDF/X-1a post-processing for `--export-for moo-a6`)
- fontTools 4.47+ (`fontTools.subset` only: glyph subsets embedded in SVG output, #76)
- openai 1.0+ (**optional** `[ai]` extra; only `core/ai_openai.py` imports it)

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
    ai_rails.py         # L3 hard category rails (occasion + prompt blocklists)
    ai_provenance.py    # L3 LicenseRecord sidecar + first-use consent gate
    ai_assets.py        # L3 POD-aware sizing + generate orchestration (injectable client)
    ai_openai.py        # L3 OpenAI image-client adapter (only module importing openai)
    images.py           # Template image path containment + PNG/JPEG content probe (D5)
    template_checks.py  # check_template: fonts, bounds, default theme, compile smoke (#57)
    template_schema.py  # template_json_schema: model JSON Schema + AliasChoices names (#57)
                        #   + effective-PPI print check on the IR (#66)
  renderers/
    reportlab_backend.py  # IR → PDF (default; sRGB or CMYK mode)
    reportlab_measurer.py # ReportLabTextMeasurer: pdfmetrics widths/ascent + the font catalog (#75)
    svg_backend.py        # IR → SVG (browser-openable, self-contained: fonts embedded as glyph subsets)
    svg_fonts.py          # fontTools subset → `@font-face` data URI per font_id + GENERIC_FAMILY (#76)
    png_backend.py        # IR → PNG (powers `preview`); clips/dashes/text alpha honoured, bundled TTFs only
    pdfx_postprocess.py   # pikepdf-based PDF/X-1a:2003 upgrade
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
    commands.py         # Typer CLI: create, preview, templates, themes, validate
    exit_codes.py       # ExitCode (0-5) + the root --help epilog (#80)
  utils/
    measurements.py     # inch ↔ point conversions; page constants
    svg_parser.py       # SVG path parser used by the compiler's `_compile_svg_path`
tests/
  unit/                 # Wave 2 core: test_render_ir, test_compiler, test_cli, test_text_fitting,
                        #   test_text_utils, test_models, test_clipping_masks,
                        #   test_gradient_models, test_pattern_models,
                        #   test_svg_models, test_svg_parser,
                        #   test_measurements, test_font_registry
                        # Curation/POD/markdown additions: test_sentiments, test_export_targets,
                        #   test_per_panel, test_markdown, test_render_changed
                        # L3 AI imagery: test_ai_rails, test_ai_provenance, test_ai_assets
                        # SVG font subsets: test_svg_fonts (#76)
                        # Loader: test_templates_loading (extra="forbid", fail-loud keys)
                        # CLI preview / init end to end: test_cli_preview_init (#84)
                        # Hypothesis properties (SVG path + Markdown parsers): test_parsers_properties (#84)
                        # CLI seam: test_card_request (precedence rules 1-18, #78)
                        # PDF/X flattening: test_compiler_flatten (backdrop rule, refusals, IR alpha)
                        # Patterns: test_compiler_patterns (lowering to clip + primitives, #74)
                        # Imposition: test_imposition (slot table, paper-fold oracle,
                        #   panel_placements, stale-coordinate loader check, #58)
    __snapshots__/      # JSON snapshots of compile_card() output per template (16 files)
  integration/          # test_full_generation, test_svg_backend, test_png_backend,
                        #   test_per_panel_output, test_voice_flag, test_md_inside,
                        #   test_png_ir_fixtures (PNG clip/dash/alpha/font IR fixtures, #61),
                        #   test_ai_asset_cli (L3 ai-asset generate subcommand)
  visual/               # Per-panel pixel-ratio gate (#68): all 21 templates × {png, pdf}
                        #   × 4 panels at 144 DPI (test_visual_regression.py); helpers +
                        #   calibrated constants in visual_gate.py, locked by
                        #   test_visual_gate_sensitivity.py. Full-sheet baselines in
                        #   fixtures/reference_cards/{png,pdf}/, generated on Ubuntu CI
                        #   by the visual-baselines workflow
                        #   (scripts/regenerate_visual_baselines.py); eyeball before commit.
  rasterize.py          # Shared pypdfium2 PDF rasterizer (conformance + visual gate)
  conformance/          # Cross-backend conformance (#67, D12): cases.py (53 one-feature
                        #   IR pages), capabilities.py (the pdf/png status matrix),
                        #   conftest.py (resvg-py / pypdfium2 rasterizers + tolerances),
                        #   test_conformance.py (case × backend vs the SVG oracle),
                        #   test_template_text_parity.py (21 templates' text, SVG vs PDF
                        #   per panel ±2 px). The SVG oracle loads only the SVG's own
                        #   embedded font subsets (resvg ignores @font-face).
                        #   docs/conformance-matrix.md is generated from capabilities.py.
LICENSE                 # MIT
scripts/                # Stand-alone helpers used by CI/Actions
                        #   render_changed_templates.py — powers .github/workflows/render-cards.yml
                        #   check_release_version.py — release.yml's tag == __version__ check + notes (#86)
                        #   build_microsite.py — Leapfrog 5 template-gallery generator
                        #   make_placeholder_photo.py — regenerates the CC0 placeholder-photo.jpg
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
uv run pytest                            # All 2678 tests pass (PNG visual gate needs raqm: see tests/visual)
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
circle / rectangle / ellipse / star clip masks, fold lines, identity
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

- **2026-09-29 — Tag-driven PyPI release via trusted publishing; trimmed
  sdist; complete metadata (expert-panel §P15 / D1 / D2, issue #86)**:
  the project had never been published (PyPI 404, no tags, no publish
  workflow) and the version was hand-edited in two places. `pyproject.toml`
  now has `dynamic = ["version"]` + `[tool.hatch.version] path =
  "src/holiday_card/__init__.py"` (the literal `version =` is gone; `uv.lock`
  records the project as dynamic). New `.github/workflows/release.yml`
  (tags `v[0-9]+.[0-9]+.[0-9]+`, plus `pull_request` on its own paths;
  top-level `contents: read`, SHA pins): `build` runs `uv build`, refuses
  root-level `data/ docs/ .claude/ .specify/ .devcontainer/ specs/ output/`
  in the sdist, runs `uvx twine==7.0.0 check --strict`, installs the
  wheel in a clean venv, and on tags only checks `scripts/
  check_release_version.py check "$GITHUB_REF_NAME" <--version>` and that
  `RELEASE_NOTES.md` has a section for the tag, then renders
  christmas-classic (letter + moo-a6) from `$RUNNER_TEMP`; `publish`
  (`environment: pypi`, `permissions: id-token: write`, tag-only) uses
  `pypa/gh-action-pypi-publish` with no `password`; `github-release`
  (`contents: write`, tag-only) runs `gh release create --verify-tag
  --notes-file` with the notes from `check_release_version.py notes`. On
  a PR only `build` runs. `[tool.hatch.build.targets.sdist] include` is
  root-anchored (`/src/`, `/tests/`, `/LICENSE`, `/README.md`,
  `/RELEASE_NOTES.md`, `/pyproject.toml`, `/uv.lock`): **hatch treats
  them as gitignore patterns, so an unanchored `README.md` also pulls
  in every `.claude/**/README.md`**. Measured sdist 11.1 → 10.1 MB
  (fonts, the ICC profile and the visual baselines dominate; the gate is
  the exclusion list). Metadata: `authors` = Chris Lostaunau (no email),
  `[project.urls]` (Homepage / Source / Issues / Changelog /
  Documentation), a 3.13 classifier, no `License ::` classifier next to
  PEP 639 `license = "MIT"`, `license-files` (root LICENSE, Liberation
  LICENSE, the six curated `*-LICENSE.txt`, the ICC NOTICE), and
  `openai>=1.0,<4` (the lock resolves 3.19.2; the AI tests pass with the
  `ai` extra installed). `__author__` matches. Wheel METADATA is still
  `Version: 1.3.0`. Guarded by `tests/unit/test_packaging_metadata.py`
  (version single-sourced, `importlib.metadata.version == __version__`,
  classifiers, URLs, license files, openai cap, sdist include list
  anchored and clutter-free, release.yml triggers / permissions / OIDC /
  no password / tag gating, the tag check where `v1.3.1` vs `1.3.0` exits
  1, notes extraction) and, via `test_workflow_policy.py`, the #85 pins /
  permissions / no-`${{`-in-`run:` rules. Tests 2642 → 2678. `requires = ["hatchling>=1.27"]` (PEP 639).

- **2026-09-29 — CI hardening: least-privilege tokens, SHA-pinned actions,
  Dependabot, pip-audit, fork-PR guard (expert-panel §P15 / D2, issue #85)**:
  `ci.yml` and `latest-deps.yml` had no `permissions:` and every workflow
  used mutable tags. Now `ci.yml` / `latest-deps.yml` /
  `visual-baselines.yml` are top-level `contents: read` (render-cards and
  microsite keep their existing scopes) and every `uses:` in
  `.github/workflows/` is a 40-hex commit SHA with a `# vX.Y.Z` comment
  (each major tag resolved to its latest patch, so no behaviour changed).
  Every `actions/checkout` sets `persist-credentials: false`. New CI job
  `audit` (not in `build`'s `needs`, so the job graph is unchanged):
  `uv export --frozen --all-extras --no-emit-project` of `uv.lock` →
  `uvx pip-audit==2.10.1 --disable-pip --require-hashes --strict`; a known
  vulnerability fails it, and a suppression must be `--ignore-vuln <ID>`
  with a `#` justification on the same line. `latest-deps.yml` runs the
  same audit weekly, because new advisories land against an unchanged
  lock. New `.github/dependabot.yml`: `github-actions` (all actions in one
  group) and `uv` (minor + patch grouped), both weekly at `/`; it updates
  `uv.lock`, not the floors (D2). `render-cards.yml` stays on
  `pull_request` (never `_target`, spec §4); the two `peter-evans/` steps
  also require `github.event.pull_request.head.repo.full_name ==
  github.repository`, and a fork PR instead appends `comment-body.md` to
  `$GITHUB_STEP_SUMMARY`, so the read-only fork token no longer turns the
  check red with a 403. No `run:` script contains `${{ … }}` any more:
  values go through step `env:` (`BASE_REF`, `COUNT`, `RUN_NUMBER`,
  `RUN_URL`, `HEAD_SHA`, visual-baselines' `BACKEND`). The pre-commit
  `check-added-large-files` keeps `--maxkb=500` and excludes
  `^src/holiday_card/data/(fonts|icc)/` (the 3.4 MB ICC profile and 1.2 MB
  Cormorant). Guarded by `tests/unit/test_workflow_policy.py` (every
  workflow: SHA pins + version comments, a `permissions` mapping and no
  `write-all`, no `${{` in `run:`, credential-less checkouts; render-cards
  trigger, fork guard and summary fallback; the pinned strict audit in CI
  and latest-deps; justified suppressions; Dependabot ecosystems / grouping;
  the large-file exclude). Tests 2606 → 2642.

- **2026-09-29 — Branch-coverage floor of 92%; `preview` / `init`,
  shrink-to-fit and parser-property tests; a live fail-loud watchdog
  (expert-panel §P12 / D4 / D17, issue #84)**: coverage was measured in
  CI but never enforced. `[tool.coverage.report]` now has `fail_under =
  92` (the measured TOTAL, 92.20% branch coverage, rounded down; every CI
  leg measured the same) and `show_missing = true`, so the CI `pytest
  --cov` step fails below it with `FAIL Required test coverage`. Raise the
  floor when coverage rises; never lower it to pass a PR. New
  `tests/unit/test_cli_preview_init.py`: `preview` writes an `8.5·dpi ×
  11·dpi` PNG, a missing template exits 2 and writes nothing, `.png` is
  appended, voice + letter flags work, `--open` / `--no-open` and
  `_open_in_default_viewer` per platform with `subprocess.run` /
  `os.startfile` patched (plus the failure message); `init` round-trips
  through `load_template_from_file` with `check_template` clean, honours
  `--fold-type` and `--output`. `test_text_fitting.py` gains a half-em
  `HalfEmMeasurer`: the wrap strategy's binary search returns the largest
  size that fits (re-measured at `size` and `size + 1`, and equal to a
  brute-force search), never goes below `min_font_size`, and
  `apply_shrink_strategy` truncates maximally at the floor. First
  `hypothesis` use, `tests/unit/test_parsers_properties.py`
  (`max_examples=200, deadline=None`, < 1 s): generated
  `M/L/H/V/C/S/Q/T/Z` paths (abs + rel) round-trip, arbitrary text either
  parses or raises `ValueError` for `SVGPathParser.parse` and
  `parse_markdown`, plain lines round-trip as unstyled runs, and
  `***x***` is one bold-italic run. **Found by it:** `parse("Z0")` raised
  `ZeroDivisionError` (`len(params) % 0` for a zero-arity command); a
  parameter on `Z`/`z` is now the same arity `ValueError` as any other
  command. The watchdog `test_unsupported_features_raise_loudly` was an
  empty parametrize (the suite's one skip); it now adds an absolute and a
  relative SVG arc to christmas-classic and requires
  `UnsupportedFeatureError`. `SUPPORTED_REJECTING_TEMPLATES` is gone.
  Not done here: `per_panel._scale_shape` no longer exists (#73), so it
  gets no tests (D17); `tests/performance_validation.py` was already
  deleted by #83. Tests 2572 → 2606. Coverage: `cli/commands.py` 83 →
  87%, `core/text_fitting.py` 76 → 92%, `utils/svg_parser.py` 92 → 98%.

- **2026-09-29 — Dead modules, dead APIs and stale comments deleted
  (expert-panel §P15 / D17, issue #83)**: Removed, with no importers
  anywhere: `core/validators.py`, `utils/gradient_utils.py`,
  `renderers/image_effects.py` (the `ImageEffects` *model* stays; the
  compiler refuses it), `utils/validators.py` (every function left after
  #65 was unused, including `validate_dpi`; #66 owns the real PPI check)
  and the uncollected `tests/performance_validation.py` (it wrote
  `/tmp/perf_test` at import). Removed APIs: `TextElement.
  get_adjustment_result` / `set_adjustment_result` / `_adjustment_applied`
  (`AdjustmentResult` stays; `text_fitting` uses it), `CardGenerator.
  generate_pdf` and `create_and_generate` (use `create_card(...)` then
  `generate(card, out)`; the 9 `test_full_generation.py` callers were
  migrated). Compiler comments no longer cite the deleted
  `reportlab_renderer.py` / `shape_renderer.py`, the `_ = SVGCommand`
  import silencer is gone, and `_compile_image`'s docstring no longer
  lists heart / svg_path clip masks (`ClipMask` never had them). Tests:
  2587 → 2572 (−20 `test_validators.py`, −1 adjustment tracking, −2
  `test_core_purity` cases for `core/validators.py`, +8 guard cases).
  Guarded by `tests/unit/test_no_dead_modules.py` (the four modules raise
  `ModuleNotFoundError`; the four APIs are absent).

- **2026-09-29 — PNG backend: anti-aliased coverage masks, centred
  strokes, vectorized gradients, bbox-sized layers (expert-panel §P6 /
  D12 / D4 / D17, issue #77)**: `preview` drew every edge aliased,
  painted strokes inside the geometry (Pillow `outline=`) at whole-pixel
  widths (min 1), filled gradients pixel by pixel in Python and gave every
  translucent or clipped draw its own page-sized RGBA layer. Now every
  fill, stroke and clip is a per-shape `"L"` mask from
  `_coverage_mask(geom, bbox_px, *, stroke_width_px=None, dash=())`,
  drawn at `PNGRenderer.SUPERSAMPLE = 4`× inside the shape's pixel box and
  `reduce`d. Each supersample is painted when its centre is inside:
  rects / rounded rects / ellipses via `_pixel_span`, polygons and paths
  via the new nonzero scanline filler `_scan_fill` (Pillow's polygon
  filler floors vertices and fills both ends, a ¼ px bias per edge at 4×;
  a path is now one nonzero fill over all subpaths, as in PDF/SVG).
  Strokes: rect / circle / ellipse = the shape grown by `w/2` minus it
  shrunk by `w/2` (exact, fractional widths); polygons, polylines, paths
  and dashes = `_stroke_polygons` (a quad per segment plus a miter join,
  bevel past SVG's limit of 4, butt caps). Neither PDF nor SVG sets a
  join or cap, so a `line_cap` other than `butt` now raises
  `NotImplementedError` (D4 / D12; the compiler only emits `butt`).
  Bezier flattening scales with the control polygon (≥ 16, one sample per
  4 px, ≤ 512). The colour composites through the mask on a layer the
  size of that box (`_paint_mask` → `_composite(layer, dest, alpha)`,
  which crops the clip mask and the canvas overlap); text uses its ink box
  (`font.getbbox`), images their own size. Fold lines are a 0.5 pt stroke
  like PDF/SVG (were 1 px). Gradients: `_gradient_t` builds `255·t` as an
  `"L"` image with `ImageMath.lambda_eval` over pixel-centre ramps
  (clamped, rounded) and `_draw_shape_with_complex_fill` maps it through
  256-entry `_interp_stops` LUTs per channel (±1/255 of the per-pixel
  reference, now sampled at pixel centres; 1000×1000 px in ~50 ms; paths
  can take gradients now). A group overlay is transformed over its
  content's box only (`getbbox` + the forward `_pixel_affine`), not the
  page. `PNGRenderer(dpi, antialias=True)`; `antialias=False` samples once
  per pixel (every pixel in or out, strokes ≥ 1 px) for exact-pixel tests.
  Deleted (D17): `_draw_in_layer` / `_in_layer`, `_draw_text_in_layer`,
  `_shape_needs_alpha_compositing`, `_geom_mask`, `_draw_geom_mask`,
  `_geom_bbox_px`, `_render_complex_fill_into`, `_draw_path`,
  `_stroke_outline`, `_draw_dashed_polyline`, `_inverse_pixel_affine`,
  `self._draw`. Timing at 300 DPI (render only, macOS): winter-sky 2.36 →
  0.42 s, holiday-masterpiece 4.96 → 0.67 s, festive-stripes 1.03 →
  0.99 s; `preview christmas-winter-sky --dpi 300` 2.80 → ~1 s wall
  and lower peak RSS. Conformance: PNG tolerance 2.0% → **1.0%**
  (`TOLERANCE` moved to `capabilities.py` and printed in
  `docs/conformance-matrix.md`), `stroke_rect_6pt` PNG flipped
  `known_diff` → `match` (7.35% → 0%); every stroke / edge / clip /
  gradient / pattern case is now ≤ 0.05% (was up to 1.23%); the worst PNG
  case is `group_square_scale2_*` at 0.75% (bicubic overlay resampling).
  The 15 PNG visual panels that moved were regenerated by the
  `visual-baselines` workflow and eyeballed against the PDF render (all
  but three moved closer to it; those three are half-pixel stripe and
  checker edges, now exact area coverage as in resvg, where pdfium
  snaps). PDF baselines and compile snapshots are unchanged. Guarded by
  the #77 block in `tests/integration/test_png_backend.py` (centred 10 pt
  stroke, 0.5 pt partial coverage, ≥ 3 AA levels / exactly 2 with
  `antialias=False`, centre-rule polygon, 4 pt line rows, miter corner,
  `line_cap` refusal, bbox-sized allocations via an `Image.new` spy,
  content-box group transform, short Bezier chords),
  `tests/unit/test_png_gradients.py` (linear / radial vs the reference at
  5 points, < 0.5 s for 1000×1000, no `for y in range(h)`) and
  `test_png_draws_pattern_primitives_on_one_layer`.

- **2026-09-29 — Core measures text through an injected `TextMeasurer`;
  no core module imports ReportLab or the renderers (expert-panel §P13 /
  §4 / D4 / D17, issue #75)**: the compiler measured through a throwaway
  ReportLab `Canvas` and imported `renderers.font_registry`, `flatten`
  and `template_checks` did the same, and `generators.py` imported all
  three backends at module level, so the decision layer depended on the
  PDF backend and tests could not inject deterministic metrics. New
  stdlib-only `core/text_measure.py`: `TextMeasurer` Protocol
  (`string_width(text, font_id, size_pt)`, `ascent_descent(font_id,
  size_pt)` for the #73 safe-zone check, `known_font_ids()` for the #60
  font refusal and `validate`'s font check; the issue named only
  `string_width`, but those two call sites landed after it was written),
  `set_default_text_measurer(factory)` and `default_text_measurer()`
  (`RuntimeError("no TextMeasurer registered…")` when unset, D4). New
  `renderers/reportlab_measurer.ReportLabTextMeasurer` registers the
  fonts and calls `pdfmetrics.stringWidth` / `getAscentDescent` on the IR
  `font_id`, exactly what `Canvas.stringWidth` did. `holiday_card/
  __init__.py` is the composition root: it registers a factory that
  imports that module on first call, so `import holiday_card` loads no
  ReportLab. `CompileContext.measurer: TextMeasurer | None`; `compile_card`
  uses `ctx.measurer or default_text_measurer()`; `_make_measurer` is
  deleted (D17). `text_utils` / `text_fitting` take a `measurer:
  TextMeasurer` where they took a canvas (same positions).
  `Flattener(measurer=None)` / `flatten_transparency(..., measurer=None)`
  measure text boxes on the IR `font_id` (it used the resolved Liberation
  name, up to 0.03% wider; no flatten decision changed).
  `generators.Renderer` is now a `runtime_checkable` Protocol
  (`file_extension`, `color_space`, `render`); the default PDF renderer is
  built by `_pdf_renderer()` with a function-local import, and the CMYK
  swap checks `file_extension == ".pdf"` instead of `isinstance`. SVG and
  PNG backends gained `color_space = "srgb"`. A regression oracle hashed
  the compiled IR of all 21 templates × 4 content modes (default, long,
  Markdown, structured letter) × {letter, letter + flatten, per-panel-pdf,
  moo-a6 fill, moo-a6 letterbox} × every panel (1176 entries) before and
  after: byte-identical. Snapshots and visual baselines unchanged; the
  christmas-classic PDF rasterizes pixel-identically to `main`. Guarded
  by `tests/unit/test_core_purity.py` (AST scan of every `core/*.py`,
  nested imports included, and subprocess checks that importing the
  package, the compiler and every core module loads neither `reportlab`
  nor `holiday_card.renderers`), `tests/unit/test_text_measure.py` (a
  `FixedWidthMeasurer` drives wrap points, known fonts, safe-zone and
  flatten boxes; the unregistered default raises),
  `tests/unit/test_reportlab_measurer.py` (== `Canvas.stringWidth` for
  every `FONT_MAP` + `CURATED_FONTS` id at 3 sizes) and
  `tests/unit/test_generators_renderer.py` (every backend satisfies the
  Protocol; a Protocol-only renderer generates; the CMYK swap).

- **2026-09-29 — SVG output embeds glyph subsets of the fonts the
  compiler measured (expert-panel §P13 / D4 / D12, issue #76)**: the SVG
  backend wrote a bare `font-family="Caveat"` with no font data, so each
  viewer substituted its own font (33% wider than Caveat at 18 pt) and the
  text overflowed the boxes the compiler wrapped with ReportLab. New
  `renderers/svg_fonts.py`: `subset_font_bytes(ttf_path, text, *,
  family_name)` runs `fontTools.subset` with fixed options (the chars
  drawn plus `.notdef`; no GSUB / GPOS / GDEF / kern, because ReportLab
  measures unkerned advances; no hinting; source `head.modified` kept, so
  output is byte-stable) and renames the subset to its CSS family
  `hc-<font_id>`, keeping the copyright / license name records. That
  rename is how non-browser tools find it: resvg, rsvg and Inkscape ignore
  `@font-face` and match the font's own name table. **Variation tables
  (`fvar` / `gvar` / `avar` / `HVAR` / `MVAR` / `STAT` …) are dropped**,
  so a variable master is embedded as its static default instance. The
  issue assumed viewers render the default axes, but browsers and resvg
  apply `font-optical-sizing: auto`, which drew Inter (`opsz` 14 by
  default) at `opsz` 32 for 32 pt text, visibly narrower than the PDF.
  `font_face_css(font_id, ttf_path, text)` gives the rule, `css_family` /
  `svg_font_family` the names, and `GENERIC_FAMILY` maps every font_id to
  serif / sans-serif / cursive / monospace. `SVGRenderer` collects the
  chars per font_id and at `EndPage` inserts one `<style>` with one
  `@font-face { … url(data:font/ttf;base64,…) format("truetype"); }` per
  font_id (sorted), preceded by an XML comment naming each face and the
  SIL OFL 1.1. `<text>` now says `font-family="'hc-Caveat', cursive"`. A
  font_id with no TTF (`ttf_path_for` → `None`) raises `NotImplementedError
  ("SVG backend cannot embed font 'NoSuchFont'")` at the `DrawText`. The
  christmas-classic SVG is 12.9 KB (11 KB of base64 font data) and
  byte-identical across runs. New dependency `fonttools>=4.47` (in
  `uv.lock`; mypy override `fontTools.*`). Conformance: the SVG rasterizer
  pulls the embedded subsets out of the SVG and passes them to resvg as
  `font_files`, with no `font_dirs`, so the oracle draws text only with
  what the file carries. `text_curated_family` (known_diff #76) became 7
  `text_family_*` cases (Cormorant, Cormorant-Italic, PlayfairDisplay,
  Inter, Caveat, Comfortaa, Helvetica), all `match` on PDF and PNG;
  `docs/conformance-matrix.md` regenerated. **OFL note:** Lato, Comfortaa,
  Playfair Display and Liberation declare Reserved Font Names (the issue
  said none do); the embedding is treated like the PDF's per-document
  subsets (`ABCDEF+Lato`), with the `hc-` tag and the original copyright /
  license records kept. Snapshots and visual baselines are unchanged (both
  are PDF / PNG). Guarded by `tests/unit/test_svg_fonts.py`, the `#76`
  block in `tests/integration/test_svg_backend.py` (every `<text>` names an
  embedded face + generic, one `@font-face` per family, each cmap covers its
  chars, the license comment, byte stability, the refusal, and
  christmas-classic advances within 0.5% of `pdfmetrics.stringWidth`) and
  `tests/conformance/test_template_text_parity.py` (all 21 templates' text,
  SVG vs PDF per panel, ±2 px; 21 of 21 fail on the old backend).

- **2026-09-29 — Pattern fills are lowered by the compiler; the three
  backend tilers are deleted (expert-panel §P13 / D13, issue #74)**: PDF,
  SVG and PNG each tiled `PatternPaint` differently. On festive-stripes
  the 90° ribbon was mostly missing in PNG and mostly solid in PDF, 45°
  stripes lost their corners, and SVG grid / checker used half the PDF
  spacing. New `compiler._lower_pattern_fill(fill, geometry, bbox_pts,
  stroke, opacity, *, where=)` emits `BeginClip(shape)` →
  `BeginGroup(Transform(pivot = bbox centre, rotate_deg), opacity =
  shape opacity)` → a `colors[0]` background → `colors[1]` primitives →
  `EndGroup` → `EndClip` → the stroke (fill `None`), if any. The group is
  always emitted, so opacity composites once. Semantics (docstring):
  `period = spacing × scale` in pt; tiles hang from the bbox top-left;
  stripes are one full-width band `period/2` tall per row, dots a circle
  of radius `period/4` at each tile centre, grid one 1 pt vertical and
  one horizontal line per tile, checkerboard `period/2` squares at the
  tile's top-left and bottom-right; a rotated pattern covers the bbox's
  circumscribed square. A single-colour pattern is just the background.
  Period < 2 pt, or > 20 000 primitives, raises `UnsupportedFeatureError`
  naming the shape (`Rectangle id 'ribbon'`) and the numbers. Rectangle,
  circle, triangle, star and SVG-path shapes route through `_draw_filled`
  (the SVG path's bbox is its transformed control-point hull); lines take
  `_resolve_stroke` only. Deleted (D17): `PatternPaint` (class, `PaintU`
  member, `__all__`), `_pattern_to_paint`, the PDF `_draw_pattern_tile`,
  the SVG `_register_pattern`, the PNG `_render_pattern_into` and their
  dispatch branches, and the flattener's pattern blending. Consequences:
  CMYK needs no pattern code (primitives are `SolidPaint`); a
  translucent pattern on a PDF/X target is refused by the flattener (its
  background and primitives overlap inside a translucent group), and
  `BeginGroup.opacity < 1` still raises in PDF / PNG. The flattener drops
  rotated bands its clip box culls entirely. **PNG changes found on the
  way:** (1) an identity `BeginGroup` opened under a clip now gets its own
  overlay, so a pattern's primitives draw directly and are clipped once
  (festive-stripes went 0.11 s → 2.0 s with one canvas-sized layer per
  clipped primitive; now 0.24 s); (2) Pillow's box end is inclusive, so a
  fill-only rect drew one pixel too wide (a 2 px grid line was 3 px):
  unstroked rects now fill the pixels whose centres are inside
  (`_pixel_span`; abutting checker cells get exactly one owner per
  pixel), and fill-only circles / ellipses inset their box by 0.5 px.
  Measured against the SVG oracle, PNG moved closer on every template it
  changed. Both are interim until #77's coverage masks. Conformance: the
  4 `pattern_*` cases became 12 (`pattern_{kind}_{0,45,90}`, built with
  `_lower_pattern_fill`), all `match` on PDF and PNG;
  `docs/conformance-matrix.md` regenerated. Regenerated on purpose: the
  festive-stripes compile snapshot, the festive-stripes and
  holiday-masterpiece entries of both PDF goldens, and the visual
  baselines for festive-stripes and holiday-masterpiece (PNG + PDF) plus
  10 other PNG sheets whose rect / disc edges moved by a pixel
  (0.005–0.56% of a panel; menorah, balloons and artist were over the
  gate), generated by the `visual-baselines` workflow and eyeballed. Guarded by
  `tests/unit/test_compiler_patterns.py`, `test_pattern_is_not_an_ir_paint`
  in `test_render_ir.py`, `TestFestiveStripesRibbon` /
  `test_png_draws_pattern_primitives_on_one_layer` in
  `test_gradients_patterns.py`,
  `test_png_fill_only_rect_covers_exactly_its_pixels` in
  `test_png_backend.py`, `test_translucent_pattern_is_refused` in
  `test_compiler_flatten.py` and the pattern conformance cases.

- **2026-09-29 — `validate` checks fonts, bounds, theme and compiles;
  `holiday-card schema`; template-authoring guide (expert-panel §P3 / D3 /
  D4, issue #57)**: `validate` only loaded the YAML, so an unknown font or
  an element at `x: 99` said `Template valid` and failed at `create`. New
  pure `core/template_checks.py`: `check_template(template) ->
  list[TemplateProblem(path, message)]` reports every problem: a
  `font_family` outside `known_font_ids()` (unless `font_file` is set), a
  text anchor, shape bbox (rect / circle / star outer radius / triangle /
  line unrotated; SVG path from `_compile_svg_path`, rotation included) or
  image rect outside `[0, width] × [0, height]` (1e-6 in slack), a
  `default_theme_id` that `load_theme` can't find, and a compile smoke
  (`create_card_from_template` + `compile_card`; `UnsupportedFeatureError`
  / `KeyError` / `ValueError` → a `<compile>` problem; an `UnknownFontError`
  already reported by the font check is not repeated). Paths read
  `panels[front].text_elements[greeting].font_family`, using the element
  `id` only when the YAML set one (else the index). `TemplateLoadError`
  gained `.problems: list[(path, message)]`, and loader locations are now
  `panels[0].text_elements[0].colr` (was dotted `panels.0.…`) in the
  message too; an unreadable file is one `<file>` problem. `validate`
  prints `Template invalid: <ref>` plus `  - <path>: <message>` lines on
  stdout and exits 2 (was a one-line stderr message), or the old summary.
  New `holiday-card schema [-o PATH]` prints
  `core/template_schema.render_template_schema()`: `Template.
  model_json_schema()` with a draft 2020-12 `$schema`, sorted, indent 2,
  plus every `AliasChoices` spelling as a property (a required field
  needs any one, via `allOf`/`anyOf`), because Pydantic lists only the
  first and the shipped `x1`/`y1` lines failed `additionalProperties:
  false`. Committed as `docs/template-schema.json`; regenerate with
  `holiday-card schema -o docs/template-schema.json`. `jsonschema` joins
  the dev extras. New `docs/template-authoring.md` (linked from README);
  `specs/004-*/contracts/yaml-schema.md` is marked superseded. **Found by
  the theme check:** christmas-geometric (`christmas-earth-tones`) and
  christmas-metallic-ornaments (`christmas-gold-burgundy`) named themes
  that never existed; both now say `christmas-gold` (the id only reaches
  PDF/SVG metadata, so 2 compile snapshots changed in `theme_id` and
  nothing else). `create_card_from_template` (#78) stands in for the
  issue's `card_from_template`. Guarded by
  `tests/unit/test_template_checks.py` (every check, all at once, all 21
  templates clean), `TestValidateCommand` / `TestSchemaCommand` in
  `test_cli.py`, `tests/unit/test_template_schema.py` (drift guard; every
  shipped YAML validates against the committed JSON; alias spellings) and
  `tests/unit/test_template_authoring_doc.py` (every YAML example in the
  guide passes `check_template`, the font table is complete).

- **2026-09-29 — BREAKING: `-o` means `--output` everywhere; listing
  tables lead with the ID; grouped help; documented exit codes
  (expert-panel §P14 / D16, issue #80)**: `templates`, `themes` and
  `init` used `-o` for `--occasion` while `create`, `preview` and
  `ai-asset generate` used it for output. Now `--occasion` has **no short
  flag** (`templates -o christmas` is `No such option: -o`, exit 2),
  `init -o DIR` is `--output`, and `ai-asset generate --out` is renamed
  `--output` (no alias, D17). The `templates` table is `ID OCCASION FOLD
  [SOURCE] NAME` (SOURCE only when a user / env layer contributes, #79),
  `themes` is `ID OCCASION NAME`; both are sorted by `(occasion, id)`,
  sized to their widest cell with nothing truncated, and drop the
  description (`--format json|yaml` payloads are unchanged).
  `--format` is a `ListFormat` `StrEnum`, so `--format xml` is a click
  usage error (exit 2) instead of a silent table. `create` / `preview`
  options sit in Rich panels Content / Inside letter / Layout / Output
  (panel order follows parameter order, so the signatures were
  reordered; `--panel-fit` is Layout, `--allow-low-res` Output).
  New `cli/exit_codes.py`: `ExitCode` (OK 0, ERROR 1, USAGE 2,
  CONSENT_REQUIRED 3, ENVIRONMENT 4, RAIL_REFUSED 5; numbers unchanged)
  and `EXIT_CODES_HELP`, the root `--help` epilog. Every `typer.Exit` in
  `commands.py` uses `ExitCode.*`; a test greps for `typer.Exit(<digit>`.
  README gains an "Exit codes" table. Guarded by `TestShortFlags`,
  `TestListingTables` (every listed id `create`s, all 21),
  `TestHelpPanels` and `TestExitCodes` in `tests/unit/test_cli.py`.

- **2026-09-29 — Template paths and a layered template search path;
  `init` → `create` works (expert-panel §P14 / D1 / D15, issue #79)**:
  `holiday-card init foo` wrote `templates/generic/foo.yaml` under the
  cwd, which nothing searched, so the suggested `create foo` failed.
  `create ./my-template.yaml` (README example 5) failed too, because
  `load_template` never treated its argument as a path. New in
  `core/templates.py`: `user_templates_dir()`
  (`$XDG_DATA_HOME/holiday-card/templates`, default
  `~/.local/share/…`; an empty `XDG_DATA_HOME` counts as unset),
  `template_search_path() -> [(source, dir)]` (each `os.pathsep` entry of
  `HOLIDAY_CARD_TEMPLATES` as `"env"`, then `"user"`, then `"builtin"`;
  missing dirs are skipped like `PATH`), `is_template_path(ref)` (ends
  `.yaml`/`.yml`, contains `/` or `os.sep`, or starts with `.`/`~`) and
  `resolve_template(ref, *, templates_dir=None) -> (Template, abs path)`.
  A path ref loads the file directly; a missing file raises
  `TemplateNotFoundError("Template not found: <ref>")`. An id ref is
  looked up by `id:` across all layers, then by file stem across all
  layers, so an id match in a later layer beats a stem match in an
  earlier one. `templates_dir=` makes that one dir the only layer (source
  `"dir"`). Layers are walked recursively for `*.yaml`/`*.yml`.
  `discover_templates()` adds `source` and, for a template whose id
  appears in a later layer too, `shadows` (the first one wins and is
  listed once). It reads `occasion` from the YAML, not the directory, and
  skips non-mapping YAML. `load_template(id, dir)` is a thin wrapper;
  `get_templates_dir` is deleted (D17). **`HOLIDAY_CARD_TEMPLATES` no
  longer replaces the bundled templates**: it is gone from
  `data_paths.ENV_OVERRIDES`, so `data_path("templates")` is always the
  bundled dir (themes and sentiments still replace). `templates` with no
  filter exits 1 when no template has `source == "builtin"`.
  Consumers: `build_card` calls `resolve_template` (so `--voice` on a
  path-loaded template uses its own `occasion`), `validate` too (its
  path special case is deleted; it now also prints `Path:`), and
  `scripts/build_microsite.py` passes the bundled dir explicitly, so a
  user's or an env layer's templates never reach the gallery.
  `init`: defaults to `user_templates_dir()/<occasion>/`, refuses an
  `--occasion` outside `OccasionType` (exit 2, lists them), refuses to
  overwrite without the new `--force` (exit 2), and prints `holiday-card
  create <name>` only when `resolve_template(name)` finds the new file,
  otherwise the (shell-quoted) path. `tests/conftest.py` points
  `XDG_DATA_HOME` at a fresh temp dir in `pytest_configure`, so the suite
  never reads the real user layer. Guarded by the search-path / discover /
  resolve classes in `tests/unit/test_templates.py`,
  `TestInitThenCreate` / `TestTemplatePaths` in `test_cli.py`,
  `test_templates_env_var_does_not_replace_the_bundled_dir` in
  `test_data_paths.py` and
  `test_gallery_shows_only_the_builtin_templates` in
  `test_microsite_build.py`.

- **2026-09-29 — Print targets warn below 300 and refuse below 150
  effective PPI (expert-panel §P8 / D4 / D8, issue #66)**: nothing checked
  photo resolution, so `create -i thumb.jpg --export-for moo-a6` shipped a
  soft print silently (the 400 px `tests/fixtures/sample_photo.jpg` in
  family-photo's 2.95" slot is 136 PPI). `core/images.py` gains
  `RECOMMENDED_PRINT_PPI = 300`, `MIN_PRINT_PPI = MIN_DPI` (150;
  `utils/measurements.MIN_DPI` stays as the one value), the frozen
  `ResolutionFinding(source, ppi, level, needed_width_px,
  needed_height_px)` (pixels needed at 300 PPI at the placed size),
  `effective_ppi(ref, group_scale=1.0)` (`preserve_aspect` "meet" → `max`
  of the axis PPIs, stretch → `min`; rotation ignored),
  `check_print_resolution(commands, *, warn_below=300, fail_below=150)`
  (a `BeginGroup` stack of `sqrt(|scale_x·scale_y|)`, so the #73 fill
  scale counts: 136 → 128 PPI under moo-a6; fail beats warn),
  `describe_finding`, `LowResolutionWarning(UserWarning)` and
  `LowResolutionImageError(ValueError)` (carries `.findings`).
  `ExportTarget.checks_print_resolution: bool = True` (all three targets).
  `CardGenerator.generate(..., allow_low_res: bool = False)` checks the
  compiled IR in `_generate_imposition` / `_generate_per_panel` (all
  panels, before any file or directory is written) only when
  `renderer.file_extension == ".pdf"` and the target opts in: any `fail`
  raises `LowResolutionImageError` unless `allow_low_res`, and every
  remaining finding (deduplicated by message) is a
  `warnings.warn(..., LowResolutionWarning)`, the same channel as
  `SafeZoneWarning`. SVG, PNG and `preview` are never checked. CLI
  `create --allow-low-res` (`CardRequest.allow_low_res`) is for proofs
  only; warnings print as `Warning: me.jpg is 237 PPI at its placed size
  (300 recommended; need ≥ 885×885 px)` and the error maps to exit 2 via
  the existing `ValueError` branch. The shipped placeholders are ≥ 375 PPI
  on letter. Guarded by `tests/unit/test_images_resolution.py`,
  `TestPrintResolutionGate` in `test_image_rendering.py` (CLI exit codes,
  no file written, moo-a6 fill scale, SVG skip, target opt-out) and
  `TestShippedTemplatesPrintResolution` in `test_full_generation.py`
  (21 templates × 3 targets, zero findings).

- **2026-09-29 — moo-a6 fills the A6 trim via one compiler scale group;
  letterbox is opt-in (expert-panel §P11 / §P8 / D8, issue #73)**: MOO A6
  panels had ~0.24" of white paper top and bottom, because
  `per_panel.prepare_scaled_panel` scaled by `min(4.13/4.25, 5.83/5.5)`
  and centred the result, and bleed only extended edges that touched the
  trim. Its per-type rescaling also skipped images, SVGPath `x`/`y`,
  radial-gradient geometry, strokes, borders, pattern spacing and
  letter/rich text sizes, and it rounded `font_size`. `ExportTarget.
  scale_panels_to_fit` is replaced by `panel_fit: Literal["native",
  "fill", "letterbox"]` (`PanelFit`): `per-panel-pdf` is `native` and
  `moo-a6` is `fill`, with the description and docstring rewritten.
  `CompileContext.panel_fit` makes `compile_card` require exactly one
  panel at the origin with no rotation (otherwise `ValueError`). It then
  replaces that panel's group transform with `Transform(scale = s,
  offset = centre)`, pivot (0,0), where `s = max(tw/pw, th/ph)` for fill
  (1.0600 letter→A6) and `min` for letterbox (0.9718). Every element,
  photos included, scales inside that one group, so no per-type code is
  left. `_fitted_bleed_rect` extends the background by `bleed / s` in the
  native frame on every edge the scaled panel reaches: all four under
  fill, left/right only under letterbox. `_warn_outside_safe_zone`
  maps each `DrawText` run's measured box (advance width ×
  ascent/descent, through the fit group and any text-rotation group) and
  emits `SafeZoneWarning(UserWarning)` naming
  `<template>/<panel>/<element>` and the overshoot in inches when the
  box leaves the ArtBox. It fires only for `panel_fit != "native"`. The
  CLI prints each warning as `Warning: …` on stderr and exits 0. Six
  shipped templates warn under moo-a6: the classic, festive-stripes,
  modern, winter-sky and mothers-day greetings (0.005–0.17"), and
  photo-ornament's inside message (1.5"). The last is a template bug: it
  is centre-aligned at x=0.5", so it hangs off the panel on every target.
  New `create --panel-fit fill|letterbox` goes through
  `CardRequest.panel_fit`. On a native target it is refused with exit 2
  (D4). Otherwise `plan_output` returns `replace(target,
  panel_fit=…)`. Deleted (D17): `prepare_scaled_panel`, `_scale_text`,
  `_scale_shape` and `build_per_panel_card`'s `target` argument; the
  panel always stays native. MediaBox is unchanged at 315.36×437.76 pt.
  Compile snapshots and visual baselines are unchanged (both are
  letter-only). Guarded by `TestPanelFit` / `TestSafeZoneWarning` in
  `test_compiler.py`, `TestMooA6FillsTrim` (PNG + pdfium edge pixels on
  all 4 panels), `TestMooA6Photo` (image rect native inside the scale
  group; a pixel inside the ornament clip matches the native photo) and
  `test_moo_a6_has_no_white_band_the_native_panel_lacks` (all 21
  templates: every white row/column in the A6 trim maps to a white one in
  the native render) in `test_per_panel_output.py`, `TestPanelFit` in
  `test_card_request.py` and `TestPanelFitOption` in `test_cli.py`.

- **2026-09-29 — Per-panel 144 DPI visual gate on PNG and PDF (expert-panel
  §P12 / D12, issue #68)**: The old gate hashed the whole 72 DPI PNG sheet
  (64-bit phash, threshold 5), so "all fonts → Lato" (distance 6) and
  inside-panel changes slipped through, and PDF had no pixel baseline.
  `tests/visual/test_visual_regression.py` now renders every shipped template
  × {png, pdf} on the letter target (fold marks off) at 144 DPI (PDF via
  pypdfium2), crops each panel where `imposition.panel_placements` puts it
  (inset 2 px), and fails a panel when more than 0.25% of its pixels differ by
  more than 32 on any channel: 21 × 2 × 4 = 168 comparisons. Helpers and the
  calibrated constants (`DPI`, `CHANNEL_DELTA`, `MAX_PANEL_RATIO`,
  `CROP_INSET_PX`) live in `tests/visual/visual_gate.py`, shared with
  `scripts/regenerate_visual_baselines.py` (now `--backend {png,pdf,all}`,
  `--template ID`, prints per-panel ratios vs the old baseline).
  `test_visual_gate_sensitivity.py` applies the calibration mutations to
  christmas-classic on both backends and requires every touched panel to trip
  (smallest: inside text removed, 0.51% PNG), so raising the limit fails it.
  Baselines are full sheets in `fixtures/reference_cards/{png,pdf}/`
  (1.9 MB), **generated on ubuntu-latest** by the new `visual-baselines`
  workflow (`workflow_dispatch`, uploads an artifact to eyeball and commit);
  the old root-level 72 DPI PNGs are deleted. On failure the CI test job
  uploads fresh sheets, crops and red diff heatmaps (`visual-out-*`,
  `HOLIDAY_CARD_VISUAL_OUT`). **Cross-host finding:** PDF rasters are
  identical on macOS and Ubuntu, but PNG text depends on whether Pillow can
  load libfribidi, which switches on its raqm (kerning) layout: without it
  text panels differ by up to 1.64%. ubuntu-latest has it; CI installs
  fribidi on macOS (exported `DYLD_FALLBACK_LIBRARY_PATH`, since SIP strips
  it from `/bin/bash`), which brings macOS to ≤ 0.102%, so both OSes are
  gated. `HOLIDAY_CARD_REQUIRE_PNG_VISUAL=1` (set in CI) turns the no-raqm
  skip into a failure, and the regenerate script refuses PNG without raqm.
  `tests/rasterize.py` now holds the pdfium rasterizer shared with the
  conformance suite. `imagehash` (and with it numpy) left the dev deps.
  Guarded by `test_visual_gate_sensitivity.py`,
  `test_visual_gate_crops.py` (boxes tile the sheet, 612×792 px each) and
  `test_regenerate_baselines_script.py`.

- **2026-09-29 — IR `Transform` is an explicit affine: pivot, rotate,
  scale about the pivot, offset (expert-panel §P11 / §P7 / D14, issue
  #72)**: `Transform.translate_x/y` held the rotation pivot, and the
  backends disagreed on `scale`: PDF scaled about the page origin, SVG
  about the pivot, and PNG raised. `core/render_ir.Transform` now has
  `pivot_x/y`, `rotate_deg`, `scale_x/y` (`gt=0`) and `offset_x/y` and is
  defined as `p' = T(offset)·T(pivot)·R(rotate, CCW)·S(scale)·T(−pivot)·p`.
  `is_identity()` ignores the pivot and `to_matrix()` returns the PDF `cm`
  tuple. The old names are removed, not aliased (D17), so
  `Transform(translate_x=…)` fails `extra="forbid"`. The four producers
  (panel, SVGPath, image and text rotation) pass `pivot_*`. PDF emits one
  `canvas.transform(*t.to_matrix())`. SVG keeps its decomposed string, with
  `translate(offset_x −offset_y)` in front. PNG replaced `overlay.rotate` with an
  AFFINE `overlay.transform` whose inverse coefficients come from
  `to_matrix()` conjugated by the IR→pixel map; its non-unit-scale raise is
  gone. `core/flatten` uses `to_matrix()` too (its copy of the old PDF
  order is deleted). The compiler still emits no scale (#73). The 16
  compile snapshots changed only by key rename plus default `offset_*`
  (checked with a key-renaming diff). Visual baselines are unchanged, and
  `christmas-classic` PDF rasterizes pixel-identically to `main`. The one
  `letter_content_sha256` entry that changed is
  christmas-holiday-masterpiece: a 45° `cm` translation moved from
  −29.93745 to −29.93729 (float rounding; ≤ 2/255 of AA noise at 300
  DPI). Guarded by `TestTransformMatrix` in `test_render_ir.py`, the
  `group_square_*` conformance cases (scale about the pivot, +rotate,
  +offset, nested scale-in-rotate; `group_scale_pivot` flipped to `match`
  for PDF and PNG), `tests/conformance/test_group_transform.py` (the SVG
  oracle vs a step-by-step formula) and
  `test_group_scale_is_about_the_pivot` in `test_compiler_flatten.py`.

- **2026-09-29 — PDF/X output has no transparency and no RGB images;
  every PDF/X file is preflighted (expert-panel §P9 / D10, issue #71)**:
  moo-a6 files carried ExtGState `/ca`/`/CA` < 1 (13 templates) and
  DeviceRGB photos with SMasks (5), both forbidden by PDF/X-1a.
  (1) New `CompileContext.flatten_transparency` (set by
  `build_per_panel_context` and `_generate_imposition` when
  `target.pdfx` is set) runs each panel's draws through
  `core/flatten.Flattener`: effective alpha = opacity × paint alpha ×
  every enclosing group opacity (groups are re-emitted at 1). A draw
  below 1 needs a known solid backdrop: the topmost earlier draw whose
  box meets the draw's box (panel frame; group transforms and clips
  applied as axis-aligned boxes; a stroke-only untransformed rect only
  "meets" boxes that touch its stroke band) must be an opaque solid
  rect / circle / ellipse fill that contains the box (rect: box
  inside, circle/ellipse: 4 corners inside, both inset by half the
  stroke); nothing earlier → paper white. The colour is composited in
  sRGB (`a·src + (1−a)·backdrop`, gradient stops and pattern colours
  too) and emitted opaque. Anything else (gradient, pattern, polygon,
  path, image or text backdrop, partial overlap, rotated or
  non-rect-clipped backdrop, a translucent group whose children
  overlap) raises `UnsupportedFeatureError` naming
  `<template>/<panel>/<list>[i] (<type>, id '…')` and the backdrop, e.g.
  "sits over a solid rect that does not fully contain it". A fully
  transparent draw is dropped. `flatten_transparency(commands, where=)`
  flattens hand-built IR. `DrawImage` records the solid backdrop on the
  new `ImageRef.backdrop: RGBA | None` (and carries the effective
  opacity); an image with alpha or opacity < 1 and no solid backdrop
  raises. (2) `IRReportLabRenderer(color_space="cmyk")` raises
  `NotImplementedError` ("compile with …flatten_transparency=True") for
  any alpha < 1 (shape, stroke, text, gradient stop, pattern colour)
  and never sets alpha; `CMYKColor` no longer takes `alpha`.
  `_draw_cmyk_image` opens the source with Pillow, composites alpha ×
  opacity over `ImageRef.backdrop` (raises without one), converts with
  `CMYKConverter.convert_image` (embedded ICC honoured) and embeds the
  CMYK image unmasked. The sRGB path is unchanged. (3)
  `CardGenerator._maybe_apply_pdfx` runs `preflight_pdfx1a` after
  `apply_pdfx1a` and raises the new
  `pdfx_preflight.PDFXConformanceError(path, violations)`; the CLI maps
  it to exit 2 listing each rule. (4) Templates: christmas-winter-sky
  (hills, trees, snowflakes), christmas-geometric (tiers, baubles),
  christmas-artist (one tree), christmas-holiday-masterpiece (two
  snowflakes; an invisible `opacity: 0` "star border" deleted) and
  birthday-photo (the photo halo) replaced `opacity` with colours
  pre-blended against the sampled preview backdrop. Previews differ by
  at most 29/255 on 0.6% of pixels (overlap tints of stacked
  translucent shapes are gone); the winter-sky and geometric visual
  baselines were regenerated and eyeballed, 3 compile snapshots and the
  5 affected entries of the letter content / PDF alpha goldens were
  regenerated. birthday-balloons, metallic-ornaments and the other
  translucent templates flatten automatically and keep live alpha in
  `letter`/SVG/PNG. The `test_pdfx_preflight_all_templates.py` xfails
  are gone: every moo-a6 file preflights clean and `pdfimages -list`
  says `cmyk`. Guarded by `tests/unit/test_compiler_flatten.py`,
  `TestCmykImages` / `TestCmykRefusesLiveAlpha` in
  `test_cmyk_operators.py`, `TestFlattenWiring` / `TestPhotoOrnamentFront`
  / `TestPdfxSelfCheck` / `TestLiveAlphaOutsidePdfx` in
  `test_pdfx_moo_a6.py` and `TestTranslucencyOnPdfxTargets` in
  `test_cli.py`. **Template authors: translucency over anything but a
  containing solid fill is refused for POD targets** (to be noted in the
  #57 authoring guide).

- **2026-09-29 — ICC-managed sRGB → CMYK with a 300% ink cap and
  press black rules (expert-panel §P10 / D9, issue #70)**: `moo-a6`
  wrote DeviceCMYK from the naive "black removal" formula, and a RIP
  prints DeviceCMYK as-is (the OutputIntent only names the condition),
  so pure blue printed purple (100/100/0/0), the christmas-classic red
  brick-orange (0/87.5/87.5/20) and large blacks a washed-out K-only
  grey. `rgb_to_cmyk` is deleted (D17). New `color_management.
  CMYKConverter(profile_path=None, *, total_ink_limit=3.00,
  rich_black=(.6,.4,.4,1), rich_black_min_area_pt2=5184)`:
  `convert(r, g, b, *, role="fill"|"stroke"|"text", area_pt2=None)`
  sends pure black text/strokes to `0 0 0 1`, a pure-black fill whose
  bbox is ≥ 1 in² to rich black and a smaller or area-less fill to K-only;
  every other colour is quantised to 8 bits and converted by one
  LittleCMS transform (Pillow `ImageCms`, sRGB → bundled GRACoL2013,
  relative colorimetric + BPC; `lru_cache` per triplet), then capped: if
  C+M+Y+K > limit, C/M/Y scale by `(limit − K)/(C+M+Y)` and K stays.
  `convert_image(img)` (the #71 seam) applies transform + cap per pixel,
  honours an embedded `icc_profile` and returns mode `CMYK`; black rules
  don't apply to rasters. A missing profile raises
  `ICCProfileNotFoundError`, an unreadable or non-CMYK one `ValueError`
  (D4, no naive fallback). `IRReportLabRenderer(color_space="cmyk")`
  shares one process-wide converter (Pillow's `ImageCmsTransform.apply`
  re-serialises the 3.4 MB output profile on every call, ~12 ms, so the
  memo must outlive a single panel); `_set_fill` takes `role` /
  `area_pt2` (`_draw_shape` passes the `_shape_bbox` area, paths
  `None`), `_draw_text` passes `role="text"`, `_set_stroke` and fold
  lines `role="stroke"`, and the gradient / pattern helpers share
  `_rl_color` (gradient stops and the pattern background carry the
  bbox area; pattern tiles count as small). `_draw_image` and alpha are
  untouched (#71). Result: classic front bg `0 .988 .925 .122 k`, blue
  100/85.5/0/0, `#0A0A0A` 77.3/69.5/59.0/94.1 (TAC exactly 300). The
  sRGB `letter` path is byte-identical: its content streams match
  `tests/integration/__golden__/letter_content_sha256.json`, captured
  before the change (regenerate only on purpose with
  `HOLIDAY_CARD_REGEN_LETTER_CONTENT_GOLDEN=1`). Snapshots and visual
  baselines unchanged. Guarded by `tests/unit/test_color_management.py`
  (the issue's ±2-point table, a 9×9×9 TAC grid, roles and the 5184 pt²
  boundary, profile errors, `convert_image` with a Display-P3 tag),
  `tests/integration/test_cmyk_operators.py` (per-role operators,
  gradient `C0`, pattern tiles, fold line, TAC ≤ 3.0 for every `k`/`K`
  in all 21 templates' moo-a6 output, the sRGB golden) and
  `TestPdfxMooA6::test_front_background_is_icc_converted`.

- **2026-09-29 — PDF/X-1a: embedded initial font, correct Info/XMP
  identification, and a rule preflight gated in CI (expert-panel §P9 /
  D11, issue #69)**: (1) `IRReportLabRenderer` created its canvas with
  ReportLab's default initial font, base-14 Helvetica, which it never
  embeds, so every page of every PDF (sRGB and CMYK) opened with `/F1 12
  Tf` on an unembedded font. The canvas now passes `initialFontName=
  resolve_font_id("Helvetica")` (LiberationSans); `pdffonts` shows
  `emb yes` on every row. (2) `apply_pdfx1a` writes `/Info
  /GTS_PDFXVersion` and `/GTS_PDFXConformance` = `PDF/X-1a:2003`; the
  XMP `pdfx:GTS_PDFXVersion` is `PDF/X-1a:2003` (ISO 15930-4; it said the
  2001 identifier `PDF/X-1:2001` and the old test enforced that) and gains
  `xmp:CreateDate` / `ModifyDate` / `MetadataDate` converted from the Info
  `D:` dates. The OutputIntent says `/OutputConditionIdentifier
  (CGATS21-2-CRPC6)` and `/OutputCondition (GRACoL 2013, CRPC6 — CGATS
  21-2)`, matching the bundled profile (was `CGATS TR 006`). (3) New
  `renderers/pdfx_preflight.py`: `preflight_pdfx1a(path) ->
  list[PreflightViolation(rule, page, detail)]` checks header 1.4, `/ID`,
  no `/Encrypt`, Info keys + `Trapped` + `GTS_PDFXVersion`, XMP ↔ Info
  equality, exactly one `/GTS_PDFX` OutputIntent with an `N=4` profile,
  MediaBox ⊇ BleedBox ⊇ TrimBox ⊇ ArtBox, embedded fonts (Form XObjects,
  tiling patterns and Type 0 descendants included), transparency
  (`/ca`/`/CA` < 1, `/BM`, `/SMask`, image `/SMask`, transparency
  groups), RGB-family colour spaces (DeviceRGB / CalRGB / ICCBased / Lab)
  in content operators, images and shadings, and JavaScript / JPX /
  transfer functions. It reports; it never raises, and the generator does
  not call it yet (#71 wires it in). (4) New CI job `pdfx-preflight`
  (ubuntu + `poppler-utils` + `ghostscript`) runs `pytest -m pdfx` with
  `HOLIDAY_CARD_REQUIRE_PREFLIGHT_TOOLS=1`, which turns a missing tool
  into a failure (elsewhere those tests skip); `build` needs it. The new
  `pdfx` marker covers `tests/unit/test_pdfx_preflight.py` (one hand-built
  PDF per rule, mutated from a clean CMYK render),
  `test_pdfx_moo_a6.py` and `tests/integration/
  test_pdfx_preflight_all_templates.py` (moo-a6 for all 21 templates:
  font / metadata / box rules clean, `pdffonts` all `emb yes`, `gs
  -sDEVICE=inkcov` 4 values per page, plus the default `letter` PDF's
  fonts). `transparency.*` is a strict xfail for 13 templates and
  `colorspace.rgb_image` for the 5 photo templates; #71 trims
  `TRANSPARENCY_TEMPLATES` / `RGB_IMAGE_TEMPLATES` as it fixes them.
  D11 was already amended (veraPDF has no PDF/X profile). Removing
  `initialFontName` turns 52 `pdfx` tests red. Snapshots and visual
  baselines unchanged.
- **2026-09-29 — Cross-backend conformance suite + capability matrix
  (expert-panel §P12 / D12, issue #67)**: New `tests/conformance/` (no
  `__init__.py`). `cases.py` holds 37 frozen `Case`s, each a 144×144 pt
  page (bleed 0, except `page_bleed_background`) built straight from
  `render_ir` types that exercises one feature: fills, strokes, dash
  arrays on a line, gradients, the four patterns, clips, group
  rotate/scale/opacity, alpha, Lato/Cormorant text, JPEG images, fold
  line and bleed. `test_conformance.py` renders every case through SVG
  (the oracle, rasterized by `resvg-py` with `skip_system_fonts=True` +
  the bundled fonts) and through PDF (rasterized by `pypdfium2`) and PNG,
  all at 144 DPI, and applies `capabilities.CAPABILITIES[case][backend]`:
  `match` must be within tolerance, `raises` must raise
  `NotImplementedError`, and `known_diff` must be **outside** tolerance,
  so fixing the bug fails the test until the matrix is flipped (explicit
  strict-xfail). Tolerances are in `conftest.py`: a pixel mismatches at a
  channel delta > 48; `match` means mismatch ratio ≤ 1.0% (PDF) / 2.0%
  (PNG, no AA until #77) **and** a mean ink colour within 48 per channel.
  The ink check exists because a 0.5 pt fold line is 0.35% of the page, so
  a ratio alone missed an inverted fold-line colour. Text cases compare
  the ink bbox (±3 px per edge) plus the mean ink colour. Drift guards:
  every case has both backends, no orphans, every `known_diff` names an
  owner. `docs/conformance-matrix.md` must equal `render_markdown(
  CAPABILITIES)`; regenerate with `python -m tests.conformance.capabilities
  > docs/conformance-matrix.md`. Observed matrix: everything `match`
  except `stroke_rect_6pt` PNG (#77), `pattern_stripes` PDF and
  `pattern_grid` / `pattern_checkerboard` on both (#74), `group_scale_pivot`
  PDF (#72; PNG raises), `text_curated_family` (#76: the SVG oracle draws
  nothing for `font-family="Cormorant"`; `conftest` points every resvg
  generic family at a sentinel name so an unmatched family draws nothing on
  every host, because resvg's default fallback resolved on Linux but not
  macOS), and `group_opacity` (both
  raise). `pattern_dots` and `pattern_stripes` PNG match with this
  fixture; PNG dots sit at 1.98% of the 2.0% limit. Dev deps:
  `pypdfium2` and `resvg-py` added (wheels only, no system packages, so
  CI is unchanged); the unused `pdf2image` is gone. The suite adds 80
  tests and ~1 s.

- **2026-09-29 — PNG backend honours clips, dashes and text alpha, or
  raises (expert-panel §P6 / §P5 / D4, issue #61)**: `preview` uses
  `PNGRenderer`, which silently rendered a different card than PDF/SVG.
  (1) `BeginClip` only pushed a geometry that `_draw_image` alone read,
  and nested clips were unioned. Now `_begin_clip` builds a canvas-sized
  "L" mask (`_geom_mask`: rect / rounded rect / circle / ellipse /
  polygon / path) intersected (`ImageChops.multiply`) with the enclosing
  mask at the same group level; `_clip_stack` holds `(level, mask)`,
  where level counts open non-identity groups. `DrawShape`, `DrawText`,
  `DrawImage` and `DrawFoldLine` under a mask draw on a transparent
  layer (`_draw_in_layer`) and `_composite` through it; `_end_group`
  composites the rotated overlay through the parent level's mask, so a
  clip opened outside a rotated group still applies. `PolylineGeom`
  clips raise `NotImplementedError` at `BeginClip`. `_stamp_clip_geom`
  and `_draw_shape_with_alpha_compositing` are gone. (2) `Stroke.dash`
  was never read. `_stroke_outline` flattens the outline
  (`_outline_polylines`; circles/ellipses ≥ 64 samples, paths via the new
  `_flatten_path`) and module-level `_dash_runs` walks it with PDF/SVG
  semantics (odd arrays repeat, phase 0, restart per subpath); fold lines
  use the same walker. (3) Text ignored `opacity` and `color.a`; the
  effective alpha `opacity × color.a` is now applied by drawing opaque
  glyphs on a layer pre-filled with the text colour at alpha 0 (no dark
  fringes) and compositing. (4) `_get_font` resolves only through
  `font_registry.ttf_path_for` and raises `NotImplementedError` naming
  the font_id otherwise; `_FONT_FALLBACKS`, `_GENERIC_FALLBACKS` and
  `ImageFont.load_default()` are deleted. (5) Found while diffing every
  template before/after: gradient/pattern fills were pasted with
  themselves as mask, which also lowered the canvas alpha, so translucent
  gradients washed toward white at save time. They now `alpha_composite`.
  Only `christmas-winter-sky` (0.7/0.6 mountains) and
  `christmas-metallic-ornaments` (translucent back ornaments) changed;
  both visual baselines were regenerated and eyeballed; the other 19
  templates render pixel-identical. Guarded by
  `tests/integration/test_png_ir_fixtures.py` (importable module-level
  fixtures for #67: `CLIP_SHAPE_IN_CIRCLE`, `CLIP_TEXT_IN_RECT`,
  `CLIP_NESTED_INTERSECT`, `CLIP_IMAGE_NESTED`, `CLIP_UNDER_ROTATED_GROUP`,
  `CLIP_POLYLINE`, `DASHED_RECT`, `DASHED_CIRCLE`, `TEXT_OPACITY_OVER_RED`,
  `GRADIENT_OPACITY_OVER_RED`, `UNKNOWN_FONT`). AA, centred strokes,
  `line_cap` and gradient speed stay with #77.
- **2026-09-29 — ReportLab backend: correct quadratics, dash arrays and
  scoped alpha (expert-panel §P7 / D4 / D12, issue #62)**: Four latent
  `IRReportLabRenderer` bugs that shipped templates dodged only because the
  compiler drops colour alpha. (1) Quadratic path ops lifted from the
  control point (`path.contour` doesn't exist on ReportLab paths);
  `_geometry_to_path` now tracks the current point and subpath start
  (`close` returns to it) and a `quadratic` with no current point raises
  `ValueError`. (2) `_apply_fill` called `setFillAlpha(c.a)` and nothing
  reset it, so one translucent fill made every later fill and text
  translucent; `opacity` replaced the colour alpha instead of multiplying;
  stroke colour alpha, text colour alpha and `DrawImage.opacity` were
  ignored. Now each draw whose effective alpha is < 1 (fill / stroke / text
  = `opacity × color.a`, image = `opacity`) is wrapped in
  `saveState`/`restoreState` (q/Q); no manual "reset to 1.0". `opacity`
  scales both `/ca` and `/CA`. (3) `setDash(*dash)` emitted `[4 0]` (solid)
  for a 1-element dash and raised `TypeError` for 3–4 elements; it is now
  `setDash(list(dash), 0)`. (4) `BeginGroup.opacity != 1` raises
  `NotImplementedError` (needs a transparency-group XObject), matching the
  PNG backend. New `tests/integration/test_pdf_ir_fixtures.py`: importable
  module-level IR fixtures (`QUAD_*`, `FILL_ALPHA_NO_LEAK`,
  `ALPHA_MULTIPLY`, `STROKE_ALPHA`, `TEXT_ALPHA`, `IMAGE_OPACITY`,
  `DASH_ARRAYS`, `GROUP_OPACITY`) for the #67 parity matrix, an
  `ops_with_alpha` pikepdf walker that tracks (ca, CA) across q/Q/gs, and a
  golden (`__golden__/pdf_alpha_sequence.json`, captured before the fix)
  of the `(op, ca, CA)` sequence for every paint op in all 21 templates'
  letter PDFs. That golden is unchanged. Regenerate it only on purpose,
  with `HOLIDAY_CARD_REGEN_PDF_ALPHA_GOLDEN=1`. Group scale about the pivot
  is left to #72.
- **2026-09-29 — Text `font_style` and `rotation` are honoured (expert-panel
  §P3 / D4, issue #63)**: after #56 the loader passed `font_style` and
  `rotation` through, but the compiler still used `text.font_family`
  verbatim and never read `text.rotation`, so the 33 `font_style` uses
  across the shipped templates printed regular. `_compile_text` now resolves the font with
  `_styled_font_id(text)`, which calls `markdown.font_id_for_run` (Cormorant +
  italic → `Cormorant-Italic`; Inter/Caveat/Comfortaa/Lato-italic degrade
  to regular, the documented limitation). Wrapping and shrink-to-fit measure
  the **resolved** font, so the mothers-day greeting (Playfair italic, 30 pt)
  no longer shrinks to 29 pt. The letter path uses the element's style as
  the base for every part; a `--signature-font` override is used verbatim.
  Rich text (`--inside-message-md`) ignores `font_style`, because the
  Markdown run flags decide each run's style. It does not raise, since the CLI sets
  `rich_content` on template elements that carry a style. A non-zero text
  `rotation` wraps the element's `DrawText`s (plain, letter or rich) in
  `BeginGroup(Transform(pivot = text anchor, rotate_deg))` / `EndGroup`.
  `_compile_text` is now a thin wrapper over `_compile_text_body`. 10
  compile snapshots changed in `font_id` only, plus that one `size_pt`.
  13 visual baselines were regenerated and eyeballed: the headings are now
  visibly bold or italic. Guarded by `TestTextFontStyle`,
  `TestShippedTemplateFontStyles` (every styled element in all 21
  templates), `TestTextRotation` in `test_compiler.py` and
  `TestLetterFontStyle` in `test_compiler_letter.py`.
- **2026-09-29 — The `letter` target is a true 8.5×11 page with no bleed
  (expert-panel §P4 / D7, issue #59)**: `holiday-card create` wrote a
  630×810 pt page (8.75×11.25") because `PageGeometry.us_letter()`
  defaulted to 0.125" of bleed and `CropBox = MediaBox`. Home print
  dialogs "fit to page" that onto Letter, shrinking it ~2.9% and moving
  the fold lines off the physical centre. `PageGeometry.us_letter(bleed_in=
  0.0)` is now the default; the `letter` target uses `us_letter()`; the
  default `CompileContext` (`preview`, `--debug-emit-ir`, the visual
  suite, the scripts) therefore produces a bleed-free Letter page. The
  PDF declares MediaBox = CropBox = TrimBox = BleedBox = `[0 0 612 792]`
  and ArtBox `[18 18 594 774]`; SVG is `width="612" height="792"
  viewBox="0 0 612 792"`; `preview` at 144 DPI is 1224×1584. In
  `_bleed_extended_panel_rect` the extension is `min(panel-or-card bleed,
  geometry.bleed_in)`, so with a zero-bleed page no background rect
  leaves the trim (before, they sat at −9 pt off the page). POD output is
  unchanged: `per-panel-pdf` and `moo-a6` keep their 0.125" geometries and
  TrimBox stays inset 9 pt. `svg_backend._fmt` normalises IEEE `-0.0`
  to `0` (a zero bleed produced `viewBox="-0 -0 …"`). **Tests that
  exercise bleed must pass an explicit `PageGeometry.us_letter(bleed_in=
  0.125)`** (`test_compiler._NO_IMPOSE` does). All 16 compile snapshots
  (`BeginPage.bleed` 9 → 0, rects unextended) and all 21 visual baselines
  (630×810 → 612×792) were regenerated and eyeballed. Guarded by
  `TestLetterPageBoxes` in `test_full_generation.py` (pikepdf boxes + SVG
  canvas), `TestBeginPageBleedFields` / `TestBleedExtension` in
  `test_compiler.py` (default bleed 0, every rect inside the trim,
  explicit-bleed geometry still extends, cap at geometry bleed),
  `test_preview_command_at_144_dpi_is_letter_sized` in
  `test_png_backend.py`, and a `moo-a6` MediaBox ≠ TrimBox guard in
  `test_per_panel_output.py`.
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
  declaring PDF/X-1a:2003 (it wrongly said `GTS_PDFXVersion=
  "PDF/X-1:2001"` until #69), `/Info /Trapped` set to
  `/False`, and the PDF header forced to 1.4. Implementation:
  `core/color_management.py` (naive sRGB→CMYK conversion, replaced
  by the ICC `CMYKConverter` in #70, + ICC path resolution), `renderers/pdfx_postprocess.py` (pikepdf-based
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
  PDF/X-1a (next slice of Leapfrog 1). (Since #73, moo-a6 fills the trim
  and crops via one compiler scale group; the domain-level scaling
  helpers are gone.)
- **2026-05-10 — Bleed support + `PageGeometry` abstraction**: Backgrounds
  now extend past the trim edge by 0.125" (industry default) on edges that
  touch the page trim. `Card.bleed` and `Panel.bleed` configure it; the
  PDF declares distinct `MediaBox` / `TrimBox` / `BleedBox` / `ArtBox`;
  SVG `viewBox` and PNG canvas grow to include the bleed band. Lays the
  rails for `--export-for moo-a6` (Leapfrog 1) without shipping it yet.
  (Since #59 the default `letter` page carries no bleed; this
  behaviour now applies to the POD targets and to any explicit
  `PageGeometry` with `bleed_in > 0`.)
- **2026-05-10 — Wave 2 complete + v1.1.0 release**: IR seam
  (PRs #4-#10), three rendering backends (PRs #7/#11/#12), working
  `preview` command (PR #12), version bump + zero mypy errors + strict
  CI gates (PR #13). Net: 12 PRs, ~6,950 LOC removed, ~3,800 added.
- **2026-05 — Wave 1 DevEx audit (PR #1)**: Real CI on every push,
  `requirements.txt` deleted, 22 B904 + 10 null-deref bugs fixed.
- **2026-05 — Valentine deprecation (PR #8)**: Removed the 2026-02
  Valentine release (templates + decorative-element library) when
  porting to the IR proved non-trivial. The dead model code (HeartClipMask,
  etc.) has since been removed; no `HeartClipMask` exists in `src/`.
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
