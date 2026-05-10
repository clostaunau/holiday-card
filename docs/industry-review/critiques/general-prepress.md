# Prepress Production Critique — holiday-card

## Verdict in one sentence
This is a competent **screen-preview / home-printer** PDF generator masquerading as a card production tool — it has none of the prepress metadata, color management, or imposition discipline that any commercial printer would require, and the "fold guide" it does emit will print on the customer-facing artwork.

## What this output is actually suitable for
**Tier 1 — Home inkjet only**, and even that with reservations.

Reasoning:
- No bleed: any commercial trimming step will produce white slivers along the flooded edges (`templates/christmas/classic.yaml:15-22` puts the red panel hard at x=4.25 with width=4.25 — i.e. flush to the trim).
- No CMYK / no ICC / no OutputIntent (`pdfinfo` shows the catalog has no `/OutputIntents`; the file declares no color profile). Any RIP that demands PDF/X-1a or X-4 (standard for offset and most digital presses) will reject it on submission.
- Fonts not embedded — only the Type1 base14 names `Helvetica` and `Times-Roman` are referenced (`pdffonts /tmp/critique_pdf.pdf` confirms `emb=no, sub=no`). Most commercial RIPs preflight-fail on this; some will silently substitute and you will discover it on the proof.
- The visible "fold line" is part of the artwork on the front face (`src/holiday_card/core/compiler.py:520`, `src/holiday_card/renderers/reportlab_backend.py:325-332`). On a home printer that's annoying; on a commercial digital press it's a defect.
- Imposition is wrong for a duplex/folded card (see show-stoppers below).

A home inkjet user who folds the page in half and accepts a 0.5pt grey dashed line bisecting their card can use this. Anyone else cannot.

## Issues found (ranked by severity, with file:line evidence)

### Show-stoppers for any production beyond home printing

**1. No bleed. None. Anywhere.**
- `src/holiday_card/utils/measurements.py:8-12` defines `PAGE_WIDTH=8.5` and `PAGE_HEIGHT=11.0` — the *trim* size. There is no separate bleed dimension and no concept of an "extends beyond trim" region.
- `templates/christmas/classic.yaml:15-22` places the red flood panel exactly at the trim edge. There is no instruction (and no IR primitive) telling the renderer "extend this fill 0.125 inches past the cut".
- Industry standard for greeting cards is **0.125" bleed** (Hallmark, Vistaprint, Moo, Printful all spec this). With nothing here, every flooded design will show white at the trim under normal cutter tolerance (±1/32" to ±1/16").

**2. The "fold line" is printed artwork, not a prepress mark.**
- `src/holiday_card/core/compiler.py:518-520` emits a `DrawFoldLine` from x=0 to x=width — i.e. **edge to edge across the live area**.
- `src/holiday_card/renderers/reportlab_backend.py:325-332` draws it as a 0.5pt 3-on/3-off grey dash directly on the page.
- The visible PNG render (`/tmp/critique_xmas-1.png`) shows the dashes cutting cleanly through the red flood. This will print on the final piece.
- Real prepress practice: fold marks live in the **margin outside the trim box**, are short tick marks, and are stripped off (or moved to a non-printing layer) before plating. Better still, scoring lives in a separate die file or a `/PieceInfo` instruction to the press, not in the artwork.

**3. The PDF declares no MediaBox/BleedBox/TrimBox/ArtBox distinction.**
- `pdfinfo -box /tmp/critique_pdf.pdf` shows all four boxes identical at `[0 0 612 792]`.
- PDF/X (and any preflight-driven RIP workflow) **requires** TrimBox to be present and distinct from MediaBox when bleed is used. Without it, the press operator has no machine-readable "where do I cut" signal.

