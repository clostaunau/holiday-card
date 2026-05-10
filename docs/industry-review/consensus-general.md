# Industry Panel Consensus — holiday-card

## The verdict the six critics would jointly sign

The codebase is genuinely well-architected — a clean IR, three backends, frozen Pydantic models, 324 tests — and the panel is unanimous that the bones are above-average for an open-source project. But the *artifact* the project ships (templates, defaults, output configuration, README) is dramatically misaligned with every audience the project gestures toward. It is sold as a cozy printer-paper utility, built like a print-pipeline framework, populated with engineer-authored templates that do not pass design, copy, prepress, retail-merchandising, or POD-upload muster, and the README is written for a person who would bounce in four seconds while the product is built for a person who would never find it. The project has spent its budget on engineering elegance instead of on the things that would let any of its potential audiences actually use the output. The good news is that almost every fix the panel agrees on is small relative to the architectural foundation already in place.

## Defects (not critiques) — fix these regardless of strategy

These are not opinions. They are wrong and should be fixed before any strategy work.

1. **Half-fold imposition prints the inside text upside-down after folding.** Prepress (sec. "Imposition is broken") confirms: the compiler lays all four panels on a single page (`src/holiday_card/core/compiler.py:135-147`); for a half-fold letter card, the inside half must be rotated 180° (or duplexed) so it reads right-side-up after the fold. The PNG preview shows the inside greeting reading right-side-up *on the flat sheet*, which means it will read upside-down *in hand*. The Designer independently flagged the same effect on `christmas-artist`. **This is a production defect, not a critique.**
2. **The `hanukkah-menorah` template contains no menorah.** Designer and Buyer both flagged: it's the same panel as `generic-celebration` with a navy background and "Happy Hanukkah!" set in Helvetica. The SKU name lies about what's in the file. Mislabeled product.
3. **The `birthday-balloons` template contains no balloons.** Designer flagged. Same defect class as #2.
4. **Mother's Day is filed as `occasion: generic` and lives in `templates/generic/`** (Copywriter, Buyer). It is not a first-class occasion in the data model despite being the second-largest seasonal card-sending day. Reclassification is one line.
5. **CLAUDE.md documents Valentine's templates and a `valentine` occasion that do not exist on disk** (Copywriter explicitly verified `templates/valentine/` is missing; Buyer notes the v2.0.0 Valentine line was deleted in the v1.1.0 refactor). Documentation lies about what ships. Fix doc OR restore templates.
6. **`TextElement.content` does not respect `\n`** — Copywriter verified no `splitlines()` in `text_utils.py` or `text_fitting.py`. Multi-line copy (haiku, address blocks, quoted stanzas) is unrepresentable. `min_length=1` also forbids blank inside copy.
7. **The `RECOMMENDED_DPI = 300` and `MIN_DPI = 150` constants in `measurements.py` are never referenced anywhere** (Prepress grep). Image elements aren't even compiled (`compiler.py:196-200` raises `UnsupportedFeatureError`), so the validation that should exist will not exist when images land.
8. **PDF declares MediaBox==TrimBox==BleedBox==CropBox** (Prepress + POD both verified with `pdfinfo -box`). This is a one-line fix in the renderer and unblocks every downstream POD uploader's preflight.
9. **Fonts are referenced, not embedded** (`pdffonts` confirms `Helvetica … emb=no, sub=no`). Even on home printers this can silently substitute. On any RIP it warns or rejects. The custom-font code path *exists* — the default base-14 path does not embed.

## Cross-cutting agreements (≥3 critics)

### Agreement 1: The shipped templates are aesthetically and linguistically embarrassing relative to the architecture
- **Critics:** Designer, Copywriter, Buyer, DIY Crafter (4/6).
- **The substance:** Eight templates, two fonts (both system defaults), abstract-noun copy that's the same line in eight outfits, geometry-primitive "decorations" that look like pie charts, palettes picked with `r:0.8 g:0.1 b:0.1` syntax. The IR supports gradients, paths, custom fonts, image effects — none of the shipped templates use them. The gap between "what the engine can do" and "what the engine *does*" is the project's central credibility problem.
- **The fix:** (a) commission ~30 hand-illustrated SVG path assets from one illustrator, (b) ship 6–8 curated open-source fonts in `fonts/` and remove Helvetica/Times-Roman from the default chain, (c) rewrite all eight templates against a small layout-pattern library, (d) extract sentiment lines into a voice-tagged library and add `--voice {warm,witty,spare,devotional,irreverent}` to the CLI, (e) add salutation / signoff / signature / P.S. / blank-inside as first-class fields.
- **Cost / time-to-ship:** ~1 quarter of focused work. The illustrator commission and the copy library can run in parallel. Engineering work is small; the cost is curation labor the project has not yet spent.

