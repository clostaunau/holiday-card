# Industry Panel Consensus — OpenAI Image Generation Feature

## The verdict the six critics would jointly sign

**No — not now, and not in the proposed shape.** The panel does not endorse shipping `gpt-image-2` image generation as a render-time, panel-filling feature against the current codebase. Five of six critics (Prepress, Designer, Copywriter, Buyer, POD) say "yes, eventually, in a much narrower form, after the prerequisites land"; one (Sandy / DIY) says "this is a Tyler feature that does not narrow my gap and may widen it." There is unanimous agreement that this proposal is **out of order** relative to the panel's prior leapfrog ranking — bleed/CMYK/`--export-for moo-a6` (Leapfrog 1) and the curated taste layer (Leapfrog 2) are hard prerequisites, not nice-to-haves. Shipping AI generation onto today's foundation produces a faster way to manufacture rejectable, voiceless, IP-fragile cards.

The shape the panel **would** eventually endorse: an authoring-time (not render-time), background-or-motif-only (not panel-replacement), style-anchored (not free-text-to-image), POD-aware (target-driven sizing + sRGB→CMYK soft-proof), provenance-tagged, category-gated, opt-in subcommand that bakes assets to disk and commits them to the repo. That is a Q1 2027 feature, not a now feature.

## Cross-cutting agreements (≥3 critics)

### Agreement A1: Out of sequence — Leapfrogs 1 and 2 must ship first
- **Critics:** Prepress, POD, Designer, Copywriter, Buyer (5/6).
- **Substance:** Without bleed + distinct PDF boxes + CMYK + ICC plumbing (Leapfrog 1), AI rasters have nowhere clean to land — they fail POD preflight on bleed, color space, and DPI simultaneously. Without the curated illustrator + sentiment + font library (Leapfrog 2), AI imagery has no style to anchor to and produces ChatGPT-aesthetic slop on cardstock. Shipping AI generation first cannibalizes engineering attention from the moves the panel actually endorsed and deepens the credibility problem.
- **Fix:** Sequence is `--export-for moo-a6` end-to-end → curated taste layer → AI as a *consumer* of both. Do not ship `--ai-fill` (or any equivalent) until the leapfrog work it depends on is in place.

### Agreement A2: Authoring-time bake to disk, never render-time API call
- **Critics:** Prepress (`ai-asset generate` subcommand baking to disk), Designer ("authoring time, yes; render time, never"), POD (`build_ai_request` + cache by seed when `--reproducible`), Copywriter (image carries `seed` for next-year reproducibility), Buyer (cache and surface the prompt) (5/6).
- **Substance:** The entire reproducibility moat — "version-controlled, CI-rendered, reproducibly-built greeting cards as code," which is the single thing this project does that Canva/Hallmark/Minted cannot — dies the moment a stochastic black-box service sits inside the render path. Model deprecation alone (`gpt-image-1` is already legacy) means the same YAML renders a different card a year later, silently. The 2-minute latency also makes per-render API calls a non-starter for CI and for Sandy's iteration loop.
- **Fix:** A `holiday-card ai-asset generate` subcommand emits an asset to disk with a license/provenance sidecar (prompt, seed, model version, timestamp, reference image, cost). The card render pipeline only ever reads static files. Authoring is online; rendering is offline.

### Agreement A3: Style-anchored, motif-not-panel, never AI-renders-text
- **Critics:** Designer (image-reference mode against curated illustrator PNGs; AI as motif generator filling a known hole), Copywriter (structured `subject/style/composition/palette_ref/reserve_for_text/avoid` schema; enumerated style vocabulary co-tagged to `--voice`), POD (background-fill primitive layered beneath shapes/decoratives, not panel replacement), Prepress (no AI-rendered text — copy goes through the existing vector text element) (4/6).
- **Substance:** Free-text-to-image with no style anchor produces the synthetic-mid-2020s ChatGPT aesthetic — recognizable in half a second, voiceless, four-different-burgundies-on-the-same-card incoherent. The model rendering text is famously imperfect even in 2026 and bypasses the project's vector text pipeline (custom fonts, kerning, embedding).
- **Fix:** Image-reference mode against `decorative_elements/*.png` is the default authoring path. Text-to-image with no anchor is gated behind a flag literally named `--unsafe-no-style-anchor`. Enumerated `style:` values (watercolor, vintage botanical, block print, riso, etc.) co-tagged to `--voice`. AI never renders text — copy stays vector. Default fill mode is `background`, not `panel`.