**4. Imposition is broken for a half-fold card.**
- The compiler lays all four panels (front, back, inside-left, inside-right) on a **single page** (`src/holiday_card/core/compiler.py:135-147`).
- For a half-fold letter card folded along the 5.5" centerline, the top half of the sheet becomes the *inside* when folded. For inside text to read right-side-up after folding, the top half of the printed sheet must be **rotated 180°** relative to the bottom half — OR the inside must be printed on the *reverse face* of the sheet (duplex), with its own page in the PDF.
- Neither is happening. The rendered PNG shows "Wishing you joy and happiness this holiday season!" reading right-side-up on the printed page, which means when the user folds bottom-half-up to make a card, the inside greeting will be **upside down**.
- This is the kind of defect that gets caught in pre-flight visual inspection at any real card printer and the file gets bounced back same day.

**5. No color management. Everything is uncalibrated DeviceRGB.**
- `src/holiday_card/core/render_ir.py:97-103` defines color as RGBA only. There is no CMYK channel, no spot color (PANTONE/PMS), no overprint flag.
- `src/holiday_card/renderers/reportlab_backend.py:266, 280` calls `setFillColorRGB` / `setStrokeColorRGB` exclusively.
- The PDF has no `/OutputIntent` and no embedded ICC profile.
- The Christmas red `(0.8, 0.1, 0.1)` (`templates/christmas/classic.yaml:19-22`) will look very different on a home inkjet vs a commercial press vs a customer's monitor, and the file gives the press no information to do anything about it. On an offset job that 80% R / 10% G / 10% B is going to convert to roughly C20 M95 Y95 K10 — a flat, dirty red. A real Christmas-red call would be a spot like PMS 200 C or a known build like C0 M100 Y65 K15.

### Issues for prosumer / Etsy / small-batch (Tier 3 digital, Vistaprint-grade)

**6. Fonts are referenced, not embedded.**
- `pdffonts` output: `Helvetica … emb=no, sub=no`. ReportLab is using the PDF base-14 fallback path because no font file was registered for these names.
- Acrobat preflight will warn; most modern RIPs will substitute (often with subtle metric differences that re-flow your wrapped text); a few strict CMYK workflows will reject. This was the right design when PDF 1.3 shipped in 1999; it is wrong in 2026. Always embed and subset.
- The Wave 2 valentine release added custom font support (`fonts/` directory, `font_file` in YAML), but the IR's `TextRun.font_id` is just an opaque string — there is no embed/subset instruction propagated into the PDF.