### Agreement 2: There is no concept of bleed, and it shows everywhere
- **Critics:** Prepress, Designer (sec. "Bleeds and trim marks"), DIY Crafter, POD (4/6).
- **The substance:** The Christmas-classic red flood lands at the trim edge; the codebase has no bleed dimension; templates use trim-coordinates only; the IR has no `BleedBox`. Result: home inkjet shows white slivers at any cutter wobble; POD services hard-reject for "no bleed"; even Sandy can't print on her Pixma without margin.
- **The fix:** Add `bleed` to `Panel`, add a compiler pass that auto-extends `background_color` fills past trim by the bleed amount, set distinct `MediaBox` / `TrimBox` / `BleedBox` in the PDF backend. Single-sprint engineering.
- **Cost / time-to-ship:** ~1 week.

### Agreement 3: The "fold line" lives in the artwork and that is wrong
- **Critics:** Prepress, DIY Crafter, POD (3/6, with the Designer also flagging the same effect indirectly via the upside-down preview).
- **The substance:** `compiler.py:518-520` emits `DrawFoldLine` from x=0 to x=width; the renderer draws a 0.5pt grey dashed line directly on the page. On a home print it's annoying. On a POD upload it becomes content that prints on the finished card. On a commercial RIP it's a defect.
- **The fix:** Gate the fold-line behind `--with-fold-marks`, default off when `--export-for` is not `home`. Ultimately move it to a non-printing layer or a separate `Crease` spot-color separation.
- **Cost / time-to-ship:** ~1 day.

### Agreement 4: One implicit format (US Letter half-fold to 5.5×8.5) is a strategic ceiling
- **Critics:** Buyer, DIY Crafter, POD, Prepress (4/6).
- **The substance:** No POD service sells 5.5×8.5 folded cards. Real card formats are A2, A6, 5×7, square. `measurements.py` collapses sheet/trim/finished-card into one set of letter constants. This single decision walls the project off from indie makers, from POD upload, from premium card stock, from anyone outside one specific home-printer workflow.
- **The fix:** Decouple `Sheet` / `Trim` / `Bleed` / `Safe`. Add `--export-for {home, moo-a6, vistaprint-5x7, catprint-a2, printful-folded, mpix-5x7}`.
- **Cost / time-to-ship:** ~2 weeks for the abstraction; ~1 week per POD target after that.

### Agreement 5: The README sells one audience and the product serves another
- **Critics:** DIY Crafter (entire critique), Buyer (sec. "Who this library actually serves"), Copywriter (implicitly via tonal mismatch), Designer (sec. "The YAML problem") (4/6).
- **The substance:** "small utility to create Holiday cards from regular printer paper" is Sandy-language. `pip install -e ".[dev]"` and `r: 0.98 g: 0.86 b: 0.88` is Tyler-tooling. Sandy bounces in 4 seconds; Tyler reads "small utility" and dismisses it as a toy. Both audiences lose.
- **The fix:** Pick a target persona explicitly. Rewrite the README around that persona's needs, vocabulary, and screenshots-or-it-didn't-happen. (See "The audience question" below for the recommendation.)
- **Cost / time-to-ship:** ~1 day for the README; multi-quarter for the actual product realignment.

### Agreement 6: The IR is good and the architectural foundation is the asset to build on
- **Critics:** Prepress, Designer, POD, DIY Crafter (4/6, all of whom independently praise it after criticizing the artifact).
- **The substance:** `render_ir.py`'s 11-command discriminated-union IR with frozen Pydantic value objects, the inches-as-source-of-truth convention, the compiler that lowers everything to absolute points before backends see it, the `assert_balanced` invariant, multiple backends from one IR — these are the rare and hard part. Every panelist who looked at the code says "the bones are right." This is the foundation every leapfrog move sits on.
- **The fix:** None — protect it. Resist any pressure to bypass the IR for short-term feature shipping.
- **Cost / time-to-ship:** Free; the cost is *discipline*.

