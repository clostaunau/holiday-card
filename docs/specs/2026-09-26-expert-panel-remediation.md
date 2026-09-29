# Expert-panel remediation program — spec of record

**Date:** 2026-09-26 · **Baseline commit:** `f3657fa` (v1.3.0) · **Status:** ACCEPTED (owner agreed to all recommendations 2026-09-26)
**Tracker issue:** see the GitHub issue titled `tracker: expert-panel remediation program`.

> **Staleness protocol.** The repo moves. Every `file:line` below was observed on
> `f3657fa`. Re-verify each anchor against current `main` before relying on it; if a
> reference has moved, say so in your PR rather than quietly using a stale one.

## 1. What this is

On 2026-09-26 a six-reviewer engineering panel audited the repo, each through one
lens: **(ARCH)** architecture & code quality, **(TEST)** testing & CI, **(PRINT)**
print production / prepress, **(SEC)** security & packaging, **(UX)** CLI UX & docs,
**(REND)** rendering correctness across backends. Reviewers built the project in
fresh venvs, generated real PDF/SVG/PNG output, inspected PDFs with pikepdf,
rasterized with pdftoppm / rsvg-convert, and measured. ~60 raw findings were merged
into the themes below. Items marked **[verified]** were independently re-checked by
the orchestrating session.

This panel is **engineering-focused** and complements (does not replace) the
product/strategy panel in `docs/industry-review/`. Standing strategic decisions from
that panel (Tyler-first CLI audience, AI imagery narrow + hard-railed) are not
re-opened here.

## 2. Standing decisions (do not re-open)

Recorded 2026-09-26; the owner accepted every recommendation.

| # | Decision | Rejected alternative |
|---|---|---|
| D1 | Package data (templates, fonts, themes, sentiments, ICC) moves **inside the package** and is resolved via `importlib.resources`; env-var overrides stay; cwd fallbacks are removed. | Keep repo-root dirs + `force-include` each one (keeps the fragile `__file__`-walking resolution). |
| D2 | Dependencies locked with **`uv.lock`**; CI installs from the lock; a weekly scheduled job tests unpinned latest. | pip-tools constraints file. |
| D3 | Template YAML is loaded with **`Template.model_validate`** and domain models use `extra="forbid"`; YAML alias spellings (e.g. `x1`/`start_x`) via `validation_alias`. | Keep hand-written per-shape parsing in `core/templates.py`. |
| D4 | **Fail loud** everywhere: silent ignores become exit-code-2 errors (CLI) or `UnsupportedFeatureError`/`NotImplementedError` (core/backends). | Warnings. |
| D5 | Template `image_elements[].source_path` resolves **relative to the template file**; absolute paths and `..` are rejected in templates (CLI `--image` may be any path). | cwd-relative resolution. |
| D6 | Letter-sheet imposition is computed **by the compiler from the fold type**, not trusted from template panel x/y. | Hand-editing every template's panel coordinates. |
| D7 | `letter` export target uses **bleed 0** (MediaBox = 8.5×11); bleed stays on POD targets. | CropBox = TrimBox with bleed retained. |
| D8 | `moo-a6` default is **fill-then-crop** (`max` scale), warning if text crosses the safe zone; letterbox is opt-in only. | Letterbox default (produces white bands). |
| D9 | CMYK conversion uses **LittleCMS via Pillow `ImageCms`** sRGB → bundled GRACoL2013 profile, relative colorimetric + BPC, total ink cap 300%, pure-black text → 0/0/0/100, large black areas → rich black. | Naive formula in `core/color_management.py`. |
| D10 | In CMYK/PDF-X mode, alpha is **pre-composited against the known backdrop in the compiler where the backdrop is a solid fill; otherwise raise `UnsupportedFeatureError`**. RGB images are converted to CMYK via the same ICC transform. A PDF/X-4 target is a possible follow-up, not in scope. | Emit live transparency. |
| D11 | ~~PDF/X conformance is checked with **veraPDF** in CI~~ **Amended 2026-09-26:** veraPDF validates PDF/A, PDF/UA and WTPDF only, not PDF/X. Conformance is checked by a pikepdf-based rule preflight (`renderers/pdfx_preflight.py`) plus a CI job cross-checking with `pdffonts` and Ghostscript `inkcov` (see §7). | Hand-rolled regex assertions only. |
| D12 | Cross-backend correctness is guarded by a **conformance suite** (`tests/conformance/`) that renders one-feature IR fixtures through all three backends; **SVG is the reference oracle**. Each backend must match within tolerance or raise `NotImplementedError` (capability matrix). | Per-backend structural tests only. |
| D13 | Pattern fills are **lowered by the compiler** into clip + primitive draw commands; the three backend pattern implementations are deleted. | Keep `PatternPaint` in the IR with a tighter tile spec. |
| D14 | IR `Transform` fields are renamed to reflect pivot semantics and **scale is defined about the pivot** in every backend (PNG gains scale support). | Leave `translate_x/y` naming. |
| D15 | One frozen **`CardRequest` + `build_card(request) -> Card`** in `core/` owns all CLI precedence rules; `create`, `preview`, `--debug-emit-ir` (and the microsite) consume it. | Keep logic inside `create()`. |
| D16 | `-o` means **`--output` everywhere** (breaking for `templates/themes/init` which use it for `--occasion`; those get no short flag or `-O`). Exit codes are documented. | Leave inconsistent. |
| D17 | Dead code is **deleted**, not kept "for the future" (owner preference: deletion over shims). | — |

