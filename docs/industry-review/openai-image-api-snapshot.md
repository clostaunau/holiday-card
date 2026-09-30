# OpenAI Image Generation API — Reference for the holiday-card panel

Source: https://developers.openai.com/api/docs/guides/image-generation
(First fetched 2026-05-10. **Size rules re-verified 2026-09-29** for #87
against the guide, the `images.generate` / `images.edit` API reference
(https://developers.openai.com/api/reference/python/resources/images/methods/generate,
…/methods/edit) and the model pages under
https://developers.openai.com/api/docs/models/. Numbers may change again;
`core/ai_assets.MODEL_SIZE_POLICIES` is the in-code copy.)

## Models
- `gpt-image-2` (current; snapshot `gpt-image-2-2026-04-21`) — holiday-card's
  `DEFAULT_AI_MODEL`
- `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare` (new 2026-09-08 snapshots;
  add `xhigh` / `max` quality)
- `gpt-image-1.5` ("our previous image generation model"; the API's
  default model when none is named), `gpt-image-1` (deprecated),
  `gpt-image-1-mini` (legacy)
- `chatgpt-image-latest` is accepted by `images.edit` (no size rules
  published; not in the policy table)

## Accepted `size` per model (verified 2026-09-29)

The same rules apply to `images.generate` and `images.edit`. `quality`
does not change the accepted sizes ("Quality does not restrict available
sizes").

| Model | `size` accepted |
|---|---|
| `gpt-image-1`, `gpt-image-1-mini`, `gpt-image-1.5` | fixed: `1024x1024`, `1536x1024`, `1024x1536` (and `auto`) |
| `gpt-image-2`, `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare` (+ dated snapshots) | any `WIDTHxHEIGHT`: both edges multiples of 16, aspect between 1:3 and 3:1, neither edge > 3840 px, total 655,360–8,294,400 px; above 2560×1440 is "experimental" |

API reference, verbatim: "For `gpt-image-2`, `gpt-image-2-2026-04-21`,
`gpt-image-2.5-sunburst`, `gpt-image-2.5-sunburst-2026-09-08`,
`gpt-image-2.5-flare`, and `gpt-image-2.5-flare-2026-09-08`, arbitrary
resolutions are supported as `WIDTHxHEIGHT` strings, for example
`1536x864`. Width and height must both be divisible by 16 and the
requested aspect ratio must be between 1:3 and 3:1. Resolutions above
`2560x1440` are experimental, and the maximum supported resolution is
`3840x2160`. The requested size must also satisfy the model's current
pixel and edge limits. The standard sizes `1024x1024`, `1536x1024`, and
`1024x1536` are supported by the GPT image models."

holiday-card's use: `moo-a6` bakes 1314×1824 (4.38×6.08 in at 300 PPI).
`gpt-image-2` is asked for 1328×1824 (rounded up to /16, then cropped);
a legacy model is asked for 1024×1536 and upscaled (233.8 PPI native,
which the CLI warns about).

## Input modes
1. Text-to-Image (prompt → image)
2. Image Edits (existing image + prompt → modified image)
3. Image Reference (1+ images as style reference for new generation)
4. Masked Editing (replace specific regions using a mask overlay)

## Output resolutions (2026-05-10 fetch; superseded by the table above)
gpt-image-2 accepts any resolution meeting:
- Max edge: 3840 px
- Both edges multiples of 16 px
- Aspect ratio max 3:1
- Pixel range: 655,360 — 8,294,400

Popular sizes: 1024×1024, 1536×1024, 2048×2048, 3840×2160 (4K).

## Pricing (gpt-image-2 output tokens)
- 1024×1024 low quality:    $0.006 per image
- 1024×1024 medium quality: $0.053 per image
- 1024×1024 high quality:   $0.211 per image
(Plus input text tokens and image-input tokens if editing.)

## Quality / format / speed
- Quality levels: low / medium / high / auto
- Formats: PNG (default), JPEG, WebP with optional compression 0-100%
- "Complex prompts may take up to 2 minutes"
- Text rendering remains imperfect; composition control inconsistent
- Square images generate fastest
- gpt-image-2 does NOT support transparent backgrounds

## Content moderation
- All prompts + images filtered per content policy
- `moderation` parameter: "auto" (stricter, default) or "low"

## Access & rate limits
- Requires API Organization Verification before access
- Specific rate limits not in this doc

## Commercial / IP / copyright
**Not specified in this doc.** Must consult separately:
- https://openai.com/policies/
- https://openai.com/policies/usage-policies/
This is a critical gap for any commercial greeting-card application.