### Agreement 7: The SKU mix has the inverse of the actual greeting-card market
- **Critics:** Buyer (extensively), Copywriter (sec. "Cultural / situational sensitivity gaps"), Designer (sec. "Compositionally, every template is the same") (3/6).
- **The substance:** 78% Christmas, 7% birthday in a market where birthday is 60% of unit volume and Christmas is ~15-20%. Zero sympathy, zero thank-you, zero anniversary, zero Father's Day, zero Eid/Diwali/Lunar New Year. One Hanukkah stub that's actually a generic template with the word changed.
- **The fix:** Calendar-driven assortment plan: 3-5 templates per month aligned to that month's actual sending peak. By Dec 2026 the library is 60+ SKUs across the real card calendar.
- **Cost / time-to-ship:** Continuous; this is content work, not engineering.

## Genuine tensions — strategic forks

### Tension 1: Add a visual editor (Sandy) vs. lean into code-first (Tyler)
- **Critics on side A (visual UI):** DIY Crafter (Path A), Designer (sec. "The YAML problem") — both want a web canvas / live preview / color picker / drag-and-drop photo crop.
- **Critics on side B (code-first):** DIY Crafter (Path B!) — explicitly says her honest pick is Tyler. Prepress and POD implicitly assume a CLI/CI workflow. Buyer is neutral on surface.
- **What's at stake:** Whether the next year of work goes into building a thinner, friendlier wrapper around the existing engine, or into doubling down on what makes this project unlike Canva (reproducibility, version control, CI integration, scriptability, "cards as code").
- **The recommendation (with reasoning):** **Lean into Tyler.** Path A asks the project to compete with Canva on Canva's home turf, where Canva is free, excellent, and has 600 fonts. Path B asks it to be the only tool of its kind for a small, devoted, reachable audience that the architecture *already serves*. The DIY Crafter herself, while asking for Path A as a customer, recommends Path B as a strategist. The compromise that the panel would actually endorse is the **template microsite escape hatch**: each template gets one auto-generated single-page web form ("Greeting", "Inside message", "Drop photo here", color pickers, download PDF). That's a weekend's work, captures 80% of Sandy's use case, and does not require building a real visual editor.

### Tension 2: Production-grade prepress (PDF/X-4, CMYK, ICC) vs. POD per-service targets
- **Critics on side A (PDF/X-4, generic prepress correctness):** Prepress (entire critique).
- **Critics on side B (per-service POD targets):** POD (entire critique).
- **What's at stake:** Engineering budget. PDF/X-4 with embedded ICC, OutputIntent, separations, overprint, spot colors, die cuts, foiling layers — that's a multi-quarter prepress engine. Per-service POD targets — A6 with 0.125" bleed, CMYK, MOO-tolerance, per-panel files — is a much smaller surface that gets you 80% of the value for the audiences who actually exist.
- **The recommendation (with reasoning):** **Ship `--export-for moo-a6` end-to-end first**, then template the same work for Catprint, Vistaprint, Printful. The Prepress critic's "real" wishlist (separations, overprint, foil layers, score-vs-crease) is right but enormous and serves a press-broker audience the project does not have. POD compatibility serves indie makers and personal-use customers who *do* exist and *can* be reached. The PDF/X-4 work then arrives naturally as a side effect of doing one POD target completely (CMYK, ICC, embedded fonts, distinct trim/bleed boxes are PDF/X-4 prerequisites anyway).

### Tension 3: Add taste (more curated content) vs. add capability (more occasions/SKUs)
- **Critics on side A (taste):** Designer ("Stop adding features and start adding *taste*"), Copywriter (sentiment library).
- **Critics on side B (coverage):** Buyer (calendar-driven SKU expansion).
- **What's at stake:** Whether the next quarter goes into making 8 templates *great* (illustrator + copywriter + curated fonts + voice library) or into making 30 templates *exist* (covering sympathy, thank-you, Father's Day, Pride, Diwali, etc.).
- **The recommendation (with reasoning):** **Taste first, then coverage.** A library of 30 mediocre templates is worse than 8 great ones — adding more SKUs at the current quality bar deepens the credibility problem. Lift the bar on what's already there (8 templates → 8 *good* templates), then expand. The Buyer's calendar plan becomes the *content production roadmap* once the quality template is established.

