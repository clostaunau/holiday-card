# OpenAI Image Generation API — Reference for the holiday-card panel

Source: https://developers.openai.com/api/docs/guides/image-generation
(Fetched 2026-05-10. Numbers may have changed since.)

## Models
- `gpt-image-2` (latest, recommended)
- `gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini` (legacy)

## Input modes
1. Text-to-Image (prompt → image)
2. Image Edits (existing image + prompt → modified image)
3. Image Reference (1+ images as style reference for new generation)
4. Masked Editing (replace specific regions using a mask overlay)

## Output resolutions
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
