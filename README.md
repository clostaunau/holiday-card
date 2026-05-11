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
renders it in Playfair Display + Cormorant, exports as a US Letter
imposition with 0.125" bleed, and saves a PDF you can drop on your
home printer or hand to a press.

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
* **Voiced greetings ship with the project** — 250 hand-tagged
  sentiments across 5 voices and 5 occasions, picked via `--voice`

## Install

```bash
pipx install holiday-card        # the canonical install
# or, for development:
pip install -e ".[dev]"
```

## Five things you can do today

```bash
# 1. Pick a voice and let the sentiment library write your card
holiday-card create christmas-classic --voice irreverent --seed 7

# 2. Set your own message; pick the typeface via the template
holiday-card create christmas-classic -m "Merry Christmas, Sarah" \
  --inside-message "Hope this year is gentle to you both."

# 3. Export per-panel files for a POD service
holiday-card create christmas-classic --export-for moo-a6 -o ./moo/
# → ./moo/{front,back,inside-left,inside-right}.pdf at A6 trim + 0.125" bleed

# 4. Skip the printer dialog — preview as PNG
holiday-card preview christmas-classic --voice spare

# 5. Render a card from a template you wrote yourself
holiday-card create ./my-template.yaml -o my-card.pdf

# 6. Christmas-letter mode: write the inside as Markdown
holiday-card create birthday-balloons --inside-message-md letter.md
# Where letter.md contains paragraphs with **bold** spans and hard
# line breaks. Renders into the inside panel with proper paragraph
# spacing.
```

## What ships in the box

| Layer | What's in it |
|---|---|
| **Templates** | 8 ship-quality templates (Christmas, Hanukkah, Birthday, Mother's Day, Generic) + 6 demo templates (gradient/pattern features, currently uncompilable) |
| **Voices** | warm, witty, spare, devotional, irreverent — pick via `--voice` |
| **Sentiments** | 250 hand-tagged copy lines across 5 occasions × 5 voices × 2 roles |
| **Fonts** | 6 curated SIL OFL families (Cormorant Garamond, Playfair Display, Lato, Inter, Caveat, Comfortaa) embedded in every PDF |
| **POD targets** | `letter` (single imposed sheet), `per-panel-pdf` (native trim per panel), `moo-a6` (A6 with content scaled to fit) |
| **Output formats** | PDF (default), SVG, PNG |

## Hacking on it

```bash
git clone https://github.com/clostaunau/holiday-card.git
cd holiday-card
pip install -e ".[dev]"

pytest                         # 555 tests, runs in ~6s
ruff check src/ tests/         # lint (zero warnings)
mypy src/                      # strict-mode type-check (zero errors)

holiday-card create christmas-classic --voice warm
```

CI runs all three gates on every push across Python 3.11/3.12/3.13 ×
Ubuntu/macOS, plus a smoke job that renders one template per occasion.
All gates are blocking.

A second workflow (`.github/workflows/render-cards.yml`) renders PNG
previews of templates affected by every PR and posts them as a sticky
PR comment. Reviewers see what the change does to the actual cards
before merging — the "cards-as-code" identity move from Leapfrog 4
of the panel review.

## What this is not

* **Not a Canva replacement.** If you want a visual editor with 600
  fonts and a drag-and-drop photo crop, use Canva. Canva is good at
  what it does. This project is for people who want to commit
  `templates/christmas/family-2026.yaml`, push to GitHub, and have CI
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
* ⏳ Illustrator commission: ~30 hand-drawn SVG path assets (Leapfrog 2 final slice — needs a human)
* ⏳ Italic font variants (extends Markdown mode beyond bold)
* ⏳ Multi-panel spill for long Markdown letters
* ⏳ Father's Day + sympathy templates (calendar-driven SKU expansion)
* ⏳ Template microsite generator (Leapfrog 5 — single-page form per template)
* ❌ AI-native authoring (Leapfrog 3) — explicitly deferred per the AI-feature consensus doc until the curation moat is wider

## Architecture

`Card → compile_card → list[RenderCommand] → Renderer → file`. Three
backends share the same compiler: `IRReportLabRenderer` (PDF, default),
`SVGRenderer`, `PNGRenderer`. Adding a fourth backend is the same
~330-LOC pattern. See [CLAUDE.md](CLAUDE.md) for the architectural
walkthrough.

## License

MIT (see [pyproject.toml](pyproject.toml)). Bundled fonts in
`fonts/curated/` are SIL OFL 1.1 — the OFL.txt for each ships next
to the TTFs.