### Tension 4: AI-native generation (Designer) vs. handcrafted curation (Copywriter, Buyer)
- **Critics on side A (AI):** Designer (sec. "The leapfrog opportunity" — LLM emits YAML against a curated theme + asset library).
- **Critics on side B (human curation):** Copywriter (handwritten sentiment library), Buyer (merchandised assortment).
- **What's at stake:** Whether the project bets on AI authoring as its differentiator or on human curation as its differentiator.
- **The recommendation (with reasoning):** **Both, sequenced.** The handcrafted layer (illustrator assets, sentiment library, curated fonts, layout patterns) IS the moat that makes AI authoring valuable. ChatGPT can write YAML against any schema; what it cannot do is have taste. A curated asset/copy/font library *plus* an LLM authoring harness against it is the right end state. But the human curation has to come first — without it, the LLM has nothing to compose from. Sequence: curation in Q3, LLM harness in Q4.

## The audience question

**The current product is for the engineer-author.** The README pretends otherwise. The Buyer's persona profile (a solo engineer making one Christmas card per year for a personal mailing list) is exactly right and matches what every other critic independently observed. The Designer says it. The Copywriter says it. The DIY Crafter says it explicitly: "This tool is for my nephew Tyler."

**Going forward, the recommendation is: stay Tyler-first, with a one-screen escape hatch for Sandy.**

Why:
- The architecture is already aligned with Tyler. YAML-as-source-of-truth, IR/compiler/backend split, CLI, CI matrix, MIT license, GitHub-first distribution — these are Tyler's love language and they are sunk costs that would be wasted by pivoting to a Canva-likeness.
- The Tyler audience is small but *unserved*. There is no other tool that does "version-controlled, CI-rendered, reproducibly-built greeting cards as code." Canva and Minted will not build it because the audience is too small to monetize.
- The Sandy audience is large but well-served by Canva, Cricut Design Space, and Shutterfly. Competing there is a five-year, hundred-person project the maintainer has neither the time nor the budget for.
- The Sandy escape hatch (template-microsite web form per template) is small, cheap, and lets a non-engineer touch the engine without the project pretending to be Canva.

**Is the architecture aligned with Tyler?** Yes. The IR is exactly the right shape, the YAML schema is exactly the right input format, the multi-backend output is exactly the right capability. The README is misaligned and the templates are misaligned — but the *code* is correctly built for the audience the panel recommends.

**The one architectural gap:** the imposition decision. The current renderer imposes for one specific output (letter half-fold). Tyler-the-engineer who wants to send to MOO needs the imposition to be *configurable per target*. The POD critic's `--export-for` proposal is the right shape and matches Tyler's mental model (declarative target → correct output) better than Sandy's (visual editor → see-what-you-get).

## The five leapfrog moves the panel jointly endorses

Ranked by panel-wide endorsement strength.

### Leapfrog 1: `--export-for` POD targeting, ship MOO-A6 end-to-end first
- **Endorsed by:** POD (primary), Prepress (subset of his wishlist), Buyer (positions for indie maker market), DIY Crafter (Path B item), Designer (implicit — proper bleed and CMYK).
- **The moat:** No open-source greeting-card generator today produces a file you can drop into MOO and have it accepted on first preflight. None. The project ships one YAML and gets a press-ready file at any of six target services without manual intervention. That's a category-defining capability.
- **Why no incumbent ships this:** Hallmark Card Studio costs $80, doesn't do CMYK, and won't integrate with MOO. Canva does its own printing and won't help you go to a competitor. Adobe expects you to design from scratch. Minted is a marketplace, not a tool. The intersection of "open-source", "POD-correct output", and "templated" is empty space.