### Agreement A4: Hard category gates against AI imagery
- **Critics:** Prepress (block AI for photos of recognizable people), Designer (`--no-ai` default for sympathy/condolence/anniversary), Copywriter (sympathy/miscarriage/pet_loss/funeral/get_well_serious/divorce_support hard-rail), Buyer (sympathy/condolence/get_well/religious holidays — radioactive failure modes), Sandy (sympathy + anything she sells + her grandma) (5/6).
- **Substance:** Bereavement, religious iconography, photo-card slots, and any commercial sale path through Etsy/Printful/Printify carry failure modes that range from "small additional cruelty to a grieving person" to "open-source project named in a Disney DMCA action." Six-fingered Jesus, menorahs with the wrong number of branches, AI condolence bouquets — these are not edge cases; they are the *predictable* outputs of unconstrained generation in those categories.
- **Fix:** `ai_imagery_allowed: false` field on the occasion type, defaulted on for the consolidated hard-rail list (see "Hard rails" section). CLI hard-errors with an explanatory message. Override requires `--i-know-what-im-doing` plus a confirmation prompt.

### Agreement A5: Provenance, disclosure, and IP guardrails are non-negotiable
- **Critics:** Buyer (XMP metadata + C2PA + visible PDF watermark + first-use consent + non-commercial positioning in README), POD (200-name trademark blocklist + `moderation: "auto"` + per-export disclosure surface + `/Subject` PDF metadata), Designer (`provenance` field in YAML + `--show-provenance` flag), Prepress (license-record sidecar required), Copywriter (cover-to-inside `sentiment_id` traceability) (5/6).
- **Substance:** EU AI Act labeling provisions are already in force. Etsy is actively de-listing AI-assisted listings in waves. Printful/Printify/Catprint require disclosure. US copyright law currently denies protection to purely AI-generated outputs. A solo part-time maintainer cannot be upstream of those failures without explicit defensive scaffolding. The OpenAI doc itself is silent on commercial/IP terms — the project must surface that gap loudly.
- **Fix:** First-use consent gate (logged); trademark prompt blocklist (refuse Disney/Marvel/Pokémon/Coca-Cola/etc., override requires explicit flag); always `moderation: "auto"`; embed `Subject: "Contains AI-generated imagery (gpt-image-2)"` in PDF Info dict; visible PDF watermark by default (override requires re-consent); per-export disclosure prompt when `--export-for` target requires it (Printful, Printify, Catprint); README paragraph in plain English about user responsibility; license-record sidecar YAML committed alongside every baked asset.

### Agreement A6: POD-aware sizing and color management or it doesn't ship
- **Critics:** Prepress (mandatory Pillow CMYK conversion w/ bundled GRACoL2013, soft-proof preview, ICC embedding, 350 DPI at declared use-size, refuse to embed without it), POD (target → trim+bleed → pixel dims at 300 DPI rounded to /16, generate at trim+2×bleed and crop inward for bleed, sRGB tagging mandatory, soft-proof + ΔE warning, optional CMYK transform), Designer (lower-priority but implicit in "shipped after Leapfrog 1") (3/6 explicit, more implicit).
- **Substance:** gpt-image-2 emits 8-bit untagged sRGB with no bleed concept and no deterministic resize. Letting users sit at 1024×1024 produces effective 168 DPI on the long edge of an A6 card — fails Smartpress preflight, looks soft on MOO. Diffusion models love saturated cyans/magentas/emeralds that collapse on sRGB→CMYK conversion. The user uploads one thing and prints another and blames MOO; MOO's reprint policy excludes color shifts from sRGB sources.
- **Fix:** A `build_ai_request(target, panel, prompt) → AIRequest` helper that resolves target geometry to pixel dims at 300 DPI, rounds to /16, requests trim+2×bleed sizing for bleed-crop, picks JPEG-90 for photographic prompts, sets moderation. Tag all output as sRGB IEC61966-2.1. When export target is CMYK-required, soft-proof and warn at ΔE >6 for >5% of pixels; optionally transform to target ICC. None of this exists today. **All of it is prerequisite.**

