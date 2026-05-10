# Greeting Card Designer Critique — holiday-card

## Verdict in one sentence
These look like the kind of thing a competent backend engineer makes when the marketing team asks for "Christmas cards by EOD" — the layouts are technically valid, the geometry is correct, and not one of them would survive ten seconds on a Minted shelf.

## What I'd say if a junior designer brought me these cards

**christmas-classic** — This is a solid red rectangle with the words "Merry Christmas!" set in Helvetica. That isn't a card; it's a fire-exit sign with a sentiment. The greeting is bottom-aligned in the panel for no reason. The red is #CC1A1A — the *blood* red of warning labels and clearance stickers, not the brick/cranberry/mulled-wine red of Christmas. Nothing is on the front but a flat color and one word. A blank red index card would convey roughly the same emotional content.

**christmas-geometric** — The strongest of the bunch and still a problem. The earth-tone palette (sage, terracotta, teal, gold) is genuinely nice — it reads as 2018 Pinterest "modern Scandi Christmas" and that's a real aesthetic. But: the tree is three opaque triangles snapped together with visible seams; the "ornaments" are perfect-circle dots that read as pie chart fragments, not blown glass; the gift box is two flat rectangles (no ribbon, no perspective, no shading); the star topper is the same five-pointed primitive used for the corner stars at 2x size, which is amateur-hour — a tree-topper should be a different *form*, not just a bigger version of the confetti. Also, the body copy "Merry Christmas!" is sitting *under* the tree, not above it. Read order on a card is top-to-bottom; you're burying your headline.

**christmas-modern** — Forest-green panel + yellow Helvetica "Season's Greetings." The yellow on dark green is the John Deere tractor palette, not a holiday card. There is *literally nothing on the front* except a color block and a phrase. A first-year design student would be sent back to the drawing board.

**christmas-artist** — A geometric cartoon of an easel surrounded by floating colored dots. The metaphor (easel = "artist") is heavy-handed. The "paint palette" is a beige circle with five dots in it; the pencils are colored rectangles with triangle tips. Whimsy is fine, but whimsy without craft is just clip art. And on the inside panel, the rotated message reads UPSIDE-DOWN in the preview render — that's not a design problem, that's the renderer correctly previewing the page-as-printed, but a designer would want to see it as it'll actually be *read* (post-fold) and you're not giving them that.

**birthday-balloons** — There are no balloons. The front is a soft lavender rectangle with "Happy Birthday!" in purple Helvetica. The file is *named* "balloons" and there are no balloons. That's a brutal indictment.

