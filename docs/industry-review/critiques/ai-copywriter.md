# Greeting Card Copywriter — On Adding AI-Generated Imagery to holiday-card

## Verdict in one sentence

Ship it, but ship it as a *cover-only*, *style-tagged*, *category-gated*, *photo-and-illustration-coexisting* feature with a structured prompt schema — anything less reproduces ChatGPT-aesthetic slop on cardstock and severs the cover-to-inside relationship that is the entire reason a greeting card exists.

---

## The threshold question: is the project ready for this?

No, and that matters. The panel consensus is unambiguous that **taste must come before capability** (Tension 3 in `industry_consensus.md`: "30 mediocre templates is worse than 8 great ones"). Adding AI image generation *before* the curated illustrator commission, the sentiment library, and `--voice` flag ship would be a textbook case of feature theater on top of an unsolved credibility problem. The Designer's leapfrog (LLM-emits-YAML against curated assets) and mine (voice-tagged sentiment library) both have the same critical dependency: **the human curation comes first; the LLM composes from it.** AI image generation that is not tethered to curated assets and voice tags will produce the same "default-beige" output, just at $0.21 per generation instead of free.

That said — assuming the curation lands first — the question is *how* to ship it, not whether. Here's the answer.

---

## On the seven specific concerns

### 1. Image-text relationship: the cover-to-inside contract

The project today has **zero concept of image-supports-sentiment**. `ImageElement` (`src/holiday_card/core/models.py`) takes a `source_path` and positions it. The renderer does not know that the cover image and the inside copy are *the same joke split across a fold*. They are two unrelated YAML blocks that happen to live in the same template.

This is the single most important fix before AI generation lands. A real card's image and copy share a **sentiment contract**: the cover sets up, the inside lands. "Cardinal in snow" on the front, "Thinking of you in the quiet hours" inside — that's a card. "Cardinal in snow" on the front, "Wishing you all the best on this special occasion!" inside — that's two unrelated PDFs taped together.

**Required:** a `sentiment_id` field at the *template* level that both the image element and the text element reference. The voice tag, the recipient relationship, and the occasion all flow from one source. The AI prompt is then *composed from* the sentiment, not authored alongside it. If the template's sentiment is `(christmas, witty, sister)`, the generated image inherits a witty visual brief — not whatever the user typed five seconds ago.

### 2. Prompt-as-creative-direction: structured fields, not a single line

A single `--image-prompt "..."` flag is the wrong shape. The most creative writers I know would *love* AI imagery if they could direct it the way they direct an illustrator — by separating subject, style, composition, palette, and negative-space intent. Bury all of that in one string and you get the default OpenAI aesthetic: plasticky, centered, over-saturated, no breathing room for type.

**Proposed structured prompt surface (in YAML, on the image element):**

```yaml
image_elements:
  - generated:
      subject: "single male cardinal on a bare branch, dusting of snow"
      style: watercolor              # tagged, see #3
      composition: "subject left third, large negative space right two-thirds"
      palette_ref: theme             # inherit from template theme, not free-form
      reserve_for_text:              # explicit copy-safe zone
        x: 2.75
        y: 0.5
        width: 2.5
        height: 4.0
      mood: "quiet, devotional, early morning"
      avoid:                         # negatives are 50% of good prompting
        - "no text in image"
        - "no people"
        - "no Christmas tree"
      seed: 42                       # reproducibility — same card next year
```

