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
