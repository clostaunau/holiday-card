# Stationery Buyer / Retail Merchandiser Critique — holiday-card

## Verdict in one sentence

This is a Christmas card generator with token gestures toward a calendar — eleven of fourteen on-disk templates serve roughly 30% of the actual greeting-card year, and the few non-Christmas SKUs are either generic-template-with-the-word-changed (Hanukkah) or so kid-coded they exclude the demographic that buys the most cards (women 35-65).

## The Christmas over-index

**Inventory on disk (15 May 2026):** 14 templates total.
- Christmas: 11 (78.6%)
- Generic: 2 (one of which is "Mother's Day" misfiled under generic — the only generic-generic is "Celebration / Congratulations")
- Birthday: 1
- Hanukkah: 1

**Working/registered (via `templates --format json`):** 15 templates (the JSON listing includes `mothers-day` registered separately). Of those, **11 are Christmas, 1 birthday, 1 Hanukkah, 2 generic.**

**Industry baseline** (Greeting Card Association data, well-known to the trade):
- Birthday: ~60% of all year-round cards sold (the single largest category, by a country mile)
- Christmas: dominant SEASONAL category, ~30-40% of seasonal/holiday revenue, but seasonal is itself only ~40% of total category — so Christmas ends up roughly **15-20% of total greeting-card volume**
- Sympathy/anniversary/get-well/thank-you/wedding: ~25-30% combined
- Mother's Day, Valentine's, Father's Day, graduation: the remaining seasonal peaks