## 3. Findings by theme (evidence)

Section IDs (§P1 …) are what issues cite.

### §P1 Installed package is broken [verified] — SEC P1, TEST F1, UX F1
- `pyproject.toml:61-62` force-includes only `assets/` → wheel contains only `holiday_card/_assets/icc/GRACoL2013_CRPC6.icc` as data.
- Path resolution walks up from `__file__`: `core/templates.py:62-72`, `core/themes.py:43`, `core/sentiments.py:96`, `renderers/font_registry.py:42` (`parent×4 / "fonts"` → `venv/lib/python3.12/fonts` when installed), `core/color_management.py:95`. Fallbacks are cwd-relative `Path("templates")`.
- Observed from a wheel install run outside the repo: `holiday-card templates` → `No templates found.` (**exit 0**); `create christmas-classic` → `Error creating card: [Errno 2] No such file or directory: 'templates'`; `themes` → `No themes found.`. With template/sentiment env vars set it then fails on fonts: `Font Lato-Bold.ttf not found at …/lib/python3.12/fonts/curated/…` → `Error creating card: 'PlayfairDisplay'` (raw KeyError).
- CI can't catch it: smoke (`.github/workflows/ci.yml:74`), `render-cards.yml:60`, `microsite.yml:55` all `pip install -e .`; the build job (`ci.yml:119-135`) builds but never installs the wheel.
- OFL requires font license texts to ship with the fonts (`fonts/LICENSE`, `fonts/curated/*-LICENSE.txt`). No root `LICENSE` despite `License-Expression: MIT`. No NOTICE for the GRACoL ICC.

### §P2 Unpinned deps; CI red today — TEST F2, SEC P6
- All deps floor-only (`pyproject.toml:28-53`), no lockfile. numpy 2.5.3 (transitive via imagehash / Pillow typing) breaks `mypy src/` under `python_version = "3.11"` (`pyproject.toml:107`): "Type statement is only supported in Python 3.12". `numpy<2.4` → clean.
- pre-commit pins ruff v0.6.9 / mypy v1.11.2 (`.pre-commit-config.yaml:3,8`); CI installs latest (observed ruff 0.16.9, mypy 2.3.1).
- `Pillow>=10.0` is below CVE-2024-28219 fix (10.3.0); `ImageCms` is used in `core/ai_assets.py:28,161`. `typer[all]` extra no longer exists in modern Typer.
- Baseline on 2026-09-26 (py3.12, fresh venv): **831 passed, 1 skipped, 57.7 s**; ruff clean; branch coverage 79%.

