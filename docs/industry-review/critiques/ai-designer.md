# Greeting Card Designer Critique — OpenAI Image Generation in holiday-card

## Verdict in one sentence

Bolting `gpt-image-2` onto this project as a text-to-image card-filler is the single fastest way to vaporize what little design credibility the architecture still has — but using the same API in *image-reference* mode against a curated illustrator library is exactly the leapfrog I described last time, and that version I will defend.

## The single biggest design risk

**It produces voicelessness at scale.** Greeting cards have *hands* — Em & Friends has a hand, Rifle Paper has a hand, Sugar Paper has a hand, the kid at the kitchen table with the glitter glue has a hand. A 1024×1024 PNG from a foundation model has no hand. It has the synthetic-mid-2020s aesthetic that everyone who has used ChatGPT for ten minutes now recognizes within half a second: over-rendered surfaces, sourceless soft lighting, motifs floating in shallow depth-of-field, the Pixar-still gloss, the tell-tale weirdness in fingers and small typography, the suspiciously plump cherub. Sending that as a Valentine reads as effort *avoided*, not effort spent. A condolence card generated this way would be insulting. A first-birthday card might pass — once. The Etsy makers competing with AI-flood shops are already being hollowed out; this project would be picking a side in that fight and picking it wrong.

Stigma aside, there is the harder problem: **a card has one identity, and four panels generated separately have four identities.** A user types "watercolor poinsettia, sage and burgundy" four times and gets four different lighting setups, four different leaf morphologies, four different burgundies, four different paper-grain textures. The card *cannot cohere*. The IR can compose these images into the layout — it cannot make them belong to each other. Image-reference mode is the only thing that comes close to fixing this, and only if the *first* image is locked as the style anchor.

## The single biggest design opportunity

**Style-amplification of human-illustrated assets.** The illustrator commission I recommended last quarter — ~30 hand-drawn SVG path motifs — is not a substitute for AI imagery; it is the *seed corn* that makes AI imagery into something worth shipping. The move is:

1. Commission the illustrator. Get 30 motifs in a single, opinionated, recognizable hand.
2. Render those motifs to PNG.
3. Pass them to `gpt-image-2` as the image-reference input, with a constrained prompt template: "Extend this illustration style. Subject: {motif}. Palette: {three hex values from the theme}. Composition: {centered | corner | border-frame}. No text. No people. Flat background, single hue, render at 1536×1024."
4. The model returns *variations and extensions* of the illustrator's hand, not generic Pixar slop.

