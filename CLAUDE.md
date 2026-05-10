# holiday-card — Development Guidelines

Last updated: 2026-05-10. Wave 2 architecture refactor is **complete**;
the codebase is at v1.1.0 with all CI quality gates blocking.

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
pip install -e ".[dev]"            # one source of truth: pyproject.toml
holiday-card create christmas-classic -m "Merry Christmas!"     # writes a PDF
holiday-card create christmas-classic --format svg              # writes an SVG
holiday-card preview christmas-classic                          # writes a PNG and opens it
pytest                              # all 324 tests, mypy-clean, ruff-clean
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
    validators.py       # Domain validation helpers
  renderers/
    reportlab_backend.py  # IR → PDF (default)
    svg_backend.py        # IR → SVG (browser-openable)
    png_backend.py        # IR → PNG (powers `preview` command)
    image_effects.py      # Pillow effects (sepia/grayscale/vignette/blur)
  cli/
    commands.py         # Typer CLI: create, preview, templates, themes, validate
  utils/
    measurements.py     # inch ↔ point conversions; page constants
    svg_parser.py       # SVG path parser (preserved for future IR support)
    validators.py       # Input validation (image format, etc.)
tests/
  unit/                 # test_render_ir, test_compiler, test_cli, test_text_fitting,
                        #   test_text_utils, test_models, test_clipping_masks,
                        #   test_gradient_models, test_pattern_models,
                        #   test_svg_models, test_svg_parser, test_validators,
                        #   test_measurements
    __snapshots__/      # JSON snapshots of compile_card() output per template
  integration/          # test_full_generation, test_svg_backend, test_png_backend
  visual/               # Reserved for future visual regression (no tests yet)
templates/              # YAML card templates
  christmas/            # 11 christmas templates (some have id-mismatch bugs — see "Known issues")
  birthday/, hanukkah/, generic/
themes/                 # Color theme YAML
fonts/                  # Custom TTF/OTF fonts
specs/                  # Historical spec-kit feature plans (001-004; some describe deleted features)
```

## Commands

### Quality gates (run all of these — they're the CI blocking gates too)

```bash
ruff check src/ tests/      # Lint — must be clean
mypy src/                   # Type-check — must be clean (strict mode)
pytest                      # All 324 tests pass
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
```

### Hidden / dev flags

```bash
holiday-card create christmas-classic --debug-emit-ir   # print compiled IR as JSON
                                                        # (skips PDF; for IR debugging)
```

## Currently supported template subset

The compiler supports backgrounds, borders, basic shapes (Rectangle,
Circle, Triangle, Star, Line) with **solid fills only**, text with
left/center/right alignment, fold lines, and identity or rotation-only
group transforms. **7 of the 11 templates currently compile cleanly:**

```
christmas-classic     christmas-geometric    christmas-modern
christmas-artist      birthday-balloons      hanukkah-menorah
generic-celebration
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

Wave 4 ideas: HTML/Canvas renderer streaming over a websocket for live
template editing; a CMYK PDF wrapper for pro-press output; a JSON
"render plan" backend for downstream tooling.

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

- **Template id-mismatch bug:** Some YAML templates have `id` fields
  that don't match their filename, so `discover_templates()` doesn't
  find them by their expected names (e.g. `christmas-holly_wreath`,
  `christmas-festive_stripes`). Look at `core/templates.py` discovery
  logic.
- **Dead Pydantic models in `models.py`:** `HeartClipMask`,
  `DecorativeElement`, gradient/pattern fill models, `SVGPath` shape
  exist but no production code imports them. They're referenced only
  by `tests/unit/test_clipping_masks.py`, `test_gradient_models.py`,
  `test_pattern_models.py`, `test_svg_models.py`. Pruning is a focused
  PR.
- **Compiler feature gaps:** Adding `ImageElement` support would
  re-enable photo cards. Adding gradient + pattern fills would unlock
  the 4 christmas templates that currently fail.
- **`tests/visual/` is empty:** A perceptual SSIM gate against a
  committed baseline PNG per template would catch layout regressions
  the structural tests miss. The PNG backend produces deterministic
  output, so this is tractable.

## Recent changes

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

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
