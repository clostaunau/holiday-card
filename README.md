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

pytest                         # 506 tests, runs in ~6s
ruff check src/ tests/         # lint (zero warnings)
mypy src/                      # strict-mode type-check (zero errors)

holiday-card create christmas-classic --voice warm
```

CI runs all three gates on every push across Python 3.11/3.12/3.13 ×
Ubuntu/macOS, plus a smoke job that renders one template per occasion.
All gates are blocking.

## What this is not

* **Not a Canva replacement.** If you want a visual editor with 600
  fonts and a drag-and-drop photo crop, use Canva. Canva is good at
  what it does. This project is for people who want to commit
  `templates/christmas/family-2026.yaml`, push to GitHub, and have CI
  render the same card every time.
* **Not a print-broker tool yet.** PDFs are RGB; a CMYK / ICC / PDF/X-1a
  pipeline is on the roadmap (Leapfrog 1, slice 2). Today's output
  passes home-printer use and POD first-preflight (e.g. MOO accepts
  RGB PDFs and converts internally).
* **Not finished.** The architecture is solid; the artifact catches
  up template by template, voice by voice, font by font.

## Roadmap

The project's direction is informed by an industry-panel review (six
critics across design, copy, prepress, retail merchandising, POD, and
DIY craft). Read `docs/industry-review/` for the consensus and per-
critic breakdowns. Recent work targets the panel's "1-month" and
"1-quarter" recommendations:

* ✅ Bleed support + `Sheet/Trim/Bleed/Safe` abstraction
* ✅ `--export-for` per-panel POD output
* ✅ Sentiment library + `--voice`
* ✅ Curated fonts shipped + every template migrated
* ⏳ Salutation / signoff / signature / P.S. as first-class fields
* ⏳ CMYK + ICC + PDF/X-1a (Leapfrog 1 polish)
* ⏳ GitHub Action for CI-rendered cards (Leapfrog 4)

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