### §P3 Template loader silently drops data [verified] — ARCH F1, UX F6
- **Status (2026-09-26): loader bullets addressed by #56.** Templates load via `Template.model_validate` with `extra="forbid"` on every domain model; the hand parsers are deleted; holly-wreath / holiday-masterpiece path coordinates fixed. The `validate` UX / schema bullets remain with #57.
- **Status (2026-09-29): compiler half of the `font_style` drop closed by #63.** `_compile_text` / `_compile_letter_content` resolve `TextElement.font_style` through `markdown.font_id_for_run` (measurement uses the resolved font), and a non-zero text `rotation` wraps the element's `DrawText`s in a pivot-rotate group at the text anchor.
- `core/templates.py:452-462` builds `SVGPath(...)` without `x`/`y` → default 0.0, although `templates/christmas/holly-wreath.yaml:41-42` sets `x: 2.125, y: 4.6`. Committed snapshot `tests/unit/__snapshots__/compile_card__christmas-holly-wreath.json` shows every leaf at `move (370.8, 12.96)` (bottom-left corner of front panel). `christmas-holiday-masterpiece` reportedly same (unverified). Snapshot **and** visual baseline have locked the bug in.
- `templates.py:491-494` catches `KeyError/ValueError/TypeError`, logs, returns `None` → shape silently vanishes (`:234`). Unknown shape `type` → `None`. `Line` branch drops `rotation` and `fill`.
- No model forbids extra keys: a YAML with `colr:`, `font_famly:`, `font_family: NotAFont`, `x: 99` passes `holiday-card validate` as "Template valid"; `create` then fails `Error creating card: 'NotAFont'`.
- Only schema doc is stale `specs/004-*/contracts/yaml-schema.md`.

