# OpenRouter image API snapshot

> This file was created by #148 with only the curated-models section. #140
> (the owner-run live verification of `POST /api/v1/images`) adds the
> request / response snapshot and the measured W×H per resolution tier.

## Curated image models (allowlist)

The allowlist lives in `src/holiday_card/core/ai_openrouter_models.py`
(`OPENROUTER_IMAGE_MODELS`). It is checked in and never fetched at run time
(O2 / spec §7). An id that is not listed is refused. Each entry pins **one**
endpoint (`provider_tag`, sent as `provider.only`, with no fallbacks, O6) and
records what that endpoint advertises, so a value outside the endpoint's
enum is refused locally instead of being clamped (§5.3).

**Fetched 2026-09-30** from the unauthenticated catalogue:
`GET /api/v1/images/models`, `GET /api/v1/images/models/{author}/{slug}/endpoints`
and `GET /api/v1/providers`. The recording, trimmed to these models plus
`recraft/recraft-v4.1`, is `tests/fixtures/openrouter/catalogue/`.

| id | provider_tag | aspect_ratios ("auto" removed) | resolutions | refs | seed | output_formats | transparent | passthrough | pricing (billable / unit / USD) |
|---|---|---|---|---|---|---|---|---|---|
| `google/gemini-3-pro-image` | `google-ai-studio/global` | 1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9 | 1K 2K 4K | 0–14 | no | — | no | cachedContent | input_image/token/0.000002; output_image/token/0.00012 |
| `google/gemini-3.1-flash-image` | `google-ai-studio` | 1:1 1:4 1:8 2:3 3:2 3:4 4:1 4:3 4:5 5:4 8:1 9:16 16:9 21:9 | 512 1K 2K 4K | 0–14 | no | — | no | cachedContent | output_image/token/0.00006 |
| `black-forest-labs/flux.2-pro` | `black-forest-labs` | 1:1 4:3 3:4 3:2 2:3 16:9 9:16 21:9 | — | 0–8 | yes | png jpeg | no | steps guidance safety_tolerance | output_image/megapixel/0.03 |
| `bytedance-seed/seedream-4.5` | `seed` | 1:1 1:2 2:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 9:19.5 19.5:9 9:20 20:9 9:21 21:9 | 1K 2K 4K | 0–14 | yes | — | no | — | output_image/image/0.04; input_image/image/0 |
| `openai/gpt-image-2` | `openai` | 1:1 3:2 2:3 4:3 3:4 16:9 9:16 21:9 | — | 0–16 | no | — | no (`auto`, `opaque` only) | moderation | input_image/token/0.000008; input_text/token/0.000005; output_image/token/0.00003 |

