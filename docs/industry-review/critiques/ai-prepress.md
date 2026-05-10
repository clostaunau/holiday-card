# AI Image Generation — Prepress Production Critique

## Verdict in one sentence
AI-generated imagery from gpt-image-2 is a **screen-and-social asset class** that prints acceptably on home inkjet, badly on digital POD, and not at all on offset — and shipping it without explicit guard rails will turn this project's already-shaky preflight story into a generator of unprintable PDFs at scale.

---

## The 3 production showstoppers for AI-generated print

### 1. Color management is fundamentally broken end-to-end
gpt-image-2 emits **8-bit sRGB PNG/JPEG/WebP** with no embedded ICC profile, no CMYK pathway, no soft-proof, and no API hook to constrain the model's palette to a printable gamut. Diffusion models love saturated cyans, magentas, and out-of-gamut emerald greens — exactly the colors that collapse on sRGB→CMYK conversion. A "rich red holly berry" will render as a candy-apple sRGB red that ProPhoto/sRGB→GRACoL flattens to a muddy C15 M100 Y100 K5 brick. Skin tones in any "family Christmas card" prompt will drift orange. Deep navy backgrounds will grey out. There is no `seed` parameter that controls the **color pipeline**, no prompt that reliably says "use printable CMYK gamut only," and no way to round-trip a soft proof through the API. This project has no CMYK in its IR (per the prior critique), so it would be embedding sRGB raster into an already color-unmanaged DeviceRGB PDF — defect on top of defect, no proof path.

### 2. No bleed, no trim safety, no preflight pass
The prior critique already established this codebase has zero bleed support and identical MediaBox/TrimBox/BleedBox. AI images are **rectangular fills with no extensible margin** — once generated, you can't ask the model to "extend the design 0.125" past trim" without re-generating (and getting a *different* image). The scene contents go right to the pixel edges with no safe-area discipline. A user who places an AI background panel will get the same white-sliver-at-the-cut defect as the existing flooded panels, except now you also can't fix it manually because the asset is fused pixels. POD preflight (Smartpress, MOO, Vistaprint Pro) will reject these for **all three** of: sub-300-DPI at the actual print size users will pick, RGB-not-CMYK, and no-bleed. Three independent rejections from one asset.

### 3. Stochastic generation destroys reprintability
Print production is **a reprint workflow**. A customer who orders 50 cards in November and 50 more in February expects identical product. AI generation is non-deterministic — even with prompt + seed pinned, model version drift (gpt-image-2 → gpt-image-2.1 → deprecation) means the *same YAML template a year later* renders a different card. There is no way to version-pin an OpenAI model in perpetuity; legacy models get retired (the doc already lists `gpt-image-1`, `1-mini`, `1.5` as "legacy"). For a project whose entire value proposition to the Tyler-engineer audience is "version-controlled, CI-rendered, reproducibly-built greeting cards as code," **embedding a stochastic black-box service kills the reproducibility moat**. Worst case: the YAML lives in git, the rendered card lives in git, the model generating the embedded image is gone, and the next CI build produces a substantively different card from the same source — silently.

---

## The 2 production wins (where AI imagery is actually GOOD for print)

### Win 1: Background textures and abstract decorative fills
AI is genuinely good at producing **non-representational, non-text decorative elements**: a watercolor wash, a snowflake-pattern repeat tile, a textured paper-stock simulation, an abstract floral border. These survive sRGB→CMYK conversion gracefully (no skin tones to ruin, no brand-critical reds), have no text to mis-render, and the diffusion-edge softness *helps* rather than hurts because they're meant to read as painterly. For these uses gpt-image-2 at high-quality 2048×2048 produces a $0.21 asset that competes with stock-image libraries. **Cache it once, embed it as a static asset, treat it as a stock illustration**, not as a live API call per render.

### Win 2: Pre-rendered hero illustrations baked into the curated asset library
The panel consensus already wants a curated illustrator commission for ~30 hand-drawn SVG path assets. AI generation could produce **draft compositions** (rasters, not vectors) for the illustrator to either trace into vector paths or use as moodboard reference, and could produce **secondary tier** assets for templates the illustrator budget doesn't cover. Generated *once*, vetted by a human, color-corrected manually, embedded at known DPI as a static file in the repo, treated identically to any other licensed stock illustration. **The win is in pre-production, not in render-time generation.**

---

## Recommended scope: should this ship? In what form?

**Ship a constrained, opinionated, asset-baking subcommand. Do NOT ship live render-time API calls inside the card pipeline.**

Specifically:

```bash
holiday-card ai-asset generate \
  --prompt "watercolor pine bough border, sage green and burgundy" \
  --size 2048x2048 \
  --quality high \
  --out assets/ai/pine-bough-border.png \
  --license-record assets/ai/pine-bough-border.license.yaml
```