That gives the project something no incumbent has: a recognizable visual identity (the illustrator's) *amplified by* an unlimited variety engine (the model). Hallmark has identity-without-variety. Canva has variety-without-identity. The thing this project can credibly own is **identity + variety**, and image-reference mode is the bridge between them. The illustrator commission becomes *more* valuable, not less, because every dollar paid to the illustrator now anchors the style of every AI-extended asset the project generates for the next year.

## The product shape I would actually endorse

Not "fill this panel with an AI image." That's the obvious move and it's the AI-slop trap. The shape I'd endorse has four properties, in priority order:

**1. AI is a motif-generator, not a panel-filler.** The model never generates a whole card. It generates *one motif* (a poinsettia, a menorah candle, a heart in the house style) that becomes one `image_element` in the IR, placed at a known coordinate by the template, with text and composition controlled by the human-authored YAML. The card's layout, typography, hierarchy, fold geometry, bleed, and read-order remain under human/IR control. The AI only fills a *known hole*.

**2. Every motif is style-anchored to the curated illustrator library.** The default authoring path is image-reference mode against `decorative_elements/*.png` (rendered from the SVG path assets). Text-to-image mode with no reference is disabled in the default CLI; available only behind `--unsafe-no-style-anchor` for experimentation. This single guardrail is what separates "card with the project's voice" from "card with ChatGPT's voice." The flag exists not because the option needs to be available but because *naming it that way* tells every user what the right default is.

**3. Generations are cached, named, and committed to the asset library, not regenerated per render.** A motif generated for `valentine-hearts/cover-anchor.png` is checked into the repo (or a CDN-backed `assets/generated/` directory with a manifest). It carries provenance: the prompt, the seed, the reference image, the model version, the date, the cost. Reproducibility — the architectural virtue the panel agreed on — is preserved. Tyler's CI build does not call `gpt-image-2` on every push at $0.21 a pop; it pulls a deterministic, version-controlled PNG. The model is invoked *during authoring*, not during rendering. This also sidesteps the 2-minute latency problem entirely — latency only matters in the authoring loop, where 30-90 seconds is fine, not in the render loop, where it would be fatal.

**4. The card declares its provenance.** A `provenance` field in the template YAML lists every AI-generated asset, its prompt, its reference image, and the model. The CLI's `--show-provenance` flag prints it. For occasions where AI imagery is wrong — sympathy, religious cards, condolence, anniversary cards for the people who care — the CLI refuses to use AI-generated motifs entirely (`--no-ai` is the default for `occasion: sympathy`, `occasion: religious-condolence`, and `occasion: anniversary` unless explicitly overridden). The product *knows* where AI belongs and where it doesn't, and the defaults encode that knowledge. A user who sends a grieving friend an AI-generated condolence card had to *fight* the tool to do it.

Composition and hierarchy are preserved because the AI never sees the card. It sees a square or rectangular crop, generates within it, returns the PNG, and the IR composes it into the layout with text positioned around it by the template author. The 2-minute latency is amortized over the asset library, not per-card. The lack of transparent backgrounds is solved by either (a) generating motifs against a known flat background that matches the panel and bleeds into it, or (b) running the output through the existing Pillow-based image-effects pipeline with a chroma-key or alpha-matte step. The imperfect text rendering is moot because **the AI never renders text in this product** — text is always human-authored, ReportLab-rendered, embedded font, optically kerned where the IR supports it.

The bolt-on version of this feature — "type a prompt, get a card panel" — fails on all seven of the questions the maintainer raised. The shape above fails on none of them, and it is the version I would endorse shipping, after the curation work in Q3 lands, as the Q4 leapfrog. **In the consensus document's sequencing, this is Leapfrog 3 done correctly.** The panel already agreed: *curation first, AI second.* This critique is the more specific version of that agreement: curation first, and then AI as the *amplifier* of curation, never as the substitute for it.

## Does this change my earlier illustrator-commission recommendation

**No — it strengthens it.** Last quarter I said the commission was required to escape "looks like an engineer made it." This quarter I am saying it is *also* required to escape "looks like ChatGPT made it." Those are the same failure mode wearing two different jackets: both produce cards with no human hand visible. The illustrator commission is the only known thing that solves either. The AI imagery option *raises the stakes* on the commission — without it, the cheap shortcut (text-to-image, no reference) wins the maintainer's roadmap by default and the project ships AI slop. With the commission already in hand, the AI feature has somewhere to anchor and becomes a force multiplier instead of a substitute.

If the maintainer is choosing between "commission the illustrator OR ship the AI feature" — commission the illustrator. Every time. If the maintainer is choosing between "commission the illustrator AND THEN ship AI in image-reference mode against those assets" — that's the leapfrog. Same recommendation as before, now with an additional reason it cannot be skipped.

## What I will not approve

- **Text-to-image with no style anchor as a default code path.** Ship it disabled, behind a flag, with a name that signals it is the wrong choice.
- **AI-generated text on the card.** The model's text rendering is imperfect, and even if it were perfect, *the sentiment is the card*. Outsourcing the words to a foundation model is what makes recipients feel sent to. Sentiment library, voice tags, human-curated copy. The Copywriter and I agree on this — do not let the AI feature backdoor copy generation.
- **Per-render API calls in the render path.** Authoring time, yes. Render time, never. The reproducibility property of this project is one of the three things that makes it interesting; do not trade it for a feature.
- **Shipping this before the illustrator library exists.** Without the style anchor, this feature *cannot produce cards with identity*. It will produce cards with the synthetic-2020s aesthetic and the project will spend its remaining reputation on them. Sequence matters. Curation first.
- **Marketing this feature as "AI-generated greeting cards."** The product the panel could endorse is "illustrated greeting cards, style-extended by AI, human-curated, human-composed." Lead with the human craft. The AI is plumbing.