Why these five: `gemini-3-pro-image` is the spec's provisional default
(§6.8), and its AI Studio endpoint is pinned because it offers 4K (Vertex
offers only 1K / 2K). `gemini-3.1-flash-image` is the cheaper Google option.
`flux.2-pro` and `seedream-4.5` are the two that advertise `seed`.
`gpt-image-2` allows a comparison with the OpenAI-direct path; it has no
resolution tier, so expect a low-PPI warning at A6. No default is set here
(#150, after #140).

Left out: `recraft/recraft-v4.1`. On 2026-09-30 it has one endpoint
(`recraft`, 0–1 references, no resolution tier, output_image/image/0.035),
but `/providers` gives it `terms_of_service_url: null`. Also left out: every
model whose endpoint takes at most 0 references (S2).

### Terms review (2026-09-30)

`upstream_terms_url` is recorded in each generated asset's sidecar (#150),
so it must be the page that governs **output ownership** for API use. The
URL `/providers` lists was not that page for any of the five, so each entry
records the more specific page. This is why the refresh script does not
report `upstream_terms_url` as drift: the value is reviewed, not copied.

| entry | `/providers` URL | governs output? | recorded URL | personal use |
|---|---|---|---|---|
| both Gemini entries (`google-ai-studio`) | `https://cloud.google.com/terms/` | no: GCP-wide terms, which refer generated output to the service-specific terms | `https://ai.google.dev/gemini-api/terms` ("Google won't claim ownership over that content") | **unclear**: the Gemini API terms say the API is "for developers … for professional or business purposes, not for consumer use"; how that applies through OpenRouter is not stated. Kept; the owner may drop them. |
| `flux.2-pro` | `https://bfl.ai/legal/terms-of-service` | partly: the consumer page defers API use to the Developer Terms | `https://bfl.ai/legal/developer-terms-of-service` ("you own all right, title, and interest in and to Output … personal or commercial purposes") | yes |
| `seedream-4.5` | `https://docs.byteplus.com/en/docs/legal/docs-terms-of-service` | no: refers to the General Terms for AI Services | `https://docs.byteplus.com/en/docs/legal/AI-Services-terms` ("you own the Output … BytePlus does not claim ownership") | yes (label AI content where required) |
| `gpt-image-2` | `https://openai.com/policies/row-terms-of-use/` | partly: individuals' terms, which say the Business Terms govern the API | `https://openai.com/policies/services-agreement/` ("Customer … owns all Output") | yes |

Dropping an entry is a curation decision: delete it from `_ENTRIES`, and the
drift guard in `tests/unit/test_ai_openrouter_models.py` changes with it.

### Resolution tiers: an assumption

`RESOLUTION_LONG_EDGE_PX` maps each tier to a nominal **long edge**:
`512` → 512, `768` → 768, `1K` → 1024, `2K` → 2048, `4K` → 4096. The
chooser (`ai_assets.choose_aspect_shape`) asks for the smallest tier whose
long edge covers the bake's, or the largest tier offered. OpenRouter does not
publish per-model pixel sizes. If #140 finds that a tier means something else
(the short edge, or megapixels), change the table and this section together.

For the two export targets with geometry, every curated model picks `3:4`:
letter (2550×3300) gets `4K` and moo-a6 (1314×1824) gets `2K`, or no tier
for flux.2-pro and gpt-image-2.

### Pricing bounds for `--max-cost` (2026-09-30, #151)

`--max-cost` multiplies each endpoint price row by an upper bound. The
bounds are human-maintained fields on each entry, cited in its
`bound_source`; the refresh script carries them over and never reports
them as drift.

| model | bound | source (read 2026-09-30) |
|---|---|---|
| `google/gemini-3-pro-image` | output tokens 1K 1120, 2K 1120, 4K 2000; 560 tokens per input image | <https://ai.google.dev/gemini-api/docs/pricing> |
| `google/gemini-3.1-flash-image` | output tokens 512 747, 1K 1120, 2K 1680, 4K 2520 (no input-image price row) | <https://ai.google.dev/gemini-api/docs/pricing> |
| `black-forest-labs/flux.2-pro` | 4.194304 MP output (2048×2048: "up to 4MP (e.g., 2048x2048)") | <https://help.bfl.ai/articles/8531149640-what-are-the-resolution-limits> |
| `bytedance-seed/seedream-4.5` | none needed (priced per image) | — |
| `openai/gpt-image-2` | **none recorded**: no token count per output size, so `--max-cost` exits 2 | — |

#140's live call reports `usage.completion_tokens`; it must stay at or
below the recorded tier bound (the `ok_png` fixture's 1120 at 2K does).

### Refreshing

`scripts/refresh_openrouter_models.py` is dev-only and is never run in CI.
It reads the three public endpoints (no key) and never writes under `src/`:

```bash
uv run python scripts/refresh_openrouter_models.py --save-dir /tmp/or          # drift table; exit 1 if any
uv run python scripts/refresh_openrouter_models.py --from-dir /tmp/or --emit python   # paste-ready entries
uv run python scripts/refresh_openrouter_models.py --from-dir /tmp/or --emit python \
    --add recraft/recraft-v4.1@recraft                                         # a candidate entry
```

A candidate whose provider has no terms URL is printed with
`upstream_terms_url="TODO-REVIEW"`, which `OpenRouterModel.__post_init__`
refuses. So an unreviewed entry cannot be pasted in by accident. Review the
terms, update the entries, this table and `snapshot_date`, and re-record the
fixture with `--save-dir`, trimmed as above.

## Live verification (#140)

Sources: `POST https://openrouter.ai/api/v1/images` (billed calls, owner-run)
and the three catalogue endpoints above, re-read without a key.
(Catalogue re-fetched **2026-10-01 04:21 UTC**. Billed calls run
**TODO(owner): YYYY-MM-DD HH:MM UTC**.) This section answers the spec's §3
"Live verification still owed" list
(`docs/specs/2026-09-30-openrouter-image-provider.md`), which was written
without a key.

No credential, image or raw response body is recorded here. Each `b64_json`
is replaced by its length and a sha256 prefix. Response headers are copied
without `set-cookie`, and request headers are limited to `Content-Type` and
the attribution headers.

### Answers

| # | Question | Answer | Evidence |
|---|---|---|---|
| Q1 | Does `/images` return `X-Generation-Id`? | TODO(owner) | Call A headers |
| Q2 | Default model W×H at `3:4` / `2K` (and `4K` if call B ran); native PPI at moo-a6 | TODO(owner) | Call A (B) decode line |
| Q3 | Unadvertised `seed` on `openai/gpt-image-2`: 400 or ignored? | TODO(owner) | Call C |
| Q4 | Shape of an image content-policy refusal | TODO(owner) | Call E |
| Q5 | Is `size: "1328x1824"` honoured on `openai/gpt-image-2`? | TODO(owner) | Call D decode line |
| Q6 | Unadvertised `output_format` on the Gemini AI Studio endpoint: accepted, ignored or 400? | TODO(owner) | Call A `media_type` / status |
| T1 | Is `2K` a 2048 px **long edge**, as `RESOLUTION_LONG_EDGE_PX` assumes (§ Resolution tiers)? | TODO(owner) | Call A (B) decode line |
| T2 | Are Gemini `2K` `usage.completion_tokens` ≤ the 1120 bound (§ Pricing bounds)? | TODO(owner) | Call A `usage` |

Whatever Q5 shows, production never sends `size` (spec §5.3).

**Spend:** TODO(owner): billed calls N (≤ 5); total `usage.cost` $X (≤ $1.00).
`/key` after the run: `limit` TODO, `limit_remaining` TODO, `usage` TODO.

**Account privacy settings at run time** (`/images` has no per-request
`data_collection`, spec §3 / O3): TODO(owner): training toggle, logging toggle.

### Catalogue deltas since 2026-09-30 (Step 0)

**None.** `scripts/refresh_openrouter_models.py` reported **0 differences in
5 curated models**; 50 catalogue models are not curated. The catalogue still
lists **55** image models. None of the issue's stop conditions fired: the
`google-ai-studio/global` tag, the `2K` / `4K` tiers and `3:4` are all still
offered for `google/gemini-3-pro-image`. Vertex still offers only `1K` / `2K`.
Neither Gemini endpoint advertises `seed` or `output_format`, and
`openai/gpt-image-2` advertises neither. So calls A, C and D each send a
parameter the endpoint does not advertise, on purpose.

### Per-call records

Common request headers: `Content-Type: application/json`,
`X-OpenRouter-Title: holiday-card`,
`HTTP-Referer: https://github.com/clostaunau/holiday-card`,
`X-OpenRouter-App-Visibility: hidden`. The reference image (`__REF__`) is
`data:image/png;base64,<64×64 flat RGB (46, 94, 62) PNG, 186 bytes>`.

#### Call A: default candidate, `3:4` / `2K`, the §6.2 body shape

```json
{"model": "google/gemini-3-pro-image",
 "prompt": "Watercolor pine bough border with red berries on a plain cream background. No text, no lettering.",
 "n": 1, "aspect_ratio": "3:4", "resolution": "2K", "output_format": "png",
 "input_references": [{"type": "image_url", "image_url": {"url": "__REF__"}}],
 "provider": {"only": ["google-ai-studio/global"], "allow_fallbacks": false}}
```

- UTC / status / `time_total`: TODO(owner)
- Response headers (minus `set-cookie`): TODO(owner)
- Redacted body: TODO(owner)
- Decode line (`media_type`, format, mode, W×H, frames): TODO(owner)
- Native PPI at moo-a6, `min(w/1314, h/1824) × 300`: TODO(owner)
- A2 (only if A was a 400 naming `output_format`; same body without it): TODO(owner) or "not needed"

#### Call B: `4K`, run only if A is below 1314×1824 on either axis

Same body as A with `"resolution": "4K"`.

- Ran? TODO(owner): yes, or "not needed" because A decoded to W×H ≥ 1314×1824
- UTC / status / `time_total`, headers, redacted body, decode line, native PPI: TODO(owner)

#### Call C: unadvertised `seed` on `openai/gpt-image-2`, plus its `3:4` size

```json
{"model": "openai/gpt-image-2",
 "prompt": "Watercolor pine bough border with red berries on a plain cream background. No text, no lettering.",
 "n": 1, "aspect_ratio": "3:4", "quality": "low", "output_format": "png", "seed": 42,
 "provider": {"only": ["openai"], "allow_fallbacks": false}}
```

`quality: low`. The spec's single data point (16:9 → 1536×864) used `high`.

- UTC / status / `time_total`: TODO(owner)
- Response headers (minus `set-cookie`): TODO(owner)
- Redacted body, or the 400 envelope verbatim: TODO(owner)
- Decode line and native PPI: TODO(owner)
- C2 (only if C was a 400; same body without `seed`): TODO(owner) or "not needed"

#### Call D: `size: "1328x1824"` on `openai/gpt-image-2`

```json
{"model": "openai/gpt-image-2",
 "prompt": "Watercolor pine bough border with red berries on a plain cream background. No text, no lettering.",
 "n": 1, "size": "1328x1824", "quality": "low", "output_format": "png",
 "provider": {"only": ["openai"], "allow_fallbacks": false}}
```

The body has no `aspect_ratio` on purpose: the docs say an explicit size
with a mismatched ratio is a 400.

- UTC / status / `time_total`: TODO(owner)
- Response headers (minus `set-cookie`): TODO(owner)
- Redacted body: TODO(owner)
- Decode line: TODO(owner). Honoured only if exactly 1328×1824.

#### Call E: content-policy refusal shape

```json
{"model": "google/gemini-3-pro-image",
 "prompt": "Mickey Mouse wearing a Santa hat, official Disney character art",
 "n": 1, "aspect_ratio": "3:4", "resolution": "1K", "output_format": "png",
 "provider": {"only": ["google-ai-studio/global"], "allow_fallbacks": false}}
```

This is the trademark prompt that the local rails already refuse
(`tests/integration/test_ai_asset_cli.py`).

- UTC / status / `time_total`: TODO(owner)
- If 403: the full error envelope verbatim, including
  `error.metadata.error_type` and `provider_code`: TODO(owner)
- If 200: "upstream did not refuse". The image is deleted, and
  `core/ai_rails.py` is then the only trademark guard: TODO(owner)

#### Free follow-ups

- `GET /api/v1/generation?id=<X-Generation-Id>`, only if a call returned the
  header: `provider_name`, `model`, `total_cost`: TODO(owner)

### Recommended default

TODO(owner): fill in after calls A and B.

| Field | Value |
|---|---|
| Model id | TODO |
| Pinned `provider_tag` | TODO |
| Aspect / resolution for moo-a6 | TODO |
| Observed W×H | TODO |
| Native PPI at moo-a6 | TODO. If it is below 300, name the tier or model that clears it. |
| Observed cost (`usage.cost`) | TODO |
| `input_references` range | 0–14 (catalogue, 2026-10-01) |

### Consequences for later issues

#148–#153 and #168 all landed on `main` before this verification ran. So
each answer is checked against the shipped code. Wherever an answer
contradicts it, a follow-up issue is filed; this docs-only PR changes no code.

| Answer | Shipped behaviour | Consequence |
|---|---|---|
| Q1 | `ai_openrouter` reads `x-generation-id` when present (#149) | TODO |
| Q2 / T1 | `PROVIDERS[OPENROUTER].default_model` is `google/gemini-3-pro-image` (#150); `2K` → 2048 long edge (#148) | TODO |
| Q3 | a seed on an entry with `seed=False` is refused locally, before any call (#149) | TODO |
| Q4 | 403 with `error_type` in {`content_policy_violation`, `refusal`} → provider refused (#149) | TODO |
| Q5 | `size` is never sent (§5.3) | None: the rule stands whatever the answer |
| Q6 | `output_format: "png"` is sent only when the entry lists `png` (#149); the Gemini entry lists none | TODO |
| T2 | Gemini `2K` bound is 1120 output tokens (#151) | TODO |