What this subcommand does (the guard rails):

1. **One-shot, never live**: image is generated, written to disk, and committed to git as a normal asset. The card render pipeline only ever sees a static file. No API call during `holiday-card create`. This preserves reproducibility — once committed, the asset is frozen.
2. **License-record sidecar required**: writes a YAML companion file capturing the prompt, model id, model version, generation timestamp, and a placeholder for the user to assert their commercial-use determination per OpenAI's then-current policy. Refuse to use the asset in a print-target build if the sidecar is missing.
3. **Mandatory `Pillow` post-processing pass**: convert sRGB to CMYK using a bundled GRACoL2013 ICC profile, soft-proof preview to PNG, embed the ICC profile in the saved TIFF/PDF asset, downsample/sharpen to 350 DPI at the declared use-size. Refuse to embed any AI asset into a `--export-for moo-a6` build that hasn't been through this pass.
4. **Block AI-generated text**: the asset generator should reject prompts containing quoted strings ("...", '...') with a hard error and a message saying "AI text rendering is unreliable; use the project's vector text element layer instead." All copy goes through the existing sharp-vector text element, layered *over* the AI background.
5. **Bleed-aware sizing**: when generating an asset intended as a panel background, require a `--for-panel` flag that automatically sizes the asset to *trim + bleed* dimensions at 350 DPI, with a 0.25" safe-margin guide overlaid in the soft-proof preview so the user can see what will get cropped.
6. **Hard-gate the `[ai]` extras**: `pip install holiday-card[ai]` adds the dependency, requires `OPENAI_API_KEY`, and prints a one-time warning on first use about IP/commercial-use uncertainty and the unsuitability for offset print.
7. **Tier-restrict the output**: any template that embeds an AI-sourced asset gets tagged in metadata and **refuses to compile under `--export-for vistaprint-pro` or `--export-for catprint`** until the user passes `--accept-ai-asset-risks`. Home and POD-A6 tiers compile freely.

Conspicuously **not** in scope:
- Live render-time generation
- AI for text content rendered into the image
- AI for photos of recognizable people (legal landmine even setting print quality aside)
- AI as the primary illustration source for shipped templates (the curated illustrator commission still needs to happen — AI is for *user-generated* assets and for *reference material*, not for the project's flagship aesthetic)

---

## Honest answer: would a print shop accept these PDFs? At what tier?

**Tier 1 (home inkjet):** Yes, with the same reservations as the existing project. The user folds, accepts the soft edges, doesn't notice the color drift because their inkjet is also uncalibrated. Fine.

**Tier 2 (POD: MOO, Vistaprint consumer, Printful):** Conditional yes, *only* if the post-processing pass above is mandatory. Without CMYK conversion + bleed extension + 300+ DPI assertion + ICC embedding, MOO's preflight rejects on color space alone, before even looking at the bleed problem. With the post-processing pass, it'll pass preflight but the printed result will be visibly softer and less color-accurate than a vector or photographic asset of the same size. Customer-acceptable for casual users, will generate complaints from anyone who's ordered "real" cards before.

**Tier 3 (Vistaprint Pro, Smartpress, Catprint, any press broker):** No. These services do PDF/X-1a or X-4 preflight, demand embedded ICC, demand distinct trim/bleed boxes, demand CMYK or named spot colors, and many will additionally flag "low-frequency-content" raster (i.e. AI's plasticky textures) as suspect. Even with the post-processing pass, the diffusion-edge softness on hero subjects will fail any human prepress operator's visual review at this tier. The maintainer should explicitly **block AI-asset templates from compiling to these targets** rather than ship a flag that lets users learn the hard way after a $200 print order is rejected.

**Tier 4 (offset, foiling, finishing):** Absolutely not. Discussion not even worth having. Offset wants spot colors and clean separations; AI output is the opposite of that.

---

## What this means for the leapfrog roadmap

The panel consensus put **`--export-for moo-a6` end-to-end** as Leapfrog 1 and **AI-native authoring against the curated asset library** as Leapfrog 3 (with Leapfrog 2 — curated taste — as a critical dependency). Adding AI image *generation* before either of those is **out of order**:

- Without bleed + CMYK + ICC + distinct trim boxes (Leapfrog 1 prerequisites), the AI asset has nowhere clean to land.
- Without the curated taste layer (Leapfrog 2), users will compose AI slop on top of engineer-default templates and the credibility problem deepens.
- The right home for AI in this project is **Leapfrog 3's authoring harness composing YAML against curated primitives** — i.e. an LLM choosing layouts, fonts, colors, and arranging existing illustrator assets — *not* gpt-image-2 generating raster pixels at render time.

Ship the asset-baking subcommand as a small Q4 experiment after Leapfrogs 1 and 2 land. Do not let it become the headline feature. The headline feature is still the press-ready PDF, and AI imagery actively undermines that headline.