**7. PDF version is 1.3 (Christmas) and 1.4 (Mother's Day).**
- PDF/X-1a:2001 minimum is PDF 1.3, but it requires CMYK-only color, embedded fonts, OutputIntent, no transparency. We have none of those.
- PDF/X-4 minimum is PDF 1.6. We can't get there from here without significant work.
- The version is being chosen by the *content* (whether ReportLab needed an ExtGState for transparency) rather than declared explicitly.

**8. No producer/author/creator metadata that means anything.**
- `pdfinfo` shows `Author: anonymous, Creator: anonymous`. The `SetMetadata` IR command (`src/holiday_card/core/render_ir.py:329-337`) only knows two keys (`template_id`, `theme_id`) and the ReportLab backend silently drops everything else (`reportlab_backend.py:120-126`).
- Production tracking (job ID, brand, customer, lot) cannot be threaded through to PDF metadata or XMP.

**9. No DPI assertion on raster images.**
- `MIN_DPI: 150` and `RECOMMENDED_DPI: 300` are defined in `measurements.py:21-23` but **never used** (a grep finds no references). Image elements aren't even compiled yet (`src/holiday_card/core/compiler.py:196-200` raises `UnsupportedFeatureError`).
- When images do land, there is no validation that a 72-DPI screenshot dragged in by a designer will look terrible at 300-DPI print.

**10. No total area coverage (TAC / TIC) check.**
- Even if CMYK conversion existed, there's no concept of "total ink coverage cannot exceed 240% on uncoated, 300% on coated." A user picking #000000 backgrounds will produce 400% TAC and the press will reject it for offset (and produce a leathery, never-drying mess on digital).

### Issues only when scaling to commercial volume

**11. No spot colors, no overprint, no traps.**
- Card lines that need consistent reds across the run (Hallmark-style) need PANTONE specification, not RGB.
- The IR has no `OverprintPaint` or `Knockout` mode for fine-tuning when fills meet (e.g. small black text on a red panel — should overprint to avoid trap registration issues; without overprint you'll see haloing on misregister).
- No trap commands: where two adjacent CMYK builds meet, the prepress operator usually adds a 0.144pt overlap. The IR cannot express this.

**12. No stock / paper instructions in the file.**
- Greeting cards are typically printed on 100lb-130lb cover (270-350 gsm). Nothing in the file or the YAML says so. A commercial print broker will quote on assumption; a sloppy one will print on text weight and your card will droop.
- No grain-direction instruction. Half-fold cards crack along the fold if the grain runs perpendicular to the fold line. The renderer does not know this concept exists.
- No score-vs-crease instruction. The IR's `DrawFoldLine` says "draw a dashed line at this position" — that's a *visual indicator*, not a *finishing instruction*. A real RIP submission needs either a separate die file or a `/PieceInfo` dictionary entry naming the score line in points.

**13. No die-cut / shape instructions.**
- All cards are rectangular. There is no IR primitive for "cut along this path" (which would be a separate spot color, conventionally named `Die` or `CutContour`, set to overprint and 100% magenta-tagged for press operators).

**14. No foiling / embossing / spot-UV layers.**
- Greeting cards from any premium line (Papyrus, Hallmark Signature) lean heavily on these finishing techniques. They are conventionally encoded as additional spot-color separations in the PDF (e.g. a `Foil_Gold` spot at 100% wherever foil should land). The IR has no separation concept.

**15. No imposition / step-and-repeat / nesting.**
- Real card printing is N-up on a 19x25 or 23x29 sheet to amortize plate cost. The renderer outputs one card per PDF. That is fine — most prepress pipelines impose downstream — but you have made it impossible to produce a useful **PDF/X-4 sheet-imposition-ready file** because there's no trim box for the imposition tool to anchor on.

## What needs to change in the IR

Concrete additions to `src/holiday_card/core/render_ir.py`:

1. **`BeginPage` needs box geometry**, not just one width/height:
   ```python
   class BeginPage(_IRBase):
       media_box: RectGeom    # paper size
       trim_box: RectGeom     # finished card after cut
       bleed_box: RectGeom    # trim + 0.125"
       art_box: RectGeom | None = None  # safe area
   ```

2. **A real color model with multiple spaces:**
   ```python
   class CMYKColor(_IRBase):
       c: float; m: float; y: float; k: float
   class SpotColor(_IRBase):
       name: str  # "PANTONE 200 C"
       fallback: CMYKColor  # for proofing
       tint: float = 1.0
   Color = Annotated[RGBA | CMYKColor | SpotColor, Field(discriminator="space")]
   ```

3. **`SetOutputIntent` command** to attach an ICC profile (e.g. GRACoL2013 for US sheetfed, FOGRA51 for European) and force PDF/X-4 catalog flags.

4. **A `MarkType` enum + `DrawMark` command** for trim marks, registration marks, color bars, and folding marks — explicitly *outside* the bleed box, so they get stripped automatically when the imposition tool clips to bleed.

5. **`ScoreLine` / `Perforation` / `DieCut` commands** — separate from `DrawFoldLine`. These produce no visible ink; they emit overprint-flagged spot-color paths on a named separation (`Crease`, `Die`, etc.) per the GWG (Ghent Workgroup) spec.

6. **`OverprintFill` / `OverprintStroke` flags on `DrawShape`** for trap-friendly black text on color.

7. **A finishing layer**: `BeginSeparation(name="Foil_Gold") … EndSeparation`. Whatever paths are drawn between go on a spot-color plate.

8. **Font embedding directives** propagated through `TextRun`:
   ```python
   class FontRef(_IRBase):
       family: str
       file: Path  # absolute path to TTF/OTF
       embed_mode: Literal["subset", "full"] = "subset"
       license: Literal["embeddable", "preview-only", "no-embed"]
   ```
   The renderer should refuse to write a PDF that references a font with no embed instruction.

9. **`PageRole` enum** on `BeginPage`: `front_face`, `back_face`. Half-fold cards should compile to **two pages** (outside / inside), not one. The compiler should also emit the correct rotation for the inside-left / inside-right positions so they read right-side-up after folding.

10. **A preflight pass** that runs before the renderer: enforce TAC limits, image DPI, font embedding, bleed coverage, safe-area compliance.

## What needs to change in the templates

Template authors should be writing things like:

```yaml
trim_size: { width: 5.5, height: 8.5 }   # finished folded size
bleed: 0.125
safe_margin: 0.25
fold_type: half_fold

color_space: cmyk           # or spot
output_intent: GRACoL2013

panels:
  - position: front
    background:
      color:
        type: spot
        name: "PANTONE 200 C"
        fallback_cmyk: { c: 0, m: 100, y: 65, k: 15 }
      bleed: full           # extend fill into the bleed region
    # ...

finishing:
  - type: score
    line: fold_centerline
  - type: foil_stamp
    color: gold
    region: { type: path, ops: [...] }  # logo
```

In other words: every coordinate the designer writes today is in *trim* coordinates; the system needs a separate *bleed* coordinate concept and the templates need to be rewritten so background fills explicitly extend to bleed.

## What's surprisingly good

**Be fair — this project gets several things right:**

1. **The IR/compiler/backend split is genuinely good architecture.** The `render_ir.py` 11-command IR with a discriminated union is exactly the right shape for adding the prepress concepts above without touching the backends each time. Most commercial card-design tools (looking at you, certain Adobe products from the 2000s) did NOT do this and paid for it.

2. **`assert_balanced` is excellent.** Catching unbalanced `BeginGroup`/`EndGroup` at compile time, rather than discovering corrupted state on a press, is the kind of invariant that real printer software re-implements at every layer because somebody downstream forgot it.

3. **The compiler lowers everything to absolute points before the backend sees it** (`src/holiday_card/core/compiler.py` line 132 `inches_to_points` calls). This is the same discipline used by real RIPs (PostScript → flattened display list). Means you can re-target SVG/PNG/print drivers without re-litigating coordinates.

4. **`_FOLD_LINE_GREY = (0.7, 0.7, 0.7)` and `setLineWidth(0.5)`** is at least a *deliberate hairline*, not a 1pt black line. Whoever wrote that has seen a fold line ruin a card before. They picked the right values; they just put the line in the wrong place.

5. **Frozen, immutable value objects with Pydantic validation** is a great call. Bleed and TrimBox additions will inherit that strictness for free.

6. **Per-shape paint/stroke** (rather than canvas-wide setter state) is correct. The legacy ReportLab API is built around setter-state and it's a constant source of "I forgot to reset the fill color and now everything is purple" bugs.

## The leapfrog opportunity

**Ship a `--print-ready` flag that emits a real, preflight-passing PDF/X-4 file with bleed, crop marks, embedded subset fonts, an ICC profile, distinct TrimBox/BleedBox, and correct two-page imposition for the fold type — and have the IR/compiler refuse to compile if the template doesn't supply bleed and CMYK colors.**

Right now, this project competes with "draw a card in Figma, export PDF, hope for the best." If it shipped the above, it would compete with **commercial card-design tools at the prosumer end** (think: a Python alternative to Hallmark Card Studio's export pipeline, or a CLI you could plug into a print-on-demand fulfillment pipeline). Getting one card design from YAML to a Vistaprint-uploadable PDF/X-4 with bleed and crop marks — *unattended, in a CI job* — is something you literally cannot do with any open-source tool today without manually wrangling Scribus or reportlab + pikepdf hacks.

The IR already has the right shape to do this. The compiler is where 80% of the work lives (insert bleed-extension, generate marks outside the trim, route fold lines to a non-printing layer, split half-fold into two pages with the inside-page rotation). The ReportLab backend gets a few additional command handlers (OutputIntent, Separation, OverprintFill). One careful month of work and this becomes the only Python tool that can produce a press-ready greeting card from a YAML file.

The other 19 things on this list are nice-to-haves. **That one is a category-definer.**