**hanukkah-menorah** — There is no menorah. Royal blue panel, white Helvetica. The blue is right (#054A91 is in the right neighborhood). Nothing else here speaks to the holiday — no shamash, no flames, no Star of David, no Hebrew typography, no oil-lamp vocabulary. This reads like "generic corporate diversity-week placeholder," which is exactly the failure mode you most want to avoid for a religious card.

**generic-celebration** — Burnt-orange block + "Congratulations!" in white Helvetica. The orange (#D97D2D) is closer to "Home Depot signage" than "celebration." There is nothing celebratory about it.

**mothers-day** — The most legitimately card-like of the eight, and still rough. Soft pink ground, italic Times-Roman in deep rose, three pink dots, an underline accent. The italic Times feels old (think 1990s wedding program). The dots are uneven — one large in the upper-left, two small bottom — and the negative space isn't doing anything intentional. But the *idea* (restrained palette, italic display word, one accent rule) is correct. With a real script display face and a botanical illustration in place of the dots, this becomes a real card.

## The 5 biggest design problems (ranked)

**1. System fonts everywhere.** Every shipped template uses `Helvetica` or `Times-Roman`. These are the ReportLab built-in fallbacks — they tell every designer who looks at the output "this was generated, not designed." The framework already supports TTF/OTF embedding (`font_file` field exists in the model, the renderer registers fonts) — and there isn't even a `fonts/` directory in the repo. Fix: ship the project with 6–8 curated open-source fonts (Cormorant Garamond, Playfair Display, Great Vibes, Cabin, Bebas Neue, Caveat, Libre Caslon, Allura) and rewrite every template to use them. No card framework should ever ship with Helvetica as the default.

**2. The "decorative" elements are pie-chart primitives, not illustrations.** Real cards use illustration: ink-line botanicals, painterly washes, hand-lettered swashes, gold-foil accents. This system uses circles-of-radius-0.12 to mean "ornament" and a triangle-stack to mean "tree." That's the visual vocabulary of an org chart, not a greeting card. The IR already supports `PathGeom` with cubic Bezier curves — nothing technical is stopping someone from shipping a hand-illustrated holly leaf as a path. Nobody has. Fix: hire one illustrator for two weeks to produce 30 SVG assets (botanicals, baubles, ribbons, snowflakes, menorahs, hearts) and ship them as `decorative_elements/*.yaml` PathGeom compositions.

**3. Color palettes have no taste.** The reds are signage-red, the oranges are construction-orange, the blues are corporate-blue. The hex values were picked with `r:0.8, g:0.1, b:0.1` syntax — the tell of an engineer reaching for "red" without consulting a swatch. Real card palettes pull from Pantone Christmas (Cranberry 19-1934, Forest Biome 19-5920, Antique Gold 16-0939), Farrow & Ball, or curated collections like coolors.co's editorial sets. Fix: rewrite every theme YAML with a designer-curated 5-color palette (primary, secondary, accent, neutral-light, neutral-dark) sourced from a real reference, and add a `theme.source_credit` field.

**4. Gradients exist in the IR and aren't used in the shipped templates.** I can see `LinearGradientPaint` and `RadialGradientPaint` in `render_ir.py`, and there are demo templates (`metallic_ornaments.yaml`, `winter_sky.yaml`) that use them — but none of the 8 *shipped* templates do. So the user-facing templates are all flat-color blocks, which is the single biggest aesthetic gap between "designed" and "generated." A subtle linear gradient on a background panel (e.g. cream → blush at 4% opacity differential) is the difference between "PDF" and "card stock." Fix: every shipped template gets at minimum a subtle background gradient and at least one gradient-filled accent.

**5. Compositionally, every template is the same.** Background fill + centered word + tiny accents. No template uses asymmetry, rule-of-thirds anchoring, full-bleed photography, monogram framing, vertical-stack typography, deckled edges, layered transparency, or any of the maybe twelve compositional moves that distinguish card design from poster design. Every front panel is "color ground + sentence." Fix: produce a *layout pattern library* (8–10 named compositions: "deckled-frame", "monogram-stack", "type-as-art", "photo-bleed", "border-with-cartouche") and rebuild templates against those patterns.

## What would have to change for these to ship at Minted

Minted's bar is brutal: 50% of submissions are rejected at jury, and the ones that ship pay royalties to *named designers*. To get on that platform:

1. **Replace all eight templates with hand-designed work** by an actual designer (not a developer iterating in YAML). Treat the existing eight as a tech demo, not a portfolio.
2. **Establish a brand voice**: warm/literary (Sugar Paper), bold/graphic (Rifle Paper), modern/spare (Smock), or curated/eclectic (Minted itself). Every template must feel like part of a *family*. Right now the eight templates feel like eight different unrelated experiments.
3. **Color management**: spec colors in CMYK or Pantone with print-safe RGB equivalents, not raw `r/g/b` floats. Cards print on uncoated/coated stock that shifts color 10–20% from the screen.
4. **Typography pairings**: every template needs an explicit display + body + accent pairing curated by a typographer. Not "use Helvetica."
5. **Foil/letterpress simulation in preview**: even if production uses flat ink, the preview should *simulate* foil with a brushed-gold pattern fill or letterpress with a soft drop shadow. Sells the design.
6. **Bleeds and trim marks**: I don't see any 0.125" bleed allowance in the templates. Every print-ready card needs bleed.
7. **Photo cards as the primary use case**: ~70% of Minted's holiday business is photo cards. Heart-clip and frame styles exist in the model; none of the shipped templates feature a photo well at all.

## The typography crisis specifically

This is where the project most loudly announces it was made by an engineer.

- **Eight templates. Two fonts. Both system defaults.** Helvetica (a Swiss neutral signage face from 1957) and Times-Roman (a 1932 newspaper face). These are the two fonts every operating system ships and every designer was taught to *avoid* on day one. Using Helvetica for "Merry Christmas" is using SF Mono for a wedding invitation. It's a category error.
- **No display/body distinction.** The classic Christmas card sets the headline ("Merry Christmas!") and the body ("Wishing you joy...") in *the same typeface*. Real card design always pairs a display face (high contrast, optical-size XL, decorative) with a body face (humanist, readable at 11pt). Even just Playfair Display + Lora would lift every template.
- **No script, no swash, no ornaments.** Holiday and celebration cards lean heavily on script faces for the headline ("Merry & Bright" in Adelina, "with love" in Allura, monograms in Cormorant Italic SC). The framework supports OTF — there's just no script in the project.
- **No optical kerning.** "Merry Christmas!" in Helvetica at 36pt has visible loose tracking around the "rr" and "as" pairs. ReportLab's text drawing doesn't do optical kerning unless you pre-process; nobody has.
- **No weight variation.** Every text element is either regular or italic. No light, no semibold, no black. A card might use Light for a date, Semibold for a name, and Black for the holiday word — three weights of one family creates hierarchy without changing fonts.
- **No vertical type, no curved baselines, no type-on-path.** The IR doesn't support any of these. Cards regularly set "JOY" vertically, or arc "Season's Greetings" around a wreath. This is a hard gap.
- **The italic Times-Roman on mothers-day** reads "wedding program from 1998." Replace with Cormorant Garamond Italic and the same composition leaps a decade forward.

The fix is small and high-leverage: ship 6–8 open-source fonts in a `fonts/` directory, rewrite every template to use them, add a `display_font` and `body_font` to themes, and *remove* Helvetica/Times-Roman from the default fallback chain so authors are forced to make a real choice. This single change would 10x the perceived quality of the project.

## The YAML problem

YAML is a fine *serialization* format and a terrible *design* tool.

**What YAML gives you:**
- Diffability, version control, programmatic generation, AI-friendliness (this is real and undersold).
- Reproducibility — same YAML always renders identically.
- Constrained structure — Pydantic validation catches errors early.

**What YAML does not give a designer:**
- *Visual feedback.* Designers iterate by eye. The cycle here is: edit YAML → run CLI → open PDF → squint at coordinates → edit YAML. That's a 30-second loop where Figma is a 0-second loop. No designer is going to author cards this way.
- *Spatial reasoning.* "Move the ornament 0.15 inches to the left and rotate it 7 degrees" is a drag in any GUI and a mental compile in YAML.
- *Color picking.* Specifying `r: 0.55, g: 0.20, b: 0.30` rather than `#8C3344` or — better — picking from a palette swatch is friction that selects against the people you most want using this tool.
- *Snap, align, distribute.* Foundational layout operations. Absent.
- *Component reuse with overrides.* You can `$ref` a decorative element but you can't override a sub-element's color without copying the whole YAML. Figma variants and Sketch symbols solve this trivially.
- *Ligatures, kerning pair adjustments, OpenType feature toggles.* All design surface. None expressible.

**The honest answer:** YAML should be the *output* of design tooling, not the *input*. The right architecture is:
1. A Figma plugin or web canvas that lets a designer compose visually.
2. An exporter that lowers the design to this YAML schema.
3. The CLI then renders YAML → PDF for production, in batches, with personalization variables injected.

Right now the project is asking *engineers* to do design work in a *config language*. That's a square peg in a round hole and is the single largest reason these cards look like cards engineers made.

A pragmatic middle ground: build a **live preview HTML editor** — a single-page web app with form inputs for every YAML field, color pickers, drag-handles for x/y, and a live SVG preview. That keeps YAML as the source of truth but removes the friction. Two weeks of work and adoption goes 10x.

## What's surprisingly good

Real credit where due, because the *bones* here are excellent:

- **The IR is genuinely well-designed.** `render_ir.py` separates geometry, paint, and command in exactly the right way. Linear gradients, radial gradients, pattern fills, cubic Bezier paths, clipping, and transforms are all first-class. The capability is there; it's the templates that don't use it.
- **Fold-aware layout.** The 4-panel model (front/back/inside_left/inside_right) with the rotation handling for the inside-left panel shows real understanding of how cards print and fold. Most generators don't get this right.
- **Half-fold geometry is correct.** 8.5x11 sheet, 4.25x5.5 panels, fold line correctly placed at the horizontal midline. The dashed fold-line indicator in the preview is a nice production-friendly touch.
- **Theme/template separation.** A template references a theme by ID; themes live in their own files. This is the right separation of concerns and lets one template ship in three colorways. (Now ship the colorways.)
- **Heart clip mask + image effects + photo frames** (per the Valentine's release notes): all the right primitives for a real photo card. They're just not used yet by the shipped templates.
- **The mothers-day template** is the only one where someone clearly *thought* about typography (italic display, italic body, restraint, accent rule). It's still not great, but it's the one where you can see a designer-shaped hand on the file. Build from there.

## The leapfrog opportunity

**AI-native, theme-driven generation with human-curated illustration assets.**

Every other card-design tool — Minted, Shutterfly, Canva, Figma templates — is built on the assumption that *humans* compose every card. The bottleneck is human design labor. That's why Minted has 25,000 templates and Shutterfly has 200; quality and quantity are inversely correlated, and there's a wall.

This project is *uniquely* positioned to crash through that wall because:

1. **YAML is the perfect intermediate format for an LLM to emit.** Claude/GPT can author YAML templates directly from a brief like "art-deco Hanukkah card with menorah motif, gold and midnight blue, body copy in Cormorant." The IR is constrained enough that an LLM won't hallucinate impossible primitives.
2. **The IR supports gradients, paths, patterns, clipping, transforms** — enough surface area for genuinely sophisticated output.
3. **A small library of curated, human-illustrated SVG path assets** (commission ~30 motifs from one illustrator) becomes the "vocabulary" the LLM composes from. The illustrator's hand provides the soul; the LLM provides the variety.

The product becomes: *user types a brief, gets a card.* "A Hanukkah card for my Bubbie with deep navy, copper foil accents, and a menorah." Six seconds later: a high-craft custom card. Hot-swap the photograph, hot-swap the message, hot-swap the recipient name. Print or send digitally.

That product doesn't exist anywhere. Minted can't build it (their moat is curation and they'd cannibalize their designers). Canva can't build it (their primitives are bitmap, not vector path-based). Figma can't build it (their primitives are great but they don't have the illustrator-asset moat or the personalization engine).

To get there from here, three things must change:
- **Commission the illustration library.** Without genuine hand-illustrated SVG assets, the output looks like ChatGPT made it. With them, it looks like Sugar Paper.
- **Bury Helvetica.** Ship 8 hand-picked fonts. Make them the only options.
- **Build the LLM-author harness** that takes a brief and emits valid YAML against a curated theme + asset library.

Everything else — the YAML-as-source-of-truth, the four-panel fold model, the gradient/path IR, the theme separation — is already correctly built for this future. The aesthetic problems are real but they're solvable in a quarter of focused work. The *architectural* setup is the rare and hard part, and that's already done. Stop adding features and start adding *taste*.