### §P4 Letter imposition wrong [verified] [closed by #58, #59] — PRINT P6, P7
- Templates (e.g. `templates/christmas/classic.yaml:14-71`): front BR (x 4.25, y 0), back BL, `inside_left` TL (x 0, y 5.5, rot 180), `inside_right` TR (x 4.25, y 5.5, rot 180). Folding print-side-out (top half back, then left half back so front BR is the cover): **TR ends up behind the front cover = the left inside page.** The 180° rotation is right; left/right positions are mirrored. Affects every 4-panel template.
- Labelled `fold_type: half_fold` but 4 panels on Letter is a quarter-fold; only the horizontal fold mark is drawn.
- Letter PDF MediaBox is 630×810 pt (8.75×11.25") because bleed is added; CropBox = MediaBox (`renderers/reportlab_backend.py:144`). Home printers "fit" → ~2.9% shrink.
- **Status (2026-09-29): imposition bullets closed by #58.** `core/imposition.py` computes the slots from the fold type (front BR, back BL, inside_left TR r180, inside_right TL r180); templates carry no panel coordinates; `half_fold` is a legacy alias of `quarter_fold` and both draw two fold marks.
- **Status (2026-09-29): MediaBox / bleed bullet closed by #59.** `PageGeometry.us_letter()` defaults to bleed 0 and backs the `letter` target; MediaBox = CropBox = TrimBox = BleedBox = 612×792; background extension is capped at the page geometry's bleed. POD targets keep 0.125". §P4 is fully closed.

### §P5 Fail-loud violations — ARCH F6, UX F4, REND F1, SEC P1 [partly verified]
- **[closed by #60]** `core/generators.py:198-199` `except ThemeNotFoundError: pass` [verified] — `--theme nope` exits 0; `SetMetadata` still records the theme id (`core/compiler.py:201`).
- **[closed by #60]** `--blank-inside --inside-message HELLO` renders nothing, reports `Inside: (blank)`.
- **[closed by #60]** `--seed` without `--voice` silently ignored.
- **[closed by #60]** `sympathy-spare --voice witty` prints two warnings (leaking absolute sentiment path) and exits 0; CLAUDE.md says it should raise `SentimentNotFoundError`.
- **[closed by #60]** `--fold-type tri_fold` on a 4-panel template succeeds and draws tri-fold guides (`core/compiler.py:1561`).
- **[closed by #60]** `--export-for moo-a6 -o single.pdf` creates a *directory* `single.pdf`; `-o x.docx` writes `x.docx.pdf`; `-o x.svg --format pdf` writes `x.svg.pdf`.
- **[closed by #60]** Unknown font → raw `KeyError` (`'PlayfairDisplay'`, `'NotAFont'`).
- `templates`/`themes` exit 0 when nothing found.
- **[closed by #61]** PNG font chain silently falls back to Pillow bitmap font (`renderers/png_backend.py:674-681`).
- **[closed by #60]** Catch-all `except Exception` → exit 1 (`cli/commands.py:625`) hides tracebacks; no `--debug`.
- Good existing behavior to preserve: flag-conflict messages (e.g. `--inside-message-md` + letter parts), unknown `--export-for`/`--voice` list valid values; no traceback in ~40 bad-input runs.

### §P6 PNG backend silently drops features [verified] — REND F1, F2, F8, F10
- **Status (2026-09-29): clip, dash, text-alpha and font bullets closed by #61.** Clips are canvas masks intersected per group level and applied to shapes, text, images and fold lines (and to a rotated group's overlay when the clip is opened outside it); `PolylineGeom` clips raise at `BeginClip`. `Stroke.dash` is walked along the flattened outline (PDF/SVG semantics). Text alpha = `opacity × color.a`. Fonts resolve only via `ttf_path_for`, else `NotImplementedError`. Translucent gradients/patterns no longer wash toward white. Fixtures in `tests/integration/test_png_ir_fixtures.py`. AA / stroke centring / perf stay with #77.
- **[closed by #61]** `BeginClip` only pushes `_clip_stack` (`png_backend.py:259`); only `_draw_image` reads it (`:747-756`). A rect clipped to a circle renders square in PNG.
- **[closed by #61]** `Stroke.dash` never read → dashed border solid.
- **[closed by #61]** `_draw_text` passes `fill=rgb` (`:636`), ignoring `cmd.opacity` and `run.color.a`.
- `src.thumbnail(...)` (`:726`) never upscales → photo at 300 DPI is ~42% of intended size; 144 DPI ~87%. Baselines at 72 DPI can't catch it.
- No anti-aliasing; Pillow strokes sit inside the edge (PDF/SVG center them); stroke widths rounded to int, min 1 (`:399`).
- Per-pixel pure-Python gradients (`:972`, `:991`): winter-sky 0.75 s @144 DPI, 2.54 s @300 DPI. Full-canvas RGBA layer per translucent shape (~35 MB @300 DPI).
- `preview` (the authoring loop) uses this backend.

### §P7 PDF backend latent bugs — REND F6, F7, F9
- **Status (2026-09-29): quadratic, dash and alpha bullets closed by #62.** `_geometry_to_path` tracks the current point / subpath start (quadratic with no current point raises `ValueError`); `setDash(list(dash), 0)`; every draw with effective alpha < 1 (fill/stroke/text = `opacity × color.a`, image = `opacity`) is scoped in q/Q; `BeginGroup.opacity != 1` raises `NotImplementedError`. Fixtures in `tests/integration/test_pdf_ir_fixtures.py`. Group scale stays with P4-4 / #72.
- Quadratic curves: `reportlab_backend.py:513` looks up `path.contour` (doesn't exist on ReportLab path) → falls back to control point as start. Any user `Q`/`T` renders wrong.
- `setFillAlpha(c.a)` (`:536`) never reset → next fill inherits alpha. `BeginGroup.opacity` ignored; `DrawImage.opacity` ignored (`_draw_image` `:581`); `cmd.opacity` replaces rather than multiplies color alpha.
- Group scale: PDF scales about origin after un-translate (`:206-209`); SVG about pivot (`svg_backend.py:237`); PNG raises (`png_backend.py:329`).

### §P8 Photo pipeline broken [verified in part] — UX F3, REND F2, PRINT P8/P9, SEC P3, ARCH F2
- `cli/commands.py:477-483` builds `ImageElement(width=3.0, …)` with no height; compiler requires both (`core/compiler.py:1434`) → `create <any> -i me.jpg` fails [verified].
- `christmas-photo-ornament` outside `tests/fixtures` fails `Cannot open resource '<cwd>/sample_photo.jpg'`; `validate` says valid. Relative paths resolved against cwd (`core/compiler.py:1442`); `scripts/build_microsite.py` works around with `contextlib.chdir(tests/fixtures)`.
- **Security:** a template with `source_path: /…/secret.env` rendered to SVG embeds the file as `data:application/octet-stream;base64,…` (`svg_backend.py:624-638` reads bytes, MIME from extension). PDF backend rejects it. `validate_image_format` exists (`utils/validators.py:191`, used for CLI at `commands.py:469`) but not in the compiler.
- No effective-PPI check: sample photo is 400 px placed at 3.2" = 125 PPI; MOO/Prodigi expect 300.
- `core/per_panel.py:140` comment "image_elements not yet supported" is stale; moo-a6 leaves images unscaled while surrounding art is scaled ×0.972.

### §P9 PDF/X-1a non-conformance — PRINT P1, P2, P3
- **Transparency:** metallic-ornaments & winter-sky MOO fronts carry ExtGState `/ca`,`/CA` 0.5–0.9 (winter-sky: 32 `gs` ops). Source: `setFillAlpha`/`setStrokeAlpha` `reportlab_backend.py:239,308,567`; CMYK gradient stops keep alpha (`:323,385`). PDF/X-1a forbids.
- **RGB images:** photo MOO front has `/DeviceRGB 400x400 DCTDecode`; `_draw_image` (`:581-590`) passes source through regardless of `color_space`, `mask="auto"`. Tests only regex `rg`/`RG` (`tests/integration/test_pdfx_moo_a6.py:55-56,130`). AI assets are sRGB PNGs → always fail.
- **[Resolved 2026-09-29, #69] Unembedded Helvetica:** every page of every PDF has `/F1 /Helvetica /Type1 embedded=False` used by `/F1 12 Tf` — ReportLab initial font from `Canvas(...)` at `reportlab_backend.py:95`.
- **[Resolved 2026-09-29, #69: `PDF/X-1a:2003` in Info + XMP, XMP dates, `CGATS21-2-CRPC6`] Metadata:** Info dict lacks `GTS_PDFXVersion`/`GTS_PDFXConformance`; XMP declares `PDF/X-1:2001` (`renderers/pdfx_postprocess.py:157`) — should be `PDF/X-1:2003`; XMP lacks Create/ModifyDate that Info has. OutputConditionIdentifier `"CGATS TR 006"` (`pdfx_postprocess.py:88-90`) with a GRACoL2013 profile — registered id is `CGATS21-2-CRPC6`.
- Keep: page boxes (TrimBox inset 9 pt, BleedBox = MediaBox, ArtBox safe area), header 1.4, `/ID`, CMYK shading dicts.

### §P10 Naive CMYK — PRINT P5
- **Status (2026-09-29): resolved by #70.** `rgb_to_cmyk` is deleted; `core/color_management.CMYKConverter` converts sRGB → GRACoL2013 through LittleCMS (relative colorimetric + BPC), caps TAC at 300% (C/M/Y scaled, K kept), prints pure-black text/strokes K-only and pure-black fills ≥ 1 in² as rich black 60/40/40/100. `IRReportLabRenderer(color_space="cmyk")` routes every solid, stroke, text, fold-line, gradient-stop and pattern colour through it with a role. `convert_image` is the seam #71 uses for rasters. `letter` (sRGB) content streams are byte-identical.
- `core/color_management.py:11-18` docstring claims the RIP converts via OutputIntent; for DeviceCMYK it does not.
- Measured through GRACoL: pure blue → naive 100/100/0/0 prints purple (57,54,134), ICC 100/85/0/0; `#CC1C1C` → naive 0/86/86/20 prints orange-brick, ICC 0/100/100/10; black → 0/0/0/100 prints washed-out grey for large areas. ICC black is 84/75/60/100 (TAC 320%) → needs cap.

### §P11 MOO A6 white bands & per-panel scaling — PRINT P4, ARCH F2, F4
- Letter panel 4.25×5.5 vs A6 4.13×5.83; `prepare_scaled_panel` (`core/per_panel.py:123-142`) uses `scale=min(...)` (letterbox); bleed only extends edges touching trim (`core/compiler.py:302-307`) → ~0.24" white top & bottom on every MOO card.
- `core/per_panel.py:105-212` re-implements scaling per domain type and misses: images, SVGPath `x`/`y` (only `scale` multiplied, `:208`), radial-gradient center/radius (panel-relative inches, `compiler.py:904-906`), `stroke_width`, `Border`, pattern spacing, letter/rich-text sizes.
- `render_ir.py:115-127` names `translate_x/y` but backends treat them as rotation pivot; stale "known TODO" comment `compiler.py:246-253`.

### §P12 Test gates too weak — TEST F3, F4, F5, F7; REND F5
- No PDF pixel tests (`grep pdf2image|convert_from_path tests/` → none); PDF gradient tests only assert key presence (`tests/integration/test_gradients_patterns.py:131-158`). `reportlab_backend.py` 66% coverage; pattern fills (`:410-442`, `:456-471`), path/polygon (`:500-522`) never run.
- Visual gate: 64-bit phash @72 DPI, threshold 5 (`tests/visual/test_visual_regression.py:55,62`). Measured distances vs christmas-classic baseline: front text change 6; **all fonts → Lato 6**; inside text removed 8; text at 80% 10.
- Only PNG is visually gated — the least faithful backend.
- Coverage gaps: `cli/commands.py` 66% (`preview` `:659-696`, `init` `:722-805` never run); `core/per_panel.py` 69% (`:185-212`); `core/text_fitting.py` 71% (shrink `:167-199`). No `fail_under`.
- `hypothesis` in dev deps but unused; `test_unsupported_features_raise_loudly` parametrized over empty `SUPPORTED_REJECTING_TEMPLATES = ()` (`tests/unit/test_compiler.py:96,180`) → the suite's one skip; `tests/performance_validation.py` writes `/tmp/perf_test` on import.

### §P13 Backend disagreement — ARCH F3, F7; REND F3, F4
- Patterns: `reportlab_backend.py:356-445`, `png_backend.py:1005-1080`, `svg_backend.py:494-580` each implement tiling. SVG grid draws 2 lines/tile (`svg_backend.py:~552`); SVG checker `half = tile/2` (`:573`) vs PDF `half = spacing` (`reportlab_backend.py:432`); rotation pivots differ; min spacing 0.1 in / 2 px / 2 pt. festive-stripes: `angle: 90` ribbon **missing in PNG** (`rotate(expand=False)` `png_backend.py:1076-1079`), mostly solid in PDF; 45° candy stripes lose corners in PNG/PDF. Pixel diff vs PDF: SVG 15%, PNG 10%.
- SVG fonts: `"font-family": run.font_id` (`svg_backend.py:595`), no `@font-face`, no generic fallback → substituted font is 33% wider than Caveat, 14% wider than Cormorant, 15% narrower than Comfortaa at 18 pt, while line breaks were measured with ReportLab on real fonts. 16 runs across renders still emit `Helvetica`.
- Core depends on renderer package for text measurement: `core/compiler.py:36-37,1599`, `core/text_utils.py:9`, `core/text_fitting.py:18` import reportlab / `renderers.font_registry`; `core/generators.py:30-32` imports all three backends eagerly.

### §P14 CLI structure & authoring loop — ARCH F5, F8; UX F2, F5, F8, F9, F10
- `create()` is `cli/commands.py:192-627` (439 lines) owning voice resolution, message/inside/Markdown/letter/`--blank-inside` precedence, `LetterContent` construction, image placement. `preview` (`:631-697`) only takes `-m/-o/--dpi/--open` yet claims WYSIWYG. `_emit_ir_debug` (`:1144`) handles 5 of ~20 inputs.
- `create tpl/my-card.yaml` (relative, `./`, absolute) → `Error: Template not found` exit 2; `load_template` (`core/templates.py:115-161`) searches only the templates dir while `validate` uses `load_template_from_file` (`commands.py:829`). `init foo` prints next step `holiday-card create foo` which fails; `init` writes `./templates/<occasion>` (`commands.py:725`). `HOLIDAY_CARD_TEMPLATES` replaces (not layers over) built-ins and is undocumented.
- `templates`/`themes` tables show display names ("Classic Christmas") that `create` rejects; IDs only in `--format json`; unsorted; descriptions truncated at 30 chars.
- `create --help`: 18 flat options. `-o` = `--occasion` in `templates/themes/init` but `--output` in `create/preview`; `ai-asset` uses `--out`. Exit 4 = permission error in `create` (`commands.py:623`) but missing key/extra in `ai-asset`. Exit codes undocumented.
- Mutable models: no `validate_assignment`; `letter_content`/`rich_content` exclusivity (`core/models.py:616`) only checked at construction while `core/generators.py:266/280/288` mutate in place; `Card.model_post_init` (`models.py:892`) comment claims "on any change".
- Microsite offers witty/irreverent for `sympathy-spare` (curation says absent); photo pages lack a photo field; `scripts/build_microsite.py:253,328` embeds `json.dumps` in `<script>` unescaped (low risk).

### §P15 Hygiene — ARCH F9, TEST F6, F8, SEC P4, P5, P7, P8, UX F7, PRINT P10
- Dead code (0% coverage, no importers): `core/validators.py` (179 LOC), `utils/gradient_utils.py` (174), `renderers/image_effects.py` (90); 8 of 10 functions in `utils/validators.py`; `TextElement.set_adjustment_result`; `generate_pdf` / `create_and_generate` used only by tests. Stale comments cite deleted `reportlab_renderer.py`/`shape_renderer.py` (`compiler.py:219,383,484`); `_ = SVGCommand` (`compiler.py:598`). CLAUDE.md wrongly says HeartClipMask still exists and svg_parser is "preserved for future" (it is used).
- Docs drift: README example `preview christmas-classic --voice spare` → `No such option: --voice`; `fonts/curated/motif.png` referenced but missing; "Five things" lists six; README says 744 tests, CLAUDE.md 831, collected 832; CLAUDE.md says 17 / 14 templates, actual 21; `--output` help says "PDF"; README lists PNG as a `create` format but `create --format png` exits 2; `--inside-message-md` help stale re bold/italic; `init --occasion` help omits mothers_day + sympathy-class; `init` scaffold uses Helvetica; `specs/004-*/quickstart.md:61` documents nonexistent `generate --template`.
- Release: no git tags, no publish workflow, version hand-edited (`pyproject.toml:7`), nothing checks `--version`.
- CI hardening: `ci.yml` has no `permissions:` block; third-party actions tag-pinned (`render-cards.yml:126,137` `peter-evans/find-comment@v3`, `create-or-update-comment@v4`); fork PRs get read-only token so comment step fails; `check-added-large-files --maxkb=500` would block fonts/ICC.
- Packaging metadata: sdist is 9.4 MB including `data/` (307 unrelated files), `.claude/`, `.specify/`, `.devcontainer/`, `specs/`, `output/`; Python 3.13 classifier missing though CI tests it (`ci.yml:47`); `authors = "Holiday Card Team"`; no `[project.urls]`; `openai>=1.0` uncapped.
- AI sizing: `build_ai_request` for moo-a6 yields 1312×1824; `core/ai_openai.py:48` passes it as `size` to `gpt-image-1`, which (per OpenAI docs; see `docs/industry-review/openai-image-api-snapshot.md`) accepts only 1024², 1536×1024, 1024×1536 — **not tested against live API**. `core/ai_assets.py:205` records returned size without a PPI check.

## 4. What NOT to change (panel consensus)

- The render-IR seam: frozen `extra="forbid"` commands, discriminated union, `assert_balanced` (`core/compiler.py:186`); z-sort/bleed decided once in the compiler.
- `UnsupportedFeatureError` ⊂ `NotImplementedError`; backends refuse unknown commands.
- The injectable `ImageClient` Protocol in `core/ai_assets.py` (AI feature fully testable offline) — reuse the pattern for text measurement.
- `yaml.safe_load` everywhere; SVG built with `xml.etree.ElementTree` (auto-escaping).
- `render-cards.yml` uses `pull_request` (not `_target`) with minimal permissions.
- Deterministic sorted-key IR snapshots + "every template has a baseline" check.
- SVG backend's native paint path — the most correct backend; reference oracle for §P12/§P13.

## 5. Program sequencing (summary — the tracker issue is authoritative)

Phase 0 foundation (§P2, §P1) → Phase 1 correctness today (§P3, §P4, §P5, §P6, §P7)
→ Phase 2 photo pipeline (§P8) → Phase 3 test infrastructure (§P12) → Phase 4 print
production (§P9, §P10, §P11) → Phase 5 backend parity (§P13) → Phase 6 CLI structure
(§P14) → Phase 7 hygiene (§P15, some items parallelisable from Phase 0 onward).

**Why this order:** green CI and a working install gate every other PR; loader and
imposition fixes change baselines, so they land before the gate is tightened;
conformance tests land before refactors (patterns, transforms, per-panel scaling)
that they are needed to verify.

## 6. Working agreements for every issue in this program

- Kickoff: `/goal complete github issue <N> in a TDD manner, do not merge the produced PR until CI is green`.
- Branch `type/kebab-slug` off `main`; PR body `Closes #N`; squash-merge; conventional-commit title.
- Quality gates: `ruff check src/ tests/ scripts/`, `mypy src/`, `pytest` — paste real counts in the PR.
- The repo's committed `.venv` symlink is dead; create a fresh venv (`uv venv` / `python3.12 -m venv`).
- Any visual-baseline or snapshot regeneration: **eyeball every regenerated PNG before committing** — automated regen faithfully captures bugs as truth (see §P3).
- Update CLAUDE.md "Recent changes" and any stale counts touched by the change.

## 7. Amendments — 2026-09-26 (issue-authoring pass)

Issue authors re-verified every anchor while writing the GitHub issues. Where the
findings above were wrong or incomplete, the issue bodies carry the corrected
version; this section records the corrections so the spec stays the source of truth.

- **D11 / §P9:** veraPDF has no PDF/X profile; see the amended D11. **2026-09-29
  (#69):** shipped as `renderers/pdfx_preflight.py` plus the `pdfx-preflight` CI
  job; RGB images are in **5** templates (holiday-masterpiece is one of the 5
  photo templates), transparency in 13. The Info/XMP
  pair for PDF/X-1a:2003 is `GTS_PDFXVersion = "PDF/X-1a:2003"` (ISO 15930-4), not
  `PDF/X-1:2003`; `tests/integration/test_pdfx_moo_a6.py:113` asserts the wrong
  value. Transparency is used by **13 of 21** templates and RGB images appear in
  **6** (5 photo templates + holiday-masterpiece), not just the two named in §P9.
- **§P10:** with black-point compensation (as D9 specifies), `#CC1C1C` →
  0/98/91/12.5 and ICC black → 83.1/74.1/61.2/99.6 (TAC still > 300%).
- **§P2:** the numpy breakpoint is **2.5** (2.4.4 and 2.3.5 pass mypy); numpy 2.5
  needs Python ≥ 3.12, which is why only the 3.12 type-check job breaks. The mypy
  pre-commit pin is on `.pre-commit-config.yaml:9`.
- **§P3:** `christmas-holiday-masterpiece` is confirmed affected (4 SVGPaths).
  `model_validate` needs two YAML aliases: `Line` `x1/y1/x2/y2` and `PatternFill`
  `angle`→`rotation`. `_parse_text_element` also drops `font_style`, `z_index`,
  `rotation`, `font_file`, `paragraph_spacing`; `_parse_panel` drops `border`.
  The compiler independently ignores `TextElement.font_style` (33 uses in 20
  templates, `core/compiler.py:1023`) and text `rotation` — new issue (P1-8).
- **§P4 [closed by #58]:** all 21 shipped templates are 4-panel; 20 use `half_fold` with mirrored
  inside panels, and `christmas-modern` uses `quarter_fold` with a different wrong
  layout. The `init` scaffold (`cli/commands.py:740-790`) omits the 180° rotation.
- **§P5 [closed by #60]:** additional silent ignores — `--signature-font` without `--signature`;
  `--blank-inside --inside-message-md`; `TextElement.font_file` never read;
  `Panel.background_image` parsed but never drawn.
- **§P6 [closed by #61]:** nested PNG clips combine by union, not intersection
  (`png_backend.py:753-756`).
- **§P7 [closed by #62]:** `reportlab_backend.py:551` `setDash(*stroke.dash)` misuses ReportLab's
  signature (1-element dash draws solid; 3–4 elements raise `TypeError`). Stroke
  and text colour alpha are never applied; all alpha bugs are masked today because
  `_color_to_rgba` (`compiler.py:1575-1576`) drops colour alpha.
- **§P8:** the `chdir(tests/fixtures)` workaround exists in six places (microsite,
  baseline regen, render-changed script, three tests); holiday-masterpiece also
  references `sample_photo.jpg`.
- **§P15:** 9 of 10 functions in `utils/validators.py` are dead (not 8). CLAUDE.md
  counts are stale: 16 snapshot files, 70 sentiment files, 21 visual baselines.
  **The package has never been published to PyPI** (`pypi.org/pypi/holiday-card`
  → 404), so the documented `pipx install holiday-card` has never worked. `openai`
  is at 3.x against a `>=1.0` floor. The version string is duplicated in
  `pyproject.toml:7` and `src/holiday_card/__init__.py:3`.
- **§P15 AI sizing:** `docs/industry-review/openai-image-api-snapshot.md:16-23`
  documents **gpt-image-2** with flexible sizes (1312×1824 is valid there); the
  fixed-size claim for gpt-image-1 is unverified. Separately, the live client calls
  `gpt-image-1` (`core/ai_openai.py:34`) while provenance records `gpt-image-2`
  (`core/ai_assets.py:176`, `core/ai_provenance.py:72`) — the sidecar can name a
  model that was never called.