### Agreement A7: This widens, not narrows, the Sandy gap
- **Critics:** Sandy (entire critique), Buyer ("personal-use-only authoring assist" — not for resale, not for indie shops), Designer (only useful as motif amplifier for the Tyler-shaped engine), Copywriter (CLI flag is a power-user fast path; Sandy's not the audience) (4/6).
- **Substance:** API-key gauntlet, OpenAI Org Verification, BYO billing with no cap, 2-minute latency on top of the existing 90-second YAML loop, $25/month at Sandy's volume vs. her $13/month Canva-included unlimited-Magic-Studio subscription, runaway-bill anxiety, no transparent backgrounds, single-result-per-generation vs. Canva's grid-of-four. The existing install gap, YAML gap, preview gap, photo-handling gap — none are touched. Sandy bounced last quarter on `pip install -e ".[dev]"`; the OpenAI Org Verification step adds a second wall *on top of* the first.
- **Fix:** Stop telling Sandy this is for her. The audience for this feature is Tyler — and even Tyler should get it shaped as authoring-time asset baking for the curated library, not as a render-time CLI flag. If Sandy is ever to use AI in this project, it arrives via the **template microsite escape hatch** (Leapfrog 5) wrapped in a hosted SaaS that handles billing — a different product, not a flag on this one.

## Genuine tensions / dissent — strategic forks

The five "yes" critics each described a *different product* under the same headline. These are not paraphrases of one another; they are real forks.

### Tension B1: Asset-baking subcommand (Prepress) vs. structured `ImageElement.generated` schema (Copywriter) vs. `--ai-fill` background primitive (POD) vs. image-reference motif extension (Designer) vs. "developer scaffolding only" (Buyer)
- **Prepress:** `holiday-card ai-asset generate --prompt ... --out assets/ai/foo.png` — a side subcommand. Card render never sees the model. Closest to a stock-photo-fetch CLI.
- **Copywriter:** A first-class `image_elements: [{ generated: { subject, style, composition, palette_ref, reserve_for_text, mood, avoid, seed }}]` schema in template YAML, with `sentiment_id` shared between cover image and inside copy. The richest, most tightly integrated proposal.
- **POD:** A `--ai-fill` flag with `--ai-fill-mode {background, panel, masked-region}` defaulting to `background`, layered beneath shapes/decoratives via existing z-index. Treats AI as a fill primitive of the *render pipeline*, but POD-aware via target-driven sizing.
- **Designer:** Image-reference-mode-only motif generator, anchored to the illustrator library. Generates *one motif* (poinsettia, candle, heart in the house style) into a known hole. Identity + variety. Text-to-image disabled by default.
- **Buyer:** `--ai-mockup` developer scaffolding with PLACEHOLDER watermark so visible no one ships it. AI as wireframe, not deliverable. Most restrictive of all.
- **Sandy:** None of the above. Wrap the whole thing in a hosted SaaS with predictable billing, or don't bother me with it.

**Reconciliation the panel would jointly sign:** A hybrid. The *primary surface* is Copywriter's structured `ImageElement.generated` schema — that's the data model. The *invocation* is Prepress's authoring-time `holiday-card ai-asset generate` subcommand — that's the workflow. The *anchoring discipline* is Designer's image-reference-mode-against-curated-PNGs as default — that's the taste guarantee. The *render-pipeline integration* is POD's target-driven sizing + bleed-crop + sRGB tagging + optional CMYK transform — that's the print correctness. The *positioning* is Buyer's "personal use, not for resale" — that's the brand-defense paragraph. The *out-of-scope thing* is everything Sandy needs (a button, a hosted bill, a grid of four results) — accepted, deferred to a future SaaS layer (Leapfrog 5+).

### Tension B2: How loud is the AI badge?
- **Buyer:** Visible PDF watermark default-on, `--no-ai-disclosure` re-triggers consent.
- **POD:** Embedded XMP metadata + `/Subject` field, no visible watermark unless target POD requires it.
- **Designer:** `--show-provenance` flag, no visible watermark on the card itself.
- **Disagreement is real.** A visible watermark on a personal grandma card ruins it; a hidden metadata-only mark fails the EU AI Act's "clearly identifiable" reading and lets a commercial seller pretend the card is human-made.
- **Recommendation:** Embedded metadata always (XMP + `/Subject`). Visible watermark default-on for `--export-for printful|printify|catprint|vistaprint` (any commercial-resale target). Visible watermark default-off for `--export-for home`. The export target carries the disclosure policy.

### Tension B3: Should AI-generated copy ever be allowed?
- **Copywriter:** Reluctantly yes, behind a separate `--generate-copy` flag, requiring explicit opt-in even with `--generate-image` on, and even then composing from the curated sentiment library rather than free generation.
- **Designer:** Hard no. "The sentiment is the card. Outsourcing the words to a foundation model is what makes recipients feel sent to."
- **Recommendation:** Designer wins. AI-generated copy is out of scope for v0, v1, and v2. If it ever ships, it ships as Copywriter described — selection-and-combination from the curated library, never free-form ghostwriting — but the panel would warn against shipping it at all. The cards-with-good-copy tool does not exist yet; do not skip past human curation to LLM ghostwriting.

### Tension B4: Hosted SaaS vs. CLI-only
- **Sandy:** Wrap it in a hosted SaaS with $5/month subscription + budget cap, or it's not for me.
- **Everyone else:** CLI on the user's machine, BYO key.
- **Recommendation:** CLI/BYO-key for v0. The hosted SaaS is a separate product (and a viable one — the maintainer could pocket the OpenAI volume-discount margin), but it's downstream of the template-microsite escape hatch (Leapfrog 5) and not on the critical path of the OSS tool's identity.

## The hard rails — categories where AI imagery should NOT be allowed

Default-on refusal. CLI hard-errors with an explanatory message. Override requires `--i-know-what-im-doing` plus a per-invocation confirmation prompt that prints the reason for the rail.

1. **Sympathy / bereavement / condolence.** (Copywriter, Designer, Buyer, Sandy.) Recipient is in their hardest week. AI imagery composed by no one is "a small additional cruelty on top of the loss." Hard rail; no commercial pressure can justify the failure mode.
2. **Miscarriage, pregnancy loss, infant loss.** (Copywriter explicit.) Subset of bereavement; same reasoning, higher stakes.
3. **Pet loss.** (Copywriter; Sandy notes the *exception* — AI editing of a real photo of the pet the family supplied is sometimes welcomed. The default refusal stands; the override path is well-marked.)
4. **Funeral / memorial cards.** (Copywriter.)
5. **Serious get-well / illness / hospital.** (Copywriter — `get_well_serious` distinct from "feel better!" cold cards.)
6. **Divorce-support / breakup-support.** (Copywriter.)
7. **Religious holiday cards with iconography** — Easter (Christ), Christmas-as-Nativity (not generic winter), Hanukkah (with menorah/dreidel), Eid, Diwali, Día de los Muertos, Lunar New Year religious framings. (Buyer explicit; Designer implicit in "voiceless at scale.") Hallucinated wrong-branched menorahs, six-fingered Jesus, candles labeled as Diyas — predictable, reputationally radioactive.
8. **Photo-card slots.** (Buyer, Copywriter, POD.) The point of a photo card is the actual photo of the actual family. AI in a photo slot is a category contradiction. Generated *backgrounds* under a real-photo polaroid frame are fine and explicitly endorsed by Copywriter; generated *replacement* of the photo is not.
9. **Anniversary cards "for the people who care."** (Designer.) Lower-confidence rail; the panel might allow this with an opt-in path. Recommended default: warn rather than refuse.
10. **Any card with recognizable likenesses of real people.** (Prepress explicit, Buyer implicit.) Legal landmine independent of print quality. Refuse prompts that name public figures via the trademark/likeness blocklist.
11. **Any card destined for `--export-for` targets that prohibit AI in the chosen product category.** (POD.) E.g., some Printify product lines. Hard refuse; not even an override.

## The audience question — has it changed?

**No. Sandy's verdict stands and is reinforced by the AI proposal, not weakened.**

- **Sandy:** "This didn't fix anything for me. It added a second wall on top of the first." The API-key gauntlet, the BYO-billing anxiety, the 2-minute latency stacked on top of the 90-second YAML loop, the lack of a Canva-style grid-of-four, the Etsy-resale danger — none of Sandy's gaps are touched. She is more emphatic this round than last: "Stop telling me it's for me."
- **Tyler:** Architecturally aligned. He has 14 API keys in his password manager. The CLI shape, the YAML schema, the cache-asset-to-git workflow, the seed-pinning — all match his mental model. AI generation as authoring-time asset baking is genuinely a Tyler feature.
- **Buyer:** Reinforces "personal-use only, never commercial." The indie-maker market segment the panel previously pointed the project toward is the segment most actively positioning *against* AI. The maintainer cannot be both the indie-maker tool and the AI-flood tool. Pick.
- **Designer:** Tyler-aligned, with the leapfrog-3 framing — AI as the engine that amplifies the curated illustrator's hand for Tyler-the-engineer to compose against.

**Confirmation:** Stay Tyler-first. AI generation is a Tyler-shaped feature when it ships in the proposed shape. Sandy's bridge is still the **template microsite escape hatch (Leapfrog 5)** — and if AI ever reaches Sandy, it reaches her *through that*, not through `--ai-fill`. The Buyer's "AI-restrained" positioning bet is the panel's recommendation: stay restrained, ship the moat, let AI be plumbing.

## Sequencing — does this go before, alongside, or after the earlier leapfrog ranking?

**After. Strictly after.** Five of six critics are explicit that AI generation is out of order. The recommended ordering does not change:

- **Q3 2026 — Leapfrog 1: `--export-for moo-a6` end-to-end.** Bleed plumbing, distinct PDF boxes, CMYK conversion via bundled GRACoL2013 ICC, embedded fonts on the default path, per-panel exports. This is the panel's #1 endorsement and remains so. The AI proposal does not displace it; it *depends on* it.
- **Q4 2026 — Leapfrog 2: Curated taste layer.** Illustrator commission (~30 SVG path motifs in one opinionated hand), 6-8 curated open-source fonts shipped in `fonts/`, voice-tagged sentiment library with `--voice {warm,witty,spare,devotional,irreverent}`, `--blank-inside`, salutation/signoff/signature/P.S. as first-class fields, occasion taxonomy expansion to include sympathy/condolence/miscarriage/pet_loss (so the AI hard-rails have categories to gate against). Defects 1-9 from the prior consensus all closed by now.
- **Q1 2027 — AI as Leapfrog 3, narrowly scoped.** The asset-baking subcommand against the curated library, image-reference-mode-default, structured `ImageElement.generated` schema, POD-aware sizing, sRGB tagging + soft-proof + optional CMYK transform, hard category rails, provenance metadata + visible-watermark-by-default-on-commercial-targets, first-use consent + trademark blocklist. **Not panel-replacement, not text generation, not render-time, not photo-replacement.**
- **Leapfrog 4 (cards-as-code identity) and Leapfrog 5 (template microsite)** retain their prior ranking and are largely orthogonal to AI. The microsite is the eventual Sandy bridge if a hosted-SaaS-with-budget-cap shape ever materializes.

**Critical:** if the maintainer ships AI generation now and skips the leapfrogs, the project becomes "fast way to make rejectable, voiceless AI cards" rather than "the only OSS tool that produces a POD-ready AI-augmented card from version-controlled YAML." Both have the same engineering effort; only the second has a moat.

## The risks the maintainer would be accepting

The Buyer's framing is the load-bearing one and deserves direct quotation: *"a solo part-time maintainer ... does not have legal/moderation/brand capacity to be upstream of Etsy takedowns, DMCA notices, OpenAI ToS shifts, POD silent rejections, or EU AI Act enforcement."* Take that seriously. The risks, in order of likelihood:

1. **Legal exposure (third-party).** A user prompts "happy mouse in red overalls," gets something that looks like Mickey, sells it on Etsy, gets a DMCA notice, posts on Twitter that "holiday-card made me do it." The project is not legally liable; the project is reputationally named. Week-one risk. Mitigation: trademark blocklist + first-use consent + README paragraph + visible watermark on commercial export targets.

2. **OpenAI ToS shifts.** OpenAI has changed terms multiple times since 2022. A retroactive change to commercial-use language exposes every user whose card includes a baked AI asset. Project is the vector. Mitigation: license-record sidecar capturing the exact policy URL and timestamp at generation.

3. **Model deprecation.** `gpt-image-1` and `1-mini` are already legacy. `gpt-image-2` will be `gpt-image-3` and then deprecated. Same YAML, same git history, different card a year later — silently. This is the biggest *architectural* risk because it directly contradicts the project's reproducibility moat. Mitigation: bake assets to disk and commit them; the model is invoked at authoring time, the asset is frozen in git, the render pipeline never calls the API.

4. **POD silent rejections.** A POD service pattern-matches `holiday-card` in PDF producer metadata as an AI pipeline and silently de-prioritizes or rejects. Users complain about rejections, the maintainer has no recourse, reputation rots from below. Mitigation: ship `--export-for` correctness *first* so the project's PDFs are independently preflight-clean; surface AI-disclosure metadata that PODs prefer over silent inference.

5. **EU AI Act enforcement.** Transparency obligations for synthetic content are in force in 2026; enforcement actions in 2026-27 are expected. European users without provenance metadata are exposed; project carries retrofit debt later. Mitigation: ship provenance + watermark from day one of the AI feature.

6. **Brand drag.** Em & Friends-adjacent buyers and the indie-maker segment the consensus pointed the project toward will not touch a tool known as an AI card generator. The project's positioning is inherently in tension with the AI feature unless explicitly framed as "personal use, not for resale, restrained-by-default." Mitigation: ship the Buyer's positioning paragraph verbatim: *"AI image generation is intended for personal use. We do not recommend AI imagery for cards you intend to sell."*

7. **Scope creep.** AI generation is a feature with infinite surface — once shipped, every issue becomes "can it do X?" Hosted SaaS, hosted billing, grid-of-four UX, in-browser preview, AI-generated copy, AI-edit-photo mode, video cards. The maintainer's part-time budget cannot absorb this. Mitigation: ship the *narrowest* viable shape and decline expansion firmly. The Designer's "AI is plumbing" framing is the right rhetorical defense.

8. **Dependency on a paid third-party API.** The OSS project now requires `OPENAI_API_KEY` for a headline feature. License conflicts, rate limits, regional availability (China, Russia, sanctioned countries) all become project problems. Mitigation: gate behind `pip install holiday-card[ai]` extras, refuse to be a default code path, ensure the project remains fully functional without the AI feature.

9. **Reproducibility moat erosion.** Even with bake-to-disk, a user who didn't commit the asset and lost the seed cannot reproduce. Mitigation: refuse to render with `--export-for`-anything if an AI asset is referenced and missing the sidecar.

## The recommended product shape

The single coherent product the panel would jointly endorse, distilled across all six critiques:

**`holiday-card ai-asset generate` — an authoring-time subcommand, not a render-time flag.**

Shape:

```bash
holiday-card ai-asset generate \
  --reference decorative_elements/valentine/heart_outline.png \
  --subject "watercolor pine bough border, sage green and burgundy" \
  --style watercolor \
  --palette-ref themes/christmas.yaml \
  --reserve-for-text "x=2.75 y=0.5 w=2.5 h=4.0" \
  --for-panel front \
  --export-for moo-a6 \
  --seed 42 \
  --out assets/ai/pine-bough-border.png
```

Properties:

1. **Authoring-time only.** Generates → writes asset to disk + sidecar YAML → exits. The card render pipeline never calls OpenAI.
2. **Image-reference mode default.** Reference image required unless `--unsafe-no-style-anchor` is passed. Reference comes from the curated illustrator library or a previously-generated asset; chains style across the project.
3. **Structured prompt schema.** Subject, style (enumerated, not free-form), palette-ref (theme YAML, not hex tuples), composition, reserve-for-text (copy-safe zone the model's composition must respect), mood, avoid (negative prompts), seed.
4. **POD-aware sizing.** `--export-for` resolves to trim+2×bleed dimensions at 300 DPI rounded to /16 multiples. Never lets the user sit at 1024×1024 for a print target.
5. **sRGB tag + soft-proof.** Always tag as sRGB IEC61966-2.1. When `--export-for` is CMYK-required, soft-proof against bundled GRACoL2013 ICC, warn at ΔE >6 for >5% of pixels, optionally transform to target ICC and embed.
6. **Sidecar provenance YAML.** Every asset gets a sibling `<asset>.license.yaml` with prompt, style, reference, model, model version, timestamp, seed, cost, OpenAI policy URL at generation time, and a placeholder for the user's commercial-use determination. Refuse to embed any AI asset whose sidecar is missing.
7. **Hard category rails.** `ai_imagery_allowed: false` on occasion types (sympathy, condolence, miscarriage, pet_loss, funeral, get_well_serious, divorce_support, religious_*); CLI refuses to use AI assets in templates of those occasions. Override requires `--i-know-what-im-doing`.
8. **Trademark prompt blocklist.** 200-name list checked against prompt before submission; refuse with explanation; override requires explicit per-invocation flag.
9. **First-use consent.** One-time gate logged to `~/.config/holiday-card/ai-consent.json`. Surfaces OpenAI usage policy URL, copyright caveat, IP responsibility, POD disclosure obligation. Default refusal until acknowledged.
10. **Provenance in the rendered PDF.** XMP metadata + `/Subject: "Contains AI-generated imagery (gpt-image-2)"` in PDF Info dict. Visible PDF watermark default-*on* when `--export-for` is a commercial-resale target (printful/printify/catprint/vistaprint); default-*off* for `--export-for home`. `--no-ai-disclosure` re-triggers consent.
11. **No AI-rendered text. No photo-replacement. No render-time API calls. Default fill mode `background`, never `panel`. No inside-panel AI by default.**
12. **Hard-gated extras.** `pip install holiday-card[ai]`. Project remains fully functional without it.
13. **Positioning paragraph in README, verbatim:** "AI image generation is intended for personal use. We do not recommend AI imagery for cards you intend to sell."

That's the shape. It is small relative to the proposal that prompted this review, and it ships *after* the leapfrog work.

## The smallest viable v0 — one PR, two weeks, defensible at six months

If the maintainer were forced to ship the absolute minimum *today* to put any AI generation in the project (panel does not endorse this without leapfrogs, but answers the question honestly):

**`holiday-card ai-asset generate --prompt ... --reference path/to/curated.png --out path.png`**

A single new subcommand that:

1. Lives behind `pip install holiday-card[ai]` extras and `OPENAI_API_KEY`.
2. **Requires** `--reference` (image-reference mode default; no text-to-image v0).
3. Generates one asset, writes it to disk as PNG, writes a sidecar `<path>.license.yaml` with prompt/model/seed/timestamp/policy-URL.
4. Tags output as sRGB IEC61966-2.1 (one Pillow line).
5. On first use, prints a consent gate covering OpenAI policy + IP responsibility + commercial-use caveat; logs to `~/.config/holiday-card/ai-consent.json`. Refuses without acknowledgment.
6. Sets `moderation: "auto"`. Hardcoded.
7. Includes a hard-coded 50-name trademark blocklist (Disney/Marvel/Pokémon/Coca-Cola minimum) checked against the prompt; refuses with explanation.
8. Prints, on every successful generation, the cost incurred and the OpenAI policy URL.
9. README paragraph: "AI image generation is intended for personal use. We do not recommend AI imagery for cards you intend to sell. AI-generated assets may inadvertently contain protected material. You are responsible for what you print and sell."
10. CLAUDE.md updated to *accurately* document what shipped (no Valentine-style documentation lies).

That's it. No `--ai-fill` flag on `create`. No structured `ImageElement.generated` schema in templates yet (waits for Leapfrog 1+2). No category gates yet (the gated occasion taxonomy doesn't exist yet — that's a Leapfrog-2 deliverable). No POD-correctness scaffolding (Leapfrog 1). No CMYK soft-proof (Leapfrog 1). Just the minimum subcommand that lets a user who knows what they're doing bake one image to disk with provenance.

This is a feature defensible at six months because it ships none of the dangerous shapes (no render-time calls, no panel-replacement, no text-to-image-from-scratch, no photo replacement, no AI in templates yet), it preserves reproducibility (asset is on disk, seeded), and it is opt-in three layers deep (extras install + env var + first-use consent). It also doesn't lock the project into the wrong abstraction — the structured schema, category gates, POD-aware sizing, and CMYK transform all arrive later as additive features, not retrofits.

**Whether this v0 *should* ship before the leapfrogs is the panel's substantive disagreement — five critics say no. If the maintainer ships it anyway, this is the version they ship.**

## What the panel would warn against

The seductive shapes that would be wrong, in roughly increasing order of damage:

1. **A `--ai-fill` flag on `holiday-card create` that calls the API at render time.** Kills reproducibility, breaks CI, fails on 2-minute latency, locks the project into a paid third-party dependency in the render path. (Designer, Prepress, POD all explicit.)
2. **Free-text-to-image with no style anchor as the default.** Produces ChatGPT-aesthetic slop, voiceless cards, four-different-burgundies-on-the-same-card incoherence. Disabled-by-default behind a flag literally named `--unsafe-no-style-anchor`. (Designer.)
3. **AI-rendered text on the card.** Bypasses vector text pipeline, gets fingers and small typography wrong, undermines the project's typographic identity. Sentiment is the card; do not outsource it. (Designer + Copywriter.)
4. **AI-generated copy as a default companion to AI-generated imagery.** "A card no one wrote, sent in someone's name. The recipient knows. They always know." If it ever ships, only as selection-from-curated-library, never free generation. (Copywriter, Designer.)
5. **Whole-panel replacement as the default.** Background-fill primitive only; force `--ai-fill-mode panel` to opt into the dangerous version. (POD.)
6. **Photo-card replacement.** Category contradiction. (Buyer, Copywriter, POD.)
7. **AI imagery in sympathy/condolence/religious-iconography contexts without the hard rail.** Worst possible failure mode of the entire feature. (Copywriter, Buyer, Designer, Sandy.)
8. **Marketing this as "AI-generated greeting cards."** That positioning irreversibly forecloses the indie-maker market the consensus pointed the project toward. The Buyer's framing is "the panel actually wants this project to become calendar-driven, taste-led, indie-maker-grade, POD-correct — fundamentally incompatible with being known as an AI card generator." Lead with the human craft. AI is plumbing. (Buyer + Designer.)
9. **Shipping it before `--export-for moo-a6` and the curated taste layer.** Cannibalizes the engineering attention that should go to the moves the panel actually endorsed; the AI-output has nowhere clean to land; the credibility problem deepens; "AI slop on top of engineer-default templates." (Prepress, POD, Designer, Copywriter, Buyer.)
10. **Skipping provenance, disclosure, and trademark scaffolding to "get it out fast."** This is the version that ends with the project named in a Disney DMCA action and a "the open-source tool fueling Etsy's AI card problem" trade-press paragraph. Cheap to ship; expensive to skip; impossible to retrofit reputationally. (Buyer, POD, Prepress.)
11. **Pretending CLAUDE.md is documentation when it's a wishlist.** Repeating the Valentine's-templates-that-don't-exist pattern with AI generation would be a credibility-killing rerun. Document only what ships. (POD, with prior consensus.)
12. **Telling Sandy this is for her.** It isn't, and she's tired of being told. (Sandy, with prior consensus.)

## Single-sentence verdict for a maintainer reading one line

**Don't ship this now — ship `--export-for moo-a6` and the curated taste layer first; then in Q1 2027 ship AI as an authoring-time, image-reference-mode-default, POD-aware, provenance-tagged, category-gated `ai-asset generate` subcommand that bakes assets to disk and never appears in the render path.**