So a library that's **78% Christmas and 7% birthday** has the inverse of the actual market. This isn't a card line. It's an engineer's holiday hobby project that happens to render PDFs. The signal is unambiguous: this was built **during** the Christmas crunch by **someone making their own** Christmas cards, and the rest of the year was either an afterthought or a refactor sprint (see RELEASE_NOTES — Valentine's was actually built in Feb 2026 and then ripped out two months later because the architecture refactor took priority over coverage).

## SKU coverage matrix

| Occasion | Rough US market share | Templates here | Gap severity |
|---|---|---|---|
| Birthday (year-round) | ~60% of unit volume | 1 (kid-coded) | **Catastrophic** |
| Christmas / holiday | ~15-20% total, ~30% seasonal | 11 | Wildly over-indexed |
| Sympathy / condolence | ~5-7%, highest emotional ASP | 0 | **Catastrophic** |
| Thank-you (incl. wedding) | ~5-8%, high re-purchase | 0 | **Catastrophic** |
| Anniversary | ~3-5% | 0 | Severe |
| Mother's Day | ~2nd biggest seasonal | 1 | Present, weakly executed |
| Father's Day | smaller but real Q2 peak | 0 | Severe |
| Valentine's Day | top-3 seasonal | 0 (deleted) | Severe + self-inflicted |
| Get-well | ~2-3% | 0 | Moderate |
| Wedding (congrats + invite) | ~2%, very high ASP | 0 | Severe |
| New baby / shower | ~2%, high ASP, gift-attached | 0 | Severe |
| Graduation | seasonal Q2 peak | 0 | Moderate |
| Easter | top-5 seasonal | 0 | Moderate |
| Halloween | growing card category | 0 | Moderate |
| Hanukkah | niche but defined | 1 (text-only stub) | Present, poorly executed |
| Eid / Diwali / Lunar New Year / Día de los Muertos / Juneteenth / Pride / Rosh Hashanah | Each underserved by majors | 0 | Strategic miss |
| "Just because" / encouragement | Fastest-growing segment | 0 | Strategic miss |

## The 5 missing categories that would matter most

If I were merchandising this assortment for a real shop and could only greenlight five new ranges this year, in priority order:

1. **Adult birthday — three sub-SKUs minimum.** Milestone (30/40/50/60 — these fly off the rack and the buyer is usually a spouse, sibling, or coworker willing to pay $7), "from a friend" (warm, not romantic), and funny/snarky (the Em & Friends / Knock Knock white space). The current `birthday-balloons` template is purple balloons with Helvetica Bold — that's a pediatrician's-office card. Adults aren't buying it for adults.

2. **Sympathy.** This is the single hardest card to write and the one buyers are most desperate to find. Margins are excellent ($5-9 for a beautifully restrained card with one phrase). Botanical, candle, or nothing-but-typography motifs. **The fact that this library has zero sympathy SKUs while having a "Holiday Masterpiece" showcase template tells you everything about whether a buyer was ever consulted.**

3. **Thank-you (multi-pack).** Wedding thank-yous, baby-shower thank-yous, generic gratitude. Sold in 8- or 10-packs with envelopes — this is where indie makers actually make rent. Recurring purchase, gift-attached, low design risk.

4. **Mother's Day expansion + Father's Day launch.** Mother's Day is the #2 card-sending day of the year. One template is table stakes; you need three (traditional/floral, modern/typographic, funny). Father's Day is currently a goose egg and the gap is doubly conspicuous because the existing Mother's Day SKU exists.

5. **Valentine's Day — restore what was deleted.** v2.0.0 had three Valentine templates. They were ripped out for an architecture refactor. From a SKU perspective that's a $400M-category own goal. Re-ship them (even feature-degraded) before next February.

## Demographic + cultural gaps

Beyond the obvious volume gaps, the library has a **calendar-cultural identity** problem. It's quietly Christian-American-nuclear-family in its assumptions:

- **Hanukkah is the only non-Christian-calendar SKU**, and its execution betrays it: the menorah template **has no menorah** in the file. It's the same panel layout as `generic-celebration` with the background changed to navy and "Happy Hanukkah!" in white Helvetica Bold. That's not a Hanukkah card — that's a buyer's lawsuit waiting to happen if anyone tried to sell it as one.
- **Eid al-Fitr and Eid al-Adha**: Muslims are ~1.1% of the US and 25% of the global population. There is a real, growing greeting-card market here being completely ignored by the majors — Hallmark and American Greetings each ship one or two SKUs, badly. White space.
- **Diwali**: South Asian-American card spending is concentrated, gift-heavy, and underserved. The audience is willing to pay premium for designs that respect the iconography (rangoli, diyas, peacock motifs).
- **Lunar New Year / Tết**: Two billion-person event. Zero coverage.
- **Día de los Muertos**: Crossed into the mainstream a decade ago.
- **Rosh Hashanah / Yom Kippur**: Hanukkah is *not* the most important Jewish holiday. The High Holy Days are. Their absence while shipping a Hanukkah stub is itself a tell.
- **Pride** (June): June is a card-sending and gift-giving month for the LGBTQ+ community and allies. Hallmark ships these now. Indies own this category.
- **Juneteenth**: Federal holiday since 2021. Card category is being defined right now — first movers win shelf space.

This isn't "be more inclusive" pablum. These are **specific, addressable, underserved markets** where indie makers are currently winning because the majors are slow.

## Format / positioning critique

**Every template is US Letter (8.5×11) folded in half**, except `christmas-modern` which is quarter-fold (and quarter-fold from letter is a 4.25×2.75 finished card — that's tiny and structurally weird, no actual card retailer sells that size). One implicit format = one implicit market.

Real card market formats:
- **A2 (4.25×5.5)** — what this project nominally produces, fine
- **A6 / 4-bar (4.875×6.875)** — premium indie standard, slightly larger and feels heftier in the envelope
- **5×7** — the "art print that ships flat with an envelope" format, dominant on Etsy, Minted, Greetabl
- **3.5×5 (mini)** — gift-attachment cards
- **6×6 / 6×9 jumbos** — milestone birthday, sympathy, "big feelings" cards, $9-15 ASP

**Letter-paper-half-fold** is a print-at-home choice. It's not a print-and-sell choice. Real card stock arrives die-cut to A2 or A6. So the format choice positions this as a **personal-use generator**, not a maker-tool. That's a defensible positioning, but it should be explicit, and it forecloses the maker market until you ship cut-line / bleed support and 5×7 flat output.

## Who this library actually serves today

Honest persona profile: **A solo engineer making one (1) Christmas card per year for their personal mailing list.** The SKU mix maps to one human's December workflow:
- 11 Christmas templates because they iterate every year on the same project
- 1 birthday card because they had a kid's birthday come up
- 1 Hanukkah card to round out December politely
- 1 Mother's Day card built in May (this month — the date of this critique is 2026-05-10) because Mother's Day was last Sunday and they noticed they had nothing
- 1 generic "Congratulations" as the catch-all

The CLI ergonomics, the per-template YAML hand-tuning, the "showcase" templates demonstrating renderer features — all confirm this. This is **a developer making cards for themselves**, with a side hobby of demonstrating ReportLab capabilities. The architecture refactor in v1.1.0 (which deleted the Valentine line to clean up the IR) is the giveaway: a buyer would have screamed about losing SKUs in February for an internal cleanup; an engineer treats Valentine's as "three YAML files we can re-add later."

## Who it COULD serve with the right SKU mix

Two viable markets, picking one:

- **The print-at-home personal-card maker.** Aunts, parents, grandparents who want to make a real-feeling Mother's Day card in 90 seconds without opening Canva. Needs: 30+ templates across the actual sending calendar, a non-CLI surface (web UI or at minimum a friendlier `holiday-card wizard`), Avery-style print-and-cut helper.

- **The micro-batch indie Etsy maker.** Templates as starting points to customize, then export to print-shop-ready PDFs. Needs: bleed marks, CMYK output, 5×7 flat support, A6 support, font licensing clarity, and a brand-customization layer (swap palette/fonts across an entire range).

These are different products. The current library straddles both and serves neither.

## What's surprisingly good

- **Mother's Day execution.** The shapes, the soft pink palette, the italic Times-Roman, the "with love" subtitle — this is a real card. Whoever wrote this template understood that adult cards are restrained, not loud.
- **The decorative-element library that existed in v2.0.0** (heart_outline, love_birds, menorah, dreidel) was the right *idea* — composable motifs that could be reused across templates. Its deletion in v1.1.0 is the single biggest assortment-strategy error in the project's history.
- **Breadth of Christmas** — within the Christmas category, the 11 templates do span aesthetics (geometric, classic, photo, modern, holly wreath). If a buyer asked me to source a Christmas-only assortment, I could actually merchandise this.
- **YAML templates** are exactly the right abstraction for an assortment-driven product. New SKUs cost hours, not days. The library doesn't grow because no one's prioritizing it, not because it's hard.

## The leapfrog opportunity

**Reposition as the open-source greeting-card engine for indie makers, and ship a "card-of-the-month" SKU calendar.**

One move, two halves:

1. **Calendar-driven assortment.** Commit to shipping 3-5 templates per month aligned to that month's actual sending peak: January (birthday + thank-you + sympathy baseline), February (Valentine's restored + Lunar New Year + Galentine's), May (Mother's Day x3 + graduation x3 + sympathy), June (Father's Day + Pride + Juneteenth + wedding), October (Halloween + Día de los Muertos + Diwali), November (Thanksgiving + sympathy + Rosh Hashanah carryover), December (Christmas + Hanukkah-that's-actually-a-Hanukkah-card + Kwanzaa + secular winter). By December 2026 the library is 60+ SKUs across the real card calendar instead of 14 SKUs across one quarter.

2. **Maker-grade output: bleed, CMYK, 5×7 flat, A6 folded.** This is the format work that converts this from "personal generator" to "the tool indie makers use to ship product." Combined with the calendar, it positions the project as **"the open-source counterpart to Minted's design templates"** — a credible, defensible niche with no current incumbent.

The Christmas-monoculture is fixable in one quarter of focused merchandising. The format-monoculture is fixable in one engineering sprint. Do both, and you've got a real product. Don't, and this is and remains an engineer's holiday hobby.