The free-form one-liner remains, but as a fallback escape hatch (`--image-prompt`), not as the primary surface. Structured fields let the engine inject the voice tag automatically, enforce the copy-safe zone, prevent baked-in text (which OpenAI's text rendering remains imperfect at — see source doc), and reuse the same composition next year via `seed`.

### 3. Sentiment voice + visual voice: tag the styles or don't ship

If the project ships `--voice {warm, witty, spare, devotional, irreverent}` for copy and ships a free-form `style: "..."` field for images, the user can write a witty card and accidentally get a devotional illustration. The two voices must be **co-tagged**, not independently free.

**Proposed visual style vocabulary:**

| Copy voice  | Default visual styles                                              |
|-------------|--------------------------------------------------------------------|
| warm        | watercolor, vintage botanical, soft gouache, hand-lettered         |
| witty       | minimal line drawing, isometric cartoon, single-color silkscreen   |
| spare       | block print, ink wash, single-line contour, monochrome             |
| devotional  | medieval illumination, byzantine icon, stained-glass, gold leaf    |
| irreverent  | zine-style collage, halftone newspaper, sticker, riso              |

A `style: watercolor` value should be one of an enumerated set, each pre-prompted with a battle-tested style sub-prompt and a `--voice` affinity. `style: auto` picks based on the template's voice tag. The user gets cohesion for free; the user who *wants* incoherence has to opt in.

This is also where the curation moat lives: 30 enumerated style tags, each with a hand-tuned sub-prompt that has been visually QA'd, is the same kind of curation work as the sentiment library. Same shape, same value.

### 4. Cards that should NOT have AI imagery: a hard rail

Sympathy. Miscarriage. Pet loss. "Sorry for your loss." Cards to people in active grief or trauma. AI imagery in these contexts is not just lazy — it is *invasive*. The recipient is asked to receive comfort from an image no one chose to make for them. That violates the basic transaction of the card.

**Proposed:** an `ai_imagery_allowed: false` field on the *occasion* type, defaulted on for `sympathy`, `condolence`, `miscarriage`, `pet_loss`, `funeral`, `get_well_serious`, and `divorce_support` (all of which the project doesn't have yet but will). The CLI hard-errors if `--generate-image` is passed against a gated occasion. Override requires `--i-know-what-im-doing` plus a confirmation prompt that explains why the rail exists. This is one of the very few places a piece of open-source software should be opinionated against the user's stated preference. The default should refuse.

The same gate should fire on `--brief` AI authoring (Designer's leapfrog) for the same occasions. The project's worst possible failure mode is auto-generating both an image AND copy for a sympathy card. That ships condolences from a stochastic parrot.

### 5. Photo cards: BOTH/AND, never instead-of

Photo cards are 70%+ of premium card volume. The temptation will be to let AI replace the photo (cheaper, no toddler-wrangling). Resist this. **The sentiment of "here is my actual family" cannot be generated.** A card with a real photo of grandkids says *we exist, we are here, we are yours*. A card with an AI-generated family says nothing — and increasingly, recipients can tell.

The right shape is BOTH: real photo as the subject, AI-generated as the *background* or the *border illustration*. The polaroid frame holds a real face; the surrounding vignette is a watercolor wreath the engine generated to match the room's tones. That's an upgrade to the photo card, not a replacement. The data model should permit, on the same panel, an `ImageElement(source_path=...)` for the photo AND a `ImageElement(generated=...)` for the background, with explicit z-ordering. The CLI should warn (not block) if a photo card has *only* generated imagery and no `source_path`: "Heads up — this card has no human photo. Continue?"

### 6. The blank-inside line

I argued previously for `--blank-inside` as a first-class mode. AI imagery interacts with this beautifully on the front and disastrously on the inside. Specifically:

- **AI cover + blank inside = upgrade to the handwriting card.** This is the best version. The engine produces a beautiful illustrated front; the human writes the inside by hand. The technology serves the relationship.
- **AI cover + AI inside copy = a card no one wrote, sent in someone's name.** This is the version that ends greeting cards as a category. The recipient knows. They always know.

**Proposed rule:** AI image generation and AI copy generation are gated behind *separate* flags (`--generate-image` and `--generate-copy`), and the second one requires explicit opt-in even when the first is on. The CLI should *suggest* `--blank-inside` whenever `--generate-image` is set without `--generate-copy`: "You're generating an illustrated cover. Consider `--blank-inside` to leave room for a handwritten note." This is the nudge architecture that respects what cards are for.

### 7. AI-generated copy that pairs with the AI image

The honest answer: **the project should support it, but reluctantly, and never as the default.** The maintainer will be tempted to auto-pair them — same model, same prompt, one round-trip. Don't. Two separate flags, two separate generations, two separate confirmations. The reason `--message "..."` exists in the CLI today is that the project already implicitly acknowledges humans write the words. Don't quietly walk that back.

If both flags are on, the LLM authoring harness (Leapfrog 3 in the consensus) should still compose copy from the **curated sentiment library**, not generate from scratch. The image prompt and the copy selection share a `sentiment_id`. The library remains the source of taste. The LLM is a selection-and-combination engine, not a free-form ghostwriter. This preserves the moat.

---

## The one card category where AI imagery would be UNAMBIGUOUSLY good

**Custom-illustrated personal-occasion cards where the sender wants imagery the project's hand-drawn library doesn't include and a real photo doesn't exist.** Examples: "card for my friend who just adopted a corgi named Beans" (no Beans photo, no corgi in the asset library); "card for my cousin whose D&D character just hit level 20"; "card for the colleague who's leaving to open a bakery in Lisbon." These are cards where the sender has a *specific image in their head*, no photo can capture it, no stock asset matches it, and the sentiment ("I see the specific thing you love") is the entire point. AI generation here serves the relationship — it lets the sender render the inside joke. With a structured prompt and a copy-safe zone, this is a feature that genuinely couldn't exist without the model.

## The one card category where AI imagery would be UNAMBIGUOUSLY bad

**Sympathy and bereavement cards.** Already argued above. The recipient is in their hardest week. They open an envelope. The image is composed by no one. The presence of generated imagery in that moment is a small, additional cruelty on top of the loss. There is no version of this that is okay. Hard rail, default-on, override requires explicit acknowledgment. If the project ships AI imagery without this gate it ships a feature that will, at some volume, hurt people who are already hurting.

## Proposed UX for the prompt interface: BOTH

A structured YAML schema on `ImageElement.generated` (subject, style, composition, palette_ref, reserve_for_text, mood, avoid, seed) is the *primary* surface — it's how templates are authored, how style tags are enforced, how the copy-safe zone is guaranteed, how reproducibility works. It's also how the future LLM authoring harness (Leapfrog 3) emits image briefs that don't collapse the cover-inside relationship.

A single `--image-prompt "..."` CLI flag is the *escape hatch* — for the user who wants to iterate fast and override the template. When used, it should still inherit the template's `style`, `palette_ref`, and `reserve_for_text` automatically unless explicitly overridden. The free-form line is the front door for power users; the structured schema is the actual shape of the data.

Concretely:

```bash
# Power-user fast path — inherits style + palette + copy-safe zone from template
holiday-card create christmas-watercolor \
  --image-prompt "single cardinal on a snowy birch branch, early morning light" \
  -m "Thinking of you in the quiet hours" \
  --blank-inside

# Template-authoring path — full structured brief in YAML
# (lives in templates/christmas/cardinal_quiet.yaml)
```

This shape lets the project meet the writer where they are (one rich line) while preserving the cohesion that the structured schema enforces.

## Does this change my earlier sentiment-library recommendation?

**No — it strengthens it, and reframes its priority.** The voice-tagged sentiment library is now a hard prerequisite, not just a leapfrog. Without it:

1. The image-style tags have nothing to align to (#3 above breaks).
2. The cover-to-inside sentiment contract has no `sentiment_id` to share (#1 above breaks).
3. The LLM copy-generation flag (#7 above) has nothing curated to compose from, so it falls back to free-form generation, which is exactly the failure mode the library was designed to prevent.
4. The category gates against AI imagery in sympathy contexts have no sympathy templates to *be* in, because the occasion taxonomy is still `christmas | hanukkah | birthday | generic | valentine`. The rail can't fire on a category that doesn't exist.

So the sequence has to be: **sentiment library + voice tags first** (one focused week with a copywriter, per my original critique), **occasion taxonomy expansion to include the gated categories second** (sympathy, condolence, miscarriage, pet_loss — these need to *exist* before the rails can guard them), **structured `ImageElement.generated` schema third**, **CLI `--generate-image` flag with style enumeration fourth**, **`--generate-copy` flag last and reluctantly**, with the suggestion to use `--blank-inside` instead being surfaced at every opportunity.

The library was the right recommendation when copy was the only surface. It is even more the right recommendation now that the engine is about to gain an imagery surface that, without it, will produce a generation of beautifully-rendered cards that no one wrote, no one composed, no one chose, and no one — on receipt — believes was meant for them.

The cards-with-good-copy tool still does not exist. The cards-with-good-copy-AND-cohesive-imagery tool would be a much bigger thing. But only in that order.