### Leapfrog 2: Curated taste layer — illustrator commission + sentiment library + 6-8 curated fonts
- **Endorsed by:** Designer, Copywriter, Buyer, DIY Crafter (all 4 of the non-engineering critics).
- **The moat:** The combination of (a) hand-illustrated SVG path assets, (b) voice-tagged sentiment library with `--voice {warm, witty, spare, devotional, irreverent}`, (c) 6-8 curated typefaces with display/body/script pairings — is the only way to escape "looks like an engineer made it." Every template gains it for free; every future template starts at a higher quality bar.
- **Why no incumbent ships this:** Canva curates fonts but not voice. Hallmark curates copy but not as a `--voice` flag. Em & Friends curates voice but doesn't open-source it. The combination, exposed as a *programmable* surface, is novel.

### Leapfrog 3: AI-native authoring against the curated asset library
- **Endorsed by:** Designer (primary), Copywriter (implicitly — voice tags are LLM-friendly), DIY Crafter (Path B's "cards as code" aesthetic).
- **The moat:** "User types a brief; gets a card." `holiday-card create --brief "art-deco Hanukkah card for my Bubbie, copper foil accents, body in Cormorant"` → 6-second render. The IR is constrained enough that an LLM cannot hallucinate impossible primitives. The illustrator's hand provides the soul; the LLM provides the variety.
- **Why no incumbent ships this:** Minted's moat IS curation, and they cannibalize their designers if they ship this. Canva's primitives are bitmap, not vector path. Figma has the primitives but no illustration moat or personalization engine. This is the leapfrog that would put the project on Hacker News.
- **Critical dependency:** Leapfrog 2 must come first. Without the curated assets, the LLM produces ChatGPT-aesthetic slop.

### Leapfrog 4: Cards-as-code identity — GitHub Action, CI-rendered, blank-inside mode, multi-line copy
- **Endorsed by:** DIY Crafter (Path B explicitly), Copywriter (multi-line + blank-inside), implicitly Prepress (CI-suitable architecture).
- **The moat:** A GitHub Action that auto-renders cards from YAML on every push, posts the PNG as a PR comment, and on release tags emails the PDF to a configured mailing list. "Christmas letter mode" where Markdown composes into the inside panel with proper typography. Reproducible builds for greeting cards.
- **Why no incumbent ships this:** Canva can't because it's a SaaS with a GUI. Minted can't because it's a marketplace. Hallmark can't because they don't ship developer tooling. This is the move that makes Tyler's demographic evangelize the project.

### Leapfrog 5: Template microsite — auto-generated single-page form per template
- **Endorsed by:** DIY Crafter (Path A's narrow version), Designer (sec. "A pragmatic middle ground").
- **The moat:** Every template auto-generates a static single-page form: greeting field, inside message field, photo drop, color pickers, "Download PDF" button. Hostable on GitHub Pages from the same repo as the templates. Customer never touches YAML.
- **Why no incumbent ships this:** Because the *engine* doing it is open-source and the *templates* are forkable. Anyone can host their own family card site. Canva can't ship that because their business is selling subscriptions to the editor itself.

## Sequencing: 1 week / 1 month / 1 quarter / 1 year

Assuming one engineer working part-time.

### 1 week (defects + quick wins)
- Fix the **upside-down inside text** half-fold imposition (Defect 1) — this is a production defect and should ship before anything else.
- Set distinct **MediaBox / TrimBox / BleedBox** in the PDF backend (Defect 8).
- Embed and subset Helvetica/Times-Roman in the default font path (Defect 9).
- Drop `min_length=1` on `TextElement.content`; add `splitlines()` handling (Defect 6).
- Reclassify Mother's Day to its own occasion (Defect 4).
- Resolve the CLAUDE.md/Valentine discrepancy (Defect 5) — either restore the templates or remove the documentation.
- Gate `DrawFoldLine` behind `--with-fold-marks` (Agreement 3).
- **Rewrite the README** to pick a persona explicitly (Agreement 5). Add "Holiday cards as code" subhead, screenshots of actual rendered cards, install instructions for Tyler-the-engineer (`pipx install`, not `pip install -e ".[dev]"`).
- Rename or rebuild `birthday-balloons` and `hanukkah-menorah` to either contain what they claim or stop claiming it (Defects 2, 3).

### 1 month (Agreement 2 + start of Agreement 1)
- **Bleed support**: add `bleed` to `Panel`, compiler pass to extend background fills, distinct PDF boxes (Agreement 2).
- **Curated font shipment**: 6-8 open-source fonts in `fonts/`, removed from default fallback (Agreement 1, font subset).
- **Sentiment library v0**: extract inline copy into `sentiments/{occasion}/{voice}/{cover|inside}.yaml`; add `--voice` and `--blank-inside` CLI flags (Agreement 1, copy subset).
- Add **salutation, signoff, signature, P.S.** as first-class fields (Agreement 1, Copywriter expansion).
- Sheet / Trim / Bleed / Safe abstraction in `measurements.py` (prerequisite for Leapfrog 1 + Agreement 4).

### 1 quarter (Leapfrog 1 + complete Agreement 1)
- **Illustrator commission**: 30 hand-drawn SVG path assets (Agreement 1, asset subset). Two weeks of one illustrator's time.
- **Rewrite all eight shipped templates** against the new fonts + assets + sentiment library + layout patterns (Agreement 1).
- **`--export-for moo-a6` ships end-to-end** (Leapfrog 1): A6 trim, 0.125" bleed, CMYK, embedded GRACoL ICC, PDF/X-1a, per-panel files, validates against MOO preflight.
- **Template microsite generator** (Leapfrog 5): static single-page form per template, hostable on GitHub Pages.
- Fix Hanukkah and Birthday templates so they contain what they're named for; add Father's Day; restore Valentine's (Agreement 7 first wave).

### 1 year (Leapfrogs 2, 3, 4 + Agreement 7)
- **`--export-for` for Catprint, Vistaprint, Printful** (Leapfrog 1 expansion).
- **Calendar-driven SKU expansion**: ship 3-5 new templates monthly aligned to the actual card calendar — sympathy, thank-you, anniversary, Pride, Juneteenth, Diwali, Lunar New Year, Eid (Agreement 7).
- **GitHub Action + Christmas letter Markdown mode** (Leapfrog 4).
- **AI-native authoring harness** against the curated library (Leapfrog 3) — `holiday-card create --brief "..."`.
- **Voice library expansion**: hire a copywriter for one focused week to triple the sentiment count.
- **Photo card primary use case**: build templates that actually use the heart-clip + image effects + frame styles, since 70% of premium card volume is photo cards.

## What the panel would warn against

1. **Building a full visual editor** to chase Sandy. Designer, DIY Crafter (Path B), and the shape of the architecture all say this is a Canva-clone trap. The narrow microsite escape hatch is fine; a real WYSIWYG is a multi-year, multi-engineer project that competes with free, excellent products.
2. **Adding more occasions before the existing ones are good.** Buyer wants 60 SKUs by December; Designer says "stop adding features and start adding taste." The Designer wins this argument: 30 mediocre templates makes the credibility problem worse, not better.
3. **Refactoring the IR again.** Wave 2 already shipped. Every critic who looked at the code praised it. Resist the temptation to do another architectural pass before the *artifact* catches up to the architecture.
4. **Shipping more renderer features (foiling, embossing, separations) before bleed and CMYK exist.** Prepress's wishlist is correct but enormous; Smartpress-grade prepress serves a press-broker audience the project does not have. Bleed + CMYK + PDF/X-1a for one POD target serves audiences who do exist.
5. **Adding new file formats** (Risograph, letterpress, die-cut SVG) before any of the existing formats produces a POD-acceptable file. Format proliferation without preflight correctness is feature theater.
6. **Treating the README as marketing copy** ("small utility for printer paper") when the product is an engineering framework. The mismatch is actively harmful — it both turns away the reachable audience and misleads the wrong one.
7. **Deleting functioning SKUs in the name of architectural cleanup**, the way v1.1.0 deleted the Valentine's line. The Buyer's "$400M-category own goal" framing is harsh but earned. SKU deletions need a buyer's review before they ship.
8. **Pretending CLAUDE.md is documentation when it's a wishlist.** Either the documented features ship or the documentation is removed. The current state — "documents Valentine's templates that don't exist" — erodes trust in every other claim in the file.

## Single sentence to a maintainer who will only read one line

The architecture is genuinely above-average and the artifact is genuinely embarrassing — spend the next quarter on taste (illustrator + sentiment library + curated fonts + bleed) and one POD target end-to-end (`--export-for moo-a6`), not on more features, more refactors, or more SKUs at the current quality bar.
