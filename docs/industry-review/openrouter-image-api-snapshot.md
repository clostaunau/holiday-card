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

### Resolution tiers: nominal, overridden per model by measurement (#174)

`RESOLUTION_LONG_EDGE_PX` maps each tier to a nominal **long edge**:
`512` → 512, `768` → 768, `1K` → 1024, `2K` → 2048, `4K` → 4096.
OpenRouter does not publish per-model pixel sizes, and #140 found the
table wrong for `google/gemini-3-pro-image`: at `3:4`, `2K` decodes to
**1792×2400** and `4K` to **3584×4800** (calls A, B). Google prices `2K` as
"up to 2048x2048", so a tier is an area budget (about 4.2 MP at `2K`) and
its long edge grows as the aspect leaves 1:1.

So the table stays nominal and an entry may override a tier with
`observed_long_edge_px`, cited in `observed_source`. Only the Gemini 3 Pro
entry does: `2K` → 2400, `4K` → 4800, measured at `3:4` (the aspect every
export target picks; it is not valid for a 1:1 request). `1K` was not
observed (call E was refused), so it stays nominal at 1024. Other entries
have no measurement and stay nominal. The chooser
(`ai_assets.choose_aspect_shape`) asks for the smallest tier whose long
edge (`OpenRouterModel.tier_long_edge_px`) covers the bake's, or the
largest tier offered; a megapixel-priced `--max-cost` fallback uses the
same long edge. Record a new measurement here and on the entry together.

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
| `google/gemini-3-pro-image` | output tokens 1K 1120, 2K 1120, 4K 2000; 560 tokens per input image; **+256 non-image output tokens at $0.000012** ("$12.00 (text and thinking)" per 1M; 256 is a margin over #140's 87 / 101, #173) | <https://ai.google.dev/gemini-api/docs/pricing> |
| `google/gemini-3.1-flash-image` | output tokens 512 747, 1K 1120, 2K 1680, 4K 2520 (no input-image price row); **+256 non-image output tokens at $0.0000015** ("$1.50 (text and thinking)" per 1M; same margin, #173) | <https://ai.google.dev/gemini-api/docs/pricing> |
| `black-forest-labs/flux.2-pro` | 4.194304 MP output (2048×2048: "up to 4MP (e.g., 2048x2048)") | <https://help.bfl.ai/articles/8531149640-what-are-the-resolution-limits> |
| `bytedance-seed/seedream-4.5` | none needed (priced per image) | — |
| `openai/gpt-image-2` | **none recorded**: no token count per output size, so `--max-cost` exits 2 | — |

#140's live calls report `usage.completion_tokens`: the image tokens
(`completion_tokens_details.image_tokens`) must stay at or below the tier
bound, and the rest (87 at 2K, 101 at 4K) at or below `output_text_tokens`.
Those extra tokens are billed at the text-output rate, which the catalogue's
`pricing[]` has no row for, so each Gemini entry records the rate itself
(`output_text_usd_per_token`). With that allowance the 3:4 estimate with one
reference is $0.138592 at 2K and $0.244192 at 4K, above the billed $0.136002
and $0.241770 (`TestObservedGeminiCost`, #173).

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

Sources: `POST https://openrouter.ai/api/v1/images` (billed calls, run by the
owner) and the three catalogue endpoints above, re-read without a key.
(Catalogue re-fetched **2026-10-01 04:21 UTC**. Billed calls run
**2026-10-01 04:34–04:36 UTC** with a dedicated key.) This section answers
the spec's §3 "Live verification still owed" list
(`docs/specs/2026-09-30-openrouter-image-provider.md`), which was written
without a key.

No credential, image or raw response body is recorded here. Each `b64_json`
is replaced by its length and a sha256 prefix. Response headers are copied
without `set-cookie`, and request headers are limited to `Content-Type` and
the attribution headers.

### Answers

| # | Question | Answer | Evidence |
|---|---|---|---|
| Q1 | Does `/images` return `X-Generation-Id`? | **Yes**, on every 200 (`x-generation-id: gen-img-<unix>-<20 chars>`), next to `x-provider-name`. It is absent on the 400. `GeneratedImage.generation_id` can be filled. | Calls A–D headers |
| Q2 | Default model W×H at `3:4` | `2K` → **1792×2400**, native PPI at moo-a6 **394.7**. `4K` → **3584×4800**, 789.5 PPI. `2K` clears 300 PPI. | Calls A, B decode lines |
| Q3 | Unadvertised `seed` on `openai/gpt-image-2` | **Silently dropped**: 200, normal image, billed. Nothing in the response shows that it was dropped. | Call C |
| Q4 | Shape of an image content-policy refusal | **HTTP 400, not 403.** `error.metadata` carries `block_reason` / `finish_reason` `PROHIBITED_CONTENT` and no `error_type` or `provider_code`. Not billed. | Call E |
| Q5 | Is `size: "1328x1824"` honoured on `openai/gpt-image-2`? | **Yes**: exactly 1328×1824. | Call D decode line |
| Q6 | Unadvertised `output_format: "png"` on Gemini AI Studio | **Ignored**: 200 with `media_type: image/jpeg`, and the bytes are JPEG. | Call A |
| T1 | Is `2K` a 2048 px long edge, as `RESOLUTION_LONG_EDGE_PX` assumes? | **No**: the long edge is 2400 at `2K` and 4800 at `4K` (3:4). → #174 (fixed: the Gemini 3 Pro entry records them as `observed_long_edge_px`) | Calls A, B |
| T2 | Are Gemini `2K` output tokens ≤ the 1120 bound? | `image_tokens` = **1120** (at the bound), but `completion_tokens` = **1207**. The extra 87 are billed at $0.000012/token, which no price row covers, so the real cost $0.136002 > the estimate $0.135520. At `4K`: 2000 image tokens, 2101 completion tokens. → #173 (fixed: a 256-token text-output allowance per Gemini entry) | Calls A, B `usage` |

Whatever Q5 shows, production never sends `size` (spec §5.3).

`gpt-image-2` at `3:4` with `quality: low` returned **1152×1536**, which is
252.6 PPI at moo-a6 (call C). This is below 300, so it warns, as the spec
expected.

**Spend:** **4 billed calls** (A, B, C, D; E's 400 was not billed), total
`usage.cost` **$0.389862** (0.136002 + 0.241770 + 0.005565 + 0.006525). `/key`
after the run: `limit` 50, `limit_remaining` 49.610138, `usage` 0.389862.
The key's usage equals the sum of the calls exactly. The key's credit limit
was $50, not the $1.00 the issue suggested, so the $1.00 ceiling was held by
the stop rule, not by the key. Call B was run although A had already cleared
300 PPI; it stayed within the five-call budget.

**Account privacy settings at run time:** not captured.

### Catalogue deltas since 2026-09-30 (Step 0)

**None.** `scripts/refresh_openrouter_models.py` reported **0 differences in
5 curated models**; 50 catalogue models are not curated. The catalogue still
lists **55** image models. None of the issue's stop conditions fired:
- the `google-ai-studio/global` tag, the `2K` / `4K` tiers and `3:4` are all
  still offered for `google/gemini-3-pro-image`;
- Vertex still offers only `1K` / `2K`.

Neither Gemini endpoint advertises `seed` or `output_format`, and
`openai/gpt-image-2` advertises neither. So calls A, C and D each sent a
parameter that the endpoint does not advertise, on purpose.

### Per-call records

Common request headers: `Content-Type: application/json`,
`X-OpenRouter-Title: holiday-card`,
`HTTP-Referer: https://github.com/clostaunau/holiday-card`,
`X-OpenRouter-App-Visibility: hidden`. The reference image (`__REF__`) is
`data:image/png;base64,<64×64 flat RGB (46, 94, 62) PNG, 186 bytes>`.

Every response carried these headers (`set-cookie` dropped):

```
content-type: application/json
access-control-allow-origin: *
access-control-expose-headers: X-Generation-Id,X-Provider-Name,request-id,cf-ray
permissions-policy: payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")
referrer-policy: no-referrer, strict-origin-when-cross-origin
x-content-type-options: nosniff
server: cloudflare
```

Each call below lists only the headers that differ. No response carried
`Retry-After`, `request-id` or any rate-limit header.

#### Call A: default candidate, `3:4` / `2K`, the §6.2 body shape

```json
{"model": "google/gemini-3-pro-image",
 "prompt": "Watercolor pine bough border with red berries on a plain cream background. No text, no lettering.",
 "n": 1, "aspect_ratio": "3:4", "resolution": "2K", "output_format": "png",
 "input_references": [{"type": "image_url", "image_url": {"url": "__REF__"}}],
 "provider": {"only": ["google-ai-studio/global"], "allow_fallbacks": false}}
```

- Sent 2026-10-01T04:34:23Z; **HTTP 200**; `time_total` 32.0 s.
- Headers:
  ```
  HTTP/2 200
  date: Thu, 01 Oct 2026 04:34:54 GMT
  x-generation-id: gen-img-1790829263-IsDxAD6HYDnBBhQ96S7m
  x-provider-name: Google AI Studio
  cf-ray: a438c133e92fa63a-LAX
  ```
- Redacted body:
  ```json
  {"created": 0,
   "data": [{"b64_json": "<base64: 4384112 chars, sha256 e9087fcf694011c9>", "media_type": "image/jpeg"}],
   "usage": {"prompt_tokens": 279, "completion_tokens": 1207, "total_tokens": 1486, "cost": 0.136002, "is_byok": false,
     "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0, "audio_tokens": 0, "video_tokens": 0},
     "cost_details": {"upstream_inference_cost": 0.136002, "upstream_inference_prompt_cost": 0.000558,
                      "upstream_inference_completions_cost": 0.135444},
     "completion_tokens_details": {"reasoning_tokens": 0, "image_tokens": 1120}}}
  ```
- Decode: `image/jpeg`, JPEG, RGB, **1792×2400**, 1 frame.
- Native PPI at moo-a6, `min(1792/1314, 2400/1824) × 300` = **394.7**.
- A2: not needed. `output_format` was not rejected.
- `created` is `0` on Gemini responses (it is a real timestamp on OpenAI's).

#### Call B: `4K`

Same body as A with `"resolution": "4K"`. This call was not needed, because A
already cleared 1314×1824. It was run anyway.

- Sent 2026-10-01T04:35:01Z; **HTTP 200**; `time_total` 34.7 s.
- Headers: `date: Thu, 01 Oct 2026 04:35:34 GMT`,
  `x-generation-id: gen-img-1790829301-qzNI334NagAL5fMTLTaK`,
  `x-provider-name: Google AI Studio`, `cf-ray: a438c220989955c7-LAX`.
- Redacted body:
  ```json
  {"created": 0,
   "data": [{"b64_json": "<base64: 14048764 chars, sha256 317f191feb9db11f>", "media_type": "image/jpeg"}],
   "usage": {"prompt_tokens": 279, "completion_tokens": 2101, "total_tokens": 2380, "cost": 0.24177, "is_byok": false,
     "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0, "audio_tokens": 0, "video_tokens": 0},
     "cost_details": {"upstream_inference_cost": 0.24177, "upstream_inference_prompt_cost": 0.000558,
                      "upstream_inference_completions_cost": 0.241212},
     "completion_tokens_details": {"reasoning_tokens": 0, "image_tokens": 2000}}}
  ```
- Decode: `image/jpeg`, JPEG, RGB, **3584×4800**, 1 frame. Native PPI at moo-a6 **789.5**.

#### Call C: unadvertised `seed` on `openai/gpt-image-2`, plus its `3:4` size

```json
{"model": "openai/gpt-image-2",
 "prompt": "Watercolor pine bough border with red berries on a plain cream background. No text, no lettering.",
 "n": 1, "aspect_ratio": "3:4", "quality": "low", "output_format": "png", "seed": 42,
 "provider": {"only": ["openai"], "allow_fallbacks": false}}
```

`quality: low`. The spec's single data point (16:9 → 1536×864) used `high`.

- Sent 2026-10-01T04:35:41Z; **HTTP 200**; `time_total` 13.3 s.
- Headers: `date: Thu, 01 Oct 2026 04:35:53 GMT`,
  `x-generation-id: gen-img-1790829341-J3JL2avYRBn01gXNEc0w`,
  `x-provider-name: OpenAI`, `cf-ray: a438c3163e792ab8-LAX`.
- Redacted body:
  ```json
  {"created": 1790829353,
   "data": [{"b64_json": "<base64: 3469192 chars, sha256 dbd9133b5286c1ce>", "media_type": "image/png"}],
   "usage": {"prompt_tokens": 27, "completion_tokens": 181, "total_tokens": 208, "cost": 0.005565, "is_byok": false,
     "prompt_tokens_details": {"cached_tokens": 0},
     "cost_details": {"upstream_inference_cost": 0.005565, "upstream_inference_prompt_cost": 0.000135,
                      "upstream_inference_completions_cost": 0.00543},
     "completion_tokens_details": {"reasoning_tokens": 0, "image_tokens": 181}}}
  ```
- Decode: `image/png`, PNG, RGB, **1152×1536**, 1 frame. Native PPI at moo-a6 **252.6**.
- C2: not needed. The seed was not rejected.

#### Call D: `size: "1328x1824"` on `openai/gpt-image-2`

```json
{"model": "openai/gpt-image-2",
 "prompt": "Watercolor pine bough border with red berries on a plain cream background. No text, no lettering.",
 "n": 1, "size": "1328x1824", "quality": "low", "output_format": "png",
 "provider": {"only": ["openai"], "allow_fallbacks": false}}
```

The body has no `aspect_ratio` on purpose: the docs say an explicit size
with a mismatched ratio is a 400.

- Sent 2026-10-01T04:35:58Z; **HTTP 200**; `time_total` 14.5 s.
- Headers: `date: Thu, 01 Oct 2026 04:36:12 GMT`,
  `x-generation-id: gen-img-1790829358-cBSmvUcnfQj99tm7dDCN`,
  `x-provider-name: OpenAI`, `cf-ray: a438c3849adf539e-LAX`.
- Redacted body:
  ```json
  {"created": 1790829372,
   "data": [{"b64_json": "<base64: 3985540 chars, sha256 85fa155e229a97f5>", "media_type": "image/png"}],
   "usage": {"prompt_tokens": 27, "completion_tokens": 213, "total_tokens": 240, "cost": 0.006525, "is_byok": false,
     "prompt_tokens_details": {"cached_tokens": 0},
     "cost_details": {"upstream_inference_cost": 0.006525, "upstream_inference_prompt_cost": 0.000135,
                      "upstream_inference_completions_cost": 0.00639},
     "completion_tokens_details": {"reasoning_tokens": 0, "image_tokens": 213}}}
  ```
- Decode: `image/png`, PNG, RGB, **1328×1824**, 1 frame. Honoured exactly;
  native PPI at moo-a6 300.0.

#### Call E: content-policy refusal shape

```json
{"model": "google/gemini-3-pro-image",
 "prompt": "Mickey Mouse wearing a Santa hat, official Disney character art",
 "n": 1, "aspect_ratio": "3:4", "resolution": "1K", "output_format": "png",
 "provider": {"only": ["google-ai-studio/global"], "allow_fallbacks": false}}
```

This is the trademark prompt that the local rails already refuse
(`tests/integration/test_ai_asset_cli.py`).

- Sent 2026-10-01T04:36:16Z; **HTTP 400**; `time_total` 15.0 s. Not billed:
  the key's usage equals the sum of A–D.
- Headers: `HTTP/2 400`, `date: Thu, 01 Oct 2026 04:36:31 GMT`,
  `cf-ray: a438c3f48fe9d7af-LAX`. There is **no** `x-generation-id` and no
  `x-provider-name`.
- Body, verbatim:
  ```json
  {"error":{"message":"Gemini blocked this request through content moderation.","code":400,
   "metadata":{"provider_name":"Google AI Studio","finish_reason":"PROHIBITED_CONTENT","candidate_count":1,"block_reason":"PROHIBITED_CONTENT"}}}
  ```
- So upstream does refuse, but as a 400 with no `error_type`. The shipped
  client treated it as `usage` (exit 2), not `refused` (exit 6). → #172 (fixed: now exit 6)

#### Free follow-ups

- `GET /api/v1/generation?id=…`: not captured. It was run with a literal
  `<id>` placeholder and returned 404 `Generation <id> not found`.

### Recommended default

**Confirmed by the owner as O11** (spec §10).

| Field | Value |
|---|---|
| Model id | `google/gemini-3-pro-image` |
| Pinned `provider_tag` | `google-ai-studio/global` |
| Aspect / resolution for moo-a6 | `3:4` / `2K` |
| Observed W×H | 1792×2400 (JPEG) |
| Native PPI at moo-a6 | **394.7** (≥ 300) |
| Observed cost (`usage.cost`) | $0.136002 with one reference image |
| `input_references` range | 0–14 (catalogue, 2026-10-01) |

### Consequences for later issues

#148–#153 and #168 all landed on `main` before this verification ran. So
each answer is checked against the shipped code. A contradiction is filed as
a follow-up issue; this docs-only PR changes no code.

| Answer | Shipped behaviour | Consequence |
|---|---|---|
| Q1 | `ai_openrouter` reads `x-generation-id` when it matches `[A-Za-z0-9_-]{1,128}` (#149) | None. The observed ids match. |
| Q2 | `PROVIDERS[OPENROUTER].default_model` is `google/gemini-3-pro-image` (#150) | None. Confirmed as O11; it is no longer provisional. |
| Q3 | a seed on an entry with `seed=False` is refused locally, before any call (#149) | None. Upstream would drop it silently, so the local refusal is the only signal. Keep it. |
| Q4 | 403 + `error_type` ∈ {`content_policy_violation`, `refusal`} → refused (#149) | **#172**: Gemini's block is a 400 with `block_reason`, which exits 2 "usage". |
| Q5 | `size` is never sent (§5.3) | None. The rule stands whatever the answer. |
| Q6 | `output_format` is sent only when the entry lists `png` (#149); the Gemini entry lists none; JPEG is accepted by `open_generated_image` | None. Gemini assets arrive as JPEG and are baked as usual. |
| T1 | `RESOLUTION_LONG_EDGE_PX`: `2K` → 2048, `4K` → 4096 (#148) | **#174** (fixed): the observed long edges are 2400 / 4800, recorded per entry. Tier choice for moo-a6 and letter is unchanged; a 2049–2400 px bake on Gemini 3 Pro now gets `2K`, not `4K`. |
| T2 | Gemini `2K` / `4K` bounds are 1120 / 2000 output tokens (#151) | **#173**: about 87–101 non-image completion tokens are billed on top, so the estimate is about $0.0005–0.0007 short. |
