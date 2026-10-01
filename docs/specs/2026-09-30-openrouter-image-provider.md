# OpenRouter as a second AI image provider — spec of record

**Date:** 2026-09-30 · **Baseline commit:** `047ee2c` (v1.3.0) · **Status:** ACCEPTED 2026-09-30 (decisions O1–O10 in §10)
**Tracker issue:** see the GitHub issue titled `tracker: OpenRouter image provider`.

> **Staleness protocol.** The repo moves. Every `file:line` below was observed on
> `047ee2c`. Re-verify each anchor against current `main` before relying on it; if a
> reference has moved, say so in your PR rather than quietly using a stale one.
> Every OpenRouter API fact was read on **2026-09-30** from the URLs in §11. They are a
> third-party API that changes monthly: re-read the cited page before coding against it.

## 1. What this is

The owner asked (2026-09-30) whether AI model support can make cards "more unique,
detailed, rich or custom", and asked to scope **OpenRouter** (https://openrouter.ai,
one API key reaching ~55 image models from OpenAI, Google, Black Forest Labs,
ByteDance, Qwen, Recraft, xAI and others) as a provider.

Four expert agents investigated in parallel, each through one lens:

| Lens | What they did |
|---|---|
| **(API)** OpenRouter API research | Read the OpenRouter docs and fetched the live, unauthenticated image catalogue. Probed the routes without a key. No authenticated call was made. |
| **(ARCH)** Codebase integration | Mapped the shipped L3 feature (`core/ai_*.py`, the `ai-asset` CLI and its tests) with anchors. |
| **(POL)** Product and responsible AI | Read `docs/industry-review/consensus-ai-feature.md` (CAI), the critiques and the standing decisions. |
| **(SEC)** Security, testing and CI | Covered the transport choice, secrets, untrusted responses, cost, the network-free test strategy and CI. |

Their working notes are not committed. This document is the merged, decision-ready
result.

**Bottom line.**
- **What fits:** OpenRouter fits as a second transport behind the existing
  `ImageClient` seam without re-opening any panel decision.
- **What doesn't change:** choosing a model alone will not make cards visibly richer.
  Richer cards come from giving baked art a better place in the card (a panel
  background layer under vector text, §8 Phase 4) and from a strong style anchor (the
  L2 illustrator commission, still outstanding).
- **The plan:** ship the transport narrowly, close the existing L3 enforcement gaps
  first, and treat "richer placement" as a separate, owner-approved phase that benefits
  every provider.

## 2. Standing decisions (do not re-open)

Inherited. None of these are re-litigated by this program.

| # | Decision | Source |
|---|---|---|
| S1 | AI imagery is **authoring-time only**. `create`, `preview`, the compiler, and the microsite never call a model API. | CAI:16-19, :160; README.md:304-306 |
| S2 | **Style-anchored by default.** `--reference` is required; text-to-image only with `--unsafe-no-style-anchor`. | CAI:21-24, :161, :206 |
| S3 | **AI never renders text.** All card text stays vector. | CAI:23-24, :207 |
| S4 | **No AI-generated copy** ("out of scope for v0, v1, and v2"). OpenRouter's LLMs are *not* used for words. | CAI:67-70, :208 |
| S5 | **Hard category rails** (sympathy-class occasions, religious iconography, likeness, trademarks, photo replacement) live in `core/ai_rails.py` `evaluate_rails` and run **before** any client is built. They are provider-independent. | CAI:77-91; `core/ai_assets.py:361-363` |
| S6 | **Provenance sidecar + first-use consent + verbatim personal-use paragraph.** | CAI:31-34, :129, :165, :168 |
| S7 | **D4 fail loud.** Unknown model, unsupported parameter, or unroutable request → error, never a silent drop. | `docs/specs/2026-09-26-expert-panel-remediation.md` §2 |
| S8 | **D17 delete, don't shim** (owner preference). | same |
| S9 | The injectable **`ImageClient` Protocol** is the seam; tests never touch the network. | `core/ai_assets.py:253-274`; remediation spec "What NOT to change" |

The panel **never addressed vendor choice**. It reviewed "the proposed OpenAI image
generation feature" only (CAI:133 names "dependency on a paid third-party API" as a
risk). Adding a second provider is therefore an **owner decision (§9 Q1), not a panel
re-open**.

## 3. What OpenRouter offers for images (verified 2026-09-30)

- **A dedicated Image API, `POST https://openrouter.ai/api/v1/images`** [IMG][IMG-API].
  It is not chat-based and not OpenAI-SDK-compatible:
  - the path is `/images`;
  - the OpenAI SDK's `/images/generations` exists but is undocumented;
  - `/images/edits` returns **404** (probe, 2026-09-30).
  - Reference images go **in the same request** as `input_references` (≤ 16 items of
    `{"type":"image_url","image_url":{"url": "<https or data: URL>"}}`).
- **Request fields:** `model`, `prompt`, `n` (upper bound), `aspect_ratio` (fixed
  enum), `resolution` (`512|768|1K|2K|4K`), `size` (tier or `WxH`; normalized
  opaquely), `quality`, `output_format` (`png|jpeg|webp|svg`), `background`
  (`transparent` needs png/webp), `seed`, `stream`, and
  `provider: {only, order, ignore, sort, allow_fallbacks, options}`.
- **Response:**
  `{created, data: [{b64_json, media_type}], usage: {prompt_tokens, completion_tokens, total_tokens, cost, is_byok, …}}`.
  - It has **no `id`, `model` or `provider` field.**
  - Whether an `X-Generation-Id` header is returned for `/images` is **unverified**.
- **The size model is aspect ratio plus resolution tier, not pixels.**
  - "Providers clamp to their supported subset."
  - No live model advertises `size`.
  - Returned pixel dimensions are **not published**. The one documented example,
    `openai/gpt-image-2` 16:9 high, returned **1536×864**, took 94 s and cost $0.13.
  - So the existing cover-crop plus LANCZOS bake (`core/ai_assets.py:318-332`) is
    mandatory, and the `native_ppi` warning (`:387`, `cli/commands.py:1102-1107`) will
    fire for many models at A6.
- **Capability catalogue, public and unauthenticated:**
  - `GET /api/v1/images/models` returns a typed `supported_parameters` per model
    (enum / range / boolean descriptors).
  - `GET /api/v1/images/models/{author}/{slug}/endpoints` returns per-provider records:
    `provider_tag` (the value to pin with `only`), a narrower `supported_parameters`,
    `allowed_passthrough_parameters` and `pricing[]` (units: image / megapixel / token).
  - **Endpoints of one model differ.** `google/gemini-3-pro-image` offers 4K on AI
    Studio but only 2K on Vertex.
  - 55 image models were listed on 2026-09-30.
- **Routing and data policy on `/images`:**
  - Only `only`, `order`, `ignore`, `sort`, `allow_fallbacks` (default **true**) and
    `options` are accepted.
  - **`data_collection`, `zdr`, `require_parameters` and `max_price` are chat-only.**
    For images they are account-level privacy settings.
  - `provider.options` **drops unknown keys silently.**
  - Model fallbacks (`models: [...]`) are not in the `/images` schema.
- **Seed:** only FLUX.2, Seedream, Qwen-Image-3 and Krea 2 advertise it, and even then
  "determinism is not guaranteed". **No OpenAI or Google image model accepts a seed.**
- **Errors:**
  - Envelope: `{"error": {"code", "message", "metadata": {"error_type", "provider_code", …}}}`.
  - 401 → auth; 402 → payment (`metadata.limit_source`; only
    `openrouter_in_flight_budget` is transient).
  - **403 with `error_type ∈ {content_policy_violation, refusal}`** → the provider refused.
  - 429 / 503 / 529 (with `Retry-After`); 502 → the generation failed and was **not
    billed** (billing is all-or-nothing); 524 → edge timeout.
  - An image-specific refusal body was not found in the docs.
- **Terms ([TOS], updated 2026-08-31):**
  - Ownership of the output is set by each **model provider's own terms** (§6.1).
  - The user must follow those terms (§5.1).
  - OpenRouter grants no output licence of its own.
- **Auth and headers:**
  - Auth is `Authorization: Bearer $OPENROUTER_API_KEY`.
  - Optional attribution headers: `HTTP-Referer`, `X-OpenRouter-Title` (legacy
    `X-Title`), `X-OpenRouter-Categories` and `X-OpenRouter-App-Visibility: hidden`.

**Live verification still owed.** It needs a key and costs a few cents; see Phase 0,
issue "verify". Five points:
1. Does `/images` return `X-Generation-Id`?
2. What are the real W×H for the default model at `3:4` and its highest tier?
3. Is `seed` ignored or a 400 on a model that doesn't advertise it?
4. What does an image content-policy 403 body look like?
5. Is `size: "WxH"` honoured for `openai/gpt-image-2`?

## 4. Current state of the shipped L3 feature (`047ee2c`)

| Concern | Where | Note |
|---|---|---|
| Seam | `core/ai_assets.py:253-274` `ImageClient` | `model` property + `generate(*, prompt, reference_path, width_px, height_px, moderation, seed) -> GeneratedImage`. **Pixel-typed**, so it doesn't fit aspect-ratio models. |
| Sizing | `core/ai_assets.py:62` `DEFAULT_AI_MODEL = "gpt-image-2"`, `:65-79` `ModelSizePolicy`, `:100-107` `MODEL_SIZE_POLICIES` (bare OpenAI ids), `:141-195` `choose_request_size`, `:277-309` `build_ai_request` | |
| Bake | `core/ai_assets.py:318-332` `_cover_resample`, `:376` `Image.open(...)`, `:387` `native_ppi` | **Provider-agnostic already.** `:376` opens model bytes with **no `formats=` allow-list and no bomb guard** (SEC). |
| OpenAI adapter | `core/ai_openai.py` (only `openai` importer) | `:25` `_FALLBACK_COST_USD = 0.04`: a **fabricated cost** written to the sidecar. `:75-76` base64 decoded with no cap or `validate=True`. `:103` `OpenAI(api_key=…)` without `base_url` honours `OPENAI_BASE_URL` and uses the SDK's default `max_retries=2` (re-POSTs a billed call). |
| Provenance | `core/ai_provenance.py:42` `OPENAI_USAGE_POLICY_URL`, `:44-58` `CONSENT_NOTICE` (names OpenAI), `:61-88` `LicenseRecord` (`:85` `openai_policy_url`), `:143-151` `record_consent` | All OpenAI-shaped. `read_sidecar` (`:105`) **has no caller in `src/`**, though its docstring (`:9-11`) claims the render pipeline refuses sidecar-less AI assets. |
| CLI | `cli/commands.py:22` top-level `from …ai_openai import make_image_client`, `:895-1112` `ai-asset generate`, `:1109` hard-coded "OpenAI policy" line | There is no `--provider` or `--model`. Only consent (→3) and rail (→5) errors are caught (`:1069-1094`), so **API/network errors escape as tracebacks**. |
| Exit codes | `cli/exit_codes.py:10-16` | 0–5. The meaning of 4 is already provider-neutral. |
| Placement | `core/models.py:918` `Panel.background_image`, `core/compiler.py:268-271` raises `UnsupportedFeatureError` | Baked art can enter a card only as an `image_elements` rect or via `create -i` into a photo slot. The latter **bypasses rail 8 (no photo replacement)**. |
| Tests | `tests/unit/test_ai_{assets,openai,provenance,rails}.py`, `tests/integration/test_ai_asset_cli.py` | CI installs only `--extra dev` (`.github/workflows/ci.yml:32,67,87,144`), so **the real OpenAI adapter is never executed in CI**. "Only `ai_openai.py` imports `openai`" is **convention, not tested** (`tests/unit/test_core_purity.py:53-73` bans only ReportLab and the renderers). |
| Deps | `pyproject.toml:56-59` `ai = ["openai>=1.0,<4"]` → lock 3.19.2 | openai 3.x depends on **`httpx2`**. **There is no `httpx` in `uv.lock`.** |

## 5. Options evaluated

### 5.1 Transport (how we talk to OpenRouter)

| Option | New deps | mypy strict | Behaviour risk | Runs in CI | Verdict |
|---|---|---|---|---|---|
| **T1: stdlib `urllib.request` behind an injected `Transport` callable, `POST /images`** | none | clean (typeshed) | Needs configuring: urllib **follows 301/302/303 and forwards `Authorization` to the new host**, so install a no-redirect opener, cap reads, and set explicit timeouts. | **yes** (no extra needed) | **Recommended** |
| T2: `openai` SDK with `base_url=openrouter` | none | poor (`openai.*` is ignored → `Any`) | Wrong paths (`/images/generations` is undocumented, `/images/edits` 404). Default `max_retries=2` re-bills. Reads `OPENAI_*` env. A second `openai` importer. | no | Rejected |
| T3: `httpx` / `httpx2` directly | a new direct dep (`httpx` isn't locked; `httpx2` is only transitive through openai) | good | sane redirect handling | only with the extra | Rejected: adds a dependency for one POST |
| T4: official `openrouter` SDK (PyPI 1.3.11) | a new dep with a generated surface | unknown | vendor-generated API churn | only with the extra | Rejected |
| T5: chat completions with `modalities:["image","text"]` | none (with T1) | untyped `image_config` | undocumented in the image guide; parses data URLs out of `message.images` | yes | Rejected as primary. **It is the only path with per-request `data_collection: "deny"` / `zdr` / `max_price`**; see §9 Q3. |

### 5.2 Which models may be used

| Option | Verdict |
|---|---|
| **M1: curated, checked-in allowlist** (`OPENROUTER_IMAGE_MODELS`), generated from `/images/models` + `/endpoints` by a dev script, with a dated snapshot doc. Each entry holds the pinned `provider_tag`, aspect enum, resolution tiers, `input_references` range, seed support, output formats, pricing unit and upstream terms URL. An unknown id → `ValueError` (D4), the same as `MODEL_SIZE_POLICIES` today. | **Recommended.** Reproducible and offline-testable; each model's output terms can be reviewed. |
| M2: any model in the live catalogue, validated at run time against `/images/models` | Rejected: output terms go unreviewed, it needs a network call before the rails even run, and a stale catalogue means silent capability drift. |

### 5.3 How the request shape generalises

Replace pixel-only requests with a tagged request shape:

- `PixelSize(w, h)` for OpenAI direct, from the existing `choose_request_size`, unchanged.
- `AspectSize(aspect_ratio, resolution | None)` for OpenRouter:
  - **Aspect ratio:** pick the enum value with the minimum `|log(a/b) − log(tw/th)|`.
    Exclude `auto` and parse `9:19.5`. The tie rule is explicit and tested.
    Example: moo-a6 1314×1824 = 0.720 → `3:4` (Δ 0.040) beats `2:3` (0.077) and `4:5` (0.105).
  - **Resolution:** the smallest tier whose nominal long edge is ≥ the target long edge
    (1824 → `2K`), else the largest offered. `None` when the pinned endpoint has no
    `resolution`.
- **Never send `size: "WxH"` to OpenRouter.** It is normalised opaquely, and `aspect_ratio`
  is silently clamped. Both would hide what was actually requested. A requested value
  outside the pinned endpoint's enum is refused locally (D4).

## 6. Recommended architecture

```
ai-asset generate --provider openrouter --model google/gemini-3-pro-image ...
  │  rails (evaluate_rails)  ← unchanged, runs before any client (S5)
  │  consent(provider)       ← per-provider record
  ▼
core/ai_providers.py   AIProvider StrEnum, ProviderInfo registry, make_image_client(provider, model)
  │                    (stdlib-only; function-local imports of the adapters)
  ├─ core/ai_openai.py       OpenAIImageClient    (only `openai` importer)          PixelSize
  └─ core/ai_openrouter.py   OpenRouterImageClient (stdlib urllib, injected Transport) AspectSize
  ▼
core/ai_assets.py  generate_ai_asset → bake (hardened decode, cover-crop, LANCZOS, sRGB, 300 dpi)
  ▼
core/ai_provenance.py  LicenseRecord (provider-neutral) → <asset>.license.yaml
```

### 6.1 New and changed interfaces (verbatim targets)

```python
# core/ai_providers.py  (new, stdlib-only, importable without extras)
class AIProvider(StrEnum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"

@dataclass(frozen=True)
class ProviderInfo:
    name: AIProvider
    api_key_env: str                 # "OPENAI_API_KEY" | "OPENROUTER_API_KEY"
    default_model: str
    policy_urls: tuple[str, ...]     # recorded in consent + sidecar
    consent_blurb: str               # provider-specific paragraph of the consent notice

PROVIDERS: Mapping[AIProvider, ProviderInfo]
def make_image_client(provider: AIProvider, model: str | None = None) -> ImageClient: ...
class AIDependencyError(RuntimeError): ...        # moves here from ai_openai (D17: no re-export)

# core/ai_assets.py
@dataclass(frozen=True)
class PixelSize:  width_px: int; height_px: int
@dataclass(frozen=True)
class AspectSize: aspect_ratio: str; resolution: str | None
RequestShape = PixelSize | AspectSize

def choose_request_shape(provider: AIProvider, model: str, target_w: int, target_h: int) -> RequestShape

class ImageClient(Protocol):
    @property
    def provider(self) -> AIProvider: ...
    @property
    def model(self) -> str: ...
    def generate(self, *, prompt: str, reference_path: str | None,
                 shape: RequestShape, seed: int | None) -> GeneratedImage: ...

@dataclass(frozen=True)
class GeneratedImage:
    image_bytes: bytes               # was png_bytes; OpenRouter returns jpeg/webp too
    media_type: str                  # "image/png" | "image/jpeg" | "image/webp"
    cost_usd: float | None           # None when the provider reported none (no invented $0.04)
    cost_source: Literal["reported", "unknown"]
    model_version: str | None
    generation_id: str | None        # X-Generation-Id if present (unverified for /images)
    provider_route: str | None       # the pinned OpenRouter provider_tag

# core/ai_openrouter.py  (new)
class HttpResponse(NamedTuple): status: int; headers: Mapping[str, str]; body: bytes
class Transport(Protocol):
    def __call__(self, url: str, *, headers: Mapping[str, str], body: bytes,
                 timeout_s: float, max_bytes: int) -> HttpResponse: ...
def urllib_transport(...) -> HttpResponse      # no redirects, default TLS, capped read
class ProviderError(Exception):                # carries only redacted text
    kind: Literal["refused", "environment", "usage", "transient"]
    status: int | None
    retry_after_s: float | None
class OpenRouterImageClient:                   # implements ImageClient
    def __init__(self, *, api_key: SecretStr, model: str, transport: Transport = urllib_transport) -> None
```

- `moderation` leaves the Protocol. It is an OpenAI-only knob:
  - the OpenAI adapter always sends `"auto"` (CAI:34);
  - the OpenRouter adapter sends it via `provider.options.openai.moderation` only when the
    pinned endpoint lists it in `allowed_passthrough_parameters`.
- **`--seed` is refused (exit 2) on a model that doesn't advertise `seed`** (D4). Today
  it is silently ignored for OpenAI (`ai_openai.py:57`). That is fixed in the same phase.

### 6.2 The OpenRouter request

```json
POST https://openrouter.ai/api/v1/images
Authorization: Bearer <key>          Content-Type: application/json
X-OpenRouter-Title: holiday-card     HTTP-Referer: https://github.com/clostaunau/holiday-card
X-OpenRouter-App-Visibility: hidden
{ "model": "<allowlisted id>", "prompt": "<rails-checked prompt>", "n": 1,
  "aspect_ratio": "3:4", "resolution": "2K", "output_format": "png",
  "input_references": [{"type": "image_url",
                        "image_url": {"url": "data:image/png;base64,<probed reference>"}}],
  "provider": {"only": ["<pinned provider_tag>"], "allow_fallbacks": false} }
```

The `seed` field is present only when the model advertises it. `size`, `models` and
`stream` are never sent. The reference first goes through `core/images.probe_image`
(today `cli/commands.py:999` checks only `exists()`).

### 6.3 Handling the untrusted response (SEC)

1. **Limits:**
   - response ≤ 48 MiB (read `max_bytes + 1`);
   - `Content-Type: application/json`;
   - validate through frozen Pydantic models with `extra="ignore"`. That differs from the
     domain models' `forbid`: a third-party response must tolerate new fields.
2. **Exactly one `data[]` entry:**
   - 0 → refused;
   - more than 1 → refused (we asked for `n: 1`).
3. **Decode:**
   - `media_type` must be `image/png|jpeg|webp` (or absent, then sniffed);
   - refuse `svg+xml` and everything else;
   - `b64_json` length is capped before decoding (image ≤ 32 MiB);
   - decode with `base64.b64decode(s, validate=True)`;
   - magic bytes must match the declared type.
4. **Open safely:**
   - `Image.open(buf, formats=["PNG","JPEG","WEBP"])` with `DecompressionBombWarning`
     turned into an error;
   - refuse more than `core/images.MAX_IMAGE_PIXELS` (50 MP) or multi-frame images.
   - **This hardening also applies to the OpenAI path at `core/ai_assets.py:376`.** Today
     a payload Pillow identifies as EPS would invoke Ghostscript.
5. **Never fetch remote image URLs.** An http(s) URL in a response is refused.
6. **Timeouts:** connect 10 s, read 300 s. **No automatic retries**: the call is billed
   and not idempotent. On 429/503/529, print `Retry-After` and exit.

### 6.4 Secrets (SEC)

1. The key comes from `OPENROUTER_API_KEY` only. There is no flag and no config file.
   An empty or whitespace value → exit 4.
2. It is held as `pydantic.SecretStr` and unwrapped only inside the function that builds
   the `Authorization` header.
3. Every provider-sourced string passes through `_redact()` (the literal key plus the
   `sk-or-v1-…` / `sk-…` patterns) **before** it enters an exception, so the
   `--debug` re-raise (`cli/commands.py:136-145`) is safe.
4. Provider text is stripped of C0/C1 control characters and ANSI escapes, and truncated
   to 500 characters, before printing.
5. `typer.Typer(..., pretty_exceptions_show_locals=False)` is set explicitly on the root
   app (`cli/commands.py:84`) and on `ai_asset_app` (`:895`). The `typer>=0.12` floor
   admits versions whose default was `True`.
6. The base URL is a module constant (`https://openrouter.ai/api/v1`) with **no env
   override**.
7. The OpenAI client gets an explicit `base_url` and `max_retries=0`, closing the
   `OPENAI_BASE_URL` key-exfiltration path and the billed retries.

### 6.5 Exit codes (additive; existing numbers never change meaning)

| Condition | Exit |
|---|---|
| Key missing or empty; 401; 402 (credits / key limit) | 4 `ENVIRONMENT` |
| 400; unknown provider or model; unsupported `--seed` / aspect / resolution; `--max-cost` exceeded at preflight | 2 `USAGE` |
| 403 `content_policy_violation` / `refusal`; empty `data`; remote-URL image | **6 `PROVIDER_REFUSED`** (new; distinct from the local rails' 5) |
| 408 / 429 / 5xx / 524 / 529 / timeout / TLS / oversize / invalid payload | **7 `PROVIDER_ERROR`** (new; the retryable class) |

All of these arrive as one `ProviderError`. The CLI maps it and **never falls through to
a traceback**. The OpenAI adapter maps its SDK errors onto the same `ProviderError`.

### 6.6 Provenance and consent (POL + ARCH)

**`LicenseRecord`** is renamed to be provider-neutral:
- **Added:** `provider`, `requested_model`, `provider_route` (pinned tag),
  `request_shape` (`{"aspect_ratio": "3:4", "resolution": "2K"}` or
  `{"size": "1328x1824"}`), `generation_id | None`, `cost_source`, `media_type` and
  `policy_urls: list[str]`. The last includes OpenRouter's ToS **and** the upstream
  model vendor's terms URL from the allowlist entry.
- **`openai_policy_url` is deleted.** On read, a legacy key is folded into
  `policy_urls` for one release (§9 Q7).
- **The key never appears in the sidecar.**

**Consent** becomes per provider.
- `ai-consent.json` becomes `{"providers": {"openai": {…}, "openrouter": {…}}}`.
- A legacy flat file counts as **OpenAI consent only**.
- `consent_notice(provider)` for OpenRouter states that:
  - prompts and reference images go to OpenRouter **and** to the pinned upstream vendor;
  - output ownership is governed by that vendor's terms;
  - OpenRouter data-retention and training settings are **account-level** (the `/images`
    endpoint has no per-request `data_collection`), with a link to the privacy settings.
- `cli/commands.py:1109` prints the provider's policy URL(s).

### 6.7 Cost safety

- OpenRouter's `usage.cost` is recorded when it is reported (`cost_source="reported"`).
- **The OpenAI `_FALLBACK_COST_USD` guess is deleted.** A missing cost is `None`,
  printed as "unknown".
- Optional `--max-cost USD` (§9 Q1):
  - estimate the price from the allowlist entry's `pricing`, refreshed by the dev script,
    so there is no live preflight;
  - refuse **before** spending (exit 2);
  - print a loud warning if the reported cost exceeded it (the money is already spent);
  - `/images` has no `max_price`, so the pinned provider plus the allowlisted price is
    the only bound;
  - never auto-retry.

### 6.8 Selection and defaults

- `--provider openai|openrouter` (a `StrEnum`; unknown → click usage error, exit 2) and
  `--model <id>`.
- Default provider: `HOLIDAY_CARD_AI_PROVIDER`, else **`openai`**, so existing users see
  no behaviour change. A bad env value → exit 2, naming the variable.
- **The provider is never inferred from the model id.** `openai/gpt-image-2` on
  OpenRouter has different semantics (aspect enum, no pixel `size`) from `gpt-image-2`
  direct.
- Default OpenRouter model: **provisional** `google/gemini-3-pro-image` pinned to AI
  Studio (1K/2K/4K, 0–14 references). `2K` at `3:4` should clear 300 PPI on moo-a6.
  **Confirm with the Phase-0 live call before it becomes the default.**
  `openai/gpt-image-2` via OpenRouter has no resolution knob and will likely warn below
  300 PPI.
- A model whose `input_references` max is 0 is refused unless
  `--unsafe-no-style-anchor` is given (S2).

### 6.9 Tests (zero network)

- **Adapter tests (`tests/unit/test_ai_openrouter.py`):** a `FakeTransport` records
  `(url, headers, body)`. The body is compared with a committed golden
  `tests/fixtures/openrouter/request_moo_a6.json`.
- **Hand-written response fixtures** (`tests/fixtures/openrouter/*.json`, each under 2 KB):
  - `ok_png` / `ok_jpeg` / `ok_webp`, `two_images`, `empty_data`, `svg`,
    `mime_mismatch`, `bad_base64`, `remote_url`;
  - `bomb_png` (a real 20000×20000 IHDR, generated by a committed script);
  - `err_400/401/402/403_policy/403_refusal/429/502/524`.
- **Real `urllib_transport` against a loopback `http.server`:**
  - a 302 is **not** followed and the second server sees no `Authorization`;
  - `max_bytes` is enforced;
  - a stall times out;
  - `http://` is refused.
- **Secret sentinel:** with `OPENROUTER_API_KEY=sk-or-v1-<sentinel>`, run every error
  path with and without `--debug`. The sentinel must be absent from stdout, stderr,
  exceptions, formatted tracebacks, the sidecar and the consent file.
- **Hypothesis property:** the response parser either returns a `GeneratedImage` or
  raises `ProviderError`, never anything else.
- **Guards:**
  - an autouse `tests/conftest.py` fixture removes `OPENAI_API_KEY` / `OPENROUTER_API_KEY`
    and blocks non-loopback `socket.connect`;
  - a new `tests/unit/test_ai_import_confinement.py` checks that `openai` is imported only
    in `core/ai_openai.py` and `urllib.request` only in `core/ai_openrouter.py`;
  - `import holiday_card.cli.commands` must load neither.
- **Opt-in live smoke:** `tests/live/test_openrouter_live.py` with `@pytest.mark.live_ai`
  (register it in `pyproject.toml`; `--strict-markers` is on). It skips unless
  `HOLIDAY_CARD_LIVE_OPENROUTER=1` and a key are set.
  `tests/unit/test_workflow_policy.py` asserts that no workflow sets that variable or
  references an OpenRouter secret.
- **Coverage:** the 92% branch floor (`pyproject.toml` `fail_under`) must hold. Target
  ≥ 97% on the new module, and no `pragma: no cover` beyond an `ImportError` branch.
- **Unchanged:** no compile snapshot, visual baseline or PDF golden touches the AI path.

## 7. Rejected: why not

- **AI-generated copy through OpenRouter's LLMs.** Rejected by the panel for v0–v2
  (CAI:67-70, :208). If it is ever revisited, the only tolerated shape is *selection* from
  the curated sentiment library. That needs its own panel run.
- **Live, unfiltered model discovery (`--all`).** Unreviewed output terms, capability
  drift, and it advertises "AI card generator" positioning (CAI:212).
- **Model or provider fallbacks.** These break provenance: `/images` returns no model or
  provider in the body, so the pin is the only reliable record of what served the request.
- **Inferring the provider from a `/` in the model id.** A silent-inference anti-pattern
  (D4).
- **Run-time catalogue fetch.** A network call before the rails, non-reproducible, and
  untestable offline.
- **Treating OpenRouter as a way to use AI in photo slots or for sympathy-class cards.**
  Those are rails (S5).

## 8. Phased plan (every phase leaves `main` shippable)

| Phase | Content | Provider-visible change |
|---|---|---|
| **0: Verify and harden** (no new provider) | (a) Live verification of the five unknowns in §3. Owner-run, costs cents, writes `docs/industry-review/openrouter-image-api-snapshot.md`. (b) Harden the existing AI path: safe decode (§6.3 items 3–4), no invented cost, `ProviderError` + exit codes 6/7 for the OpenAI SDK errors, explicit `base_url` / `max_retries=0`, `show_locals=False`, redaction, and the confinement and conftest guards. (c) If §9 Q1 says so, close the L3 enforcement gaps: `read_sidecar` enforced when an AI asset is embedded, a PDF `/Subject` + XMP AI disclosure naming the real model, and AI assets refused in `-i` photo slots. | none (OpenAI only) |
| **1: Provider-neutral seam** (still OpenAI only) | `core/ai_providers.py`, `RequestShape`, the new `ImageClient` signature, `--provider` (only `openai` valid yet) / `--model`, per-provider consent, the provider-neutral `LicenseRecord` with legacy read, and refusing `--seed` where it is unsupported. | `--model` works for OpenAI. The sidecar gains fields. |
| **2: OpenRouter transport** | The allowlist + refresh script + snapshot, the aspect/resolution chooser, `core/ai_openrouter.py` (transport, parsing, errors) with fakes, then CLI wiring for `--provider openrouter`, the consent blurb, docs (README AI section, CLAUDE.md, exit-code table) and the opt-in live smoke. | **OpenRouter usable** |
| **3: Operator conveniences** (per §9 Q1) | `--max-cost`; `ai-asset models` (curated listing: id, upstream, references, aspect/tiers, seed, price unit, terms URL). | optional |
| **4: Richer placement** (per §9 Q1; benefits every provider) | Compiler support for `Panel.background_image`, restricted to a baked, sidecar-carrying, bleed-sized asset: drawn under vector content, bleed-extended, PPI-checked (#66), flattened and CMYK-converted on PDF/X (D10), and refused in photo slots. Later, optionally: transparent-background motif generation for allowlisted models that support `background: transparent`. | visibly richer cards |

**2026-09-30: Phase 2 shipped** (#150: `--provider openrouter` wired end to end, the
consent blurb, docs and the opt-in live smoke; the default model stays provisional until
#140). The privacy-settings link is `https://openrouter.ai/workspaces/default/settings`,
the page OpenRouter's data-collection guide links (verified 2026-09-30).

**2026-09-30: Phase 3 shipped** (#151 `--max-cost`; #152 `ai-asset models`, the curated,
offline listing with a versioned JSON document, `schema_version: 1`; no `--all`, no fetch).

**Critical path:** 0b → 1 → 2 (allowlist ∥ transport) → 2 (CLI wiring).
0a gates only the choice of *default* model. Phase 4 depends on 0c and nothing else.

## 9. Open questions for the owner (recommended defaults)

1. **Scope beyond the core provider.** Default: **include 0c (enforcement gaps) and 3
   (`--max-cost`, curated `ai-asset models`). Include 4 (background art) as its own
   phase.** 0c must land before more providers multiply undisclosed AI assets (CAI:119,
   127); 4 is where "richer" actually shows.
2. **Model set: curated allowlist or any live model?** Default: **curated allowlist
   (M1).**
3. **Data retention.** `/images` can't send `data_collection: "deny"` / `zdr` per
   request. Default: **use `/images`; the consent text states that retention is an
   account-level OpenRouter setting and links to it.** The alternative is the
   chat-completions path (T5), which can deny per request but is undocumented for images
   and untyped.
4. **Install gating.** The OpenRouter client is stdlib, so it needs no extra. Default:
   **no extra. `--provider openrouter` + `OPENROUTER_API_KEY` + per-provider consent is
   the gate.** The alternative is to require `pip install holiday-card[ai]` for symmetry.
5. **Default provider.** Default: **`openai`; OpenRouter only with explicit `--provider`
   / `HOLIDAY_CARD_AI_PROVIDER`.**
6. **Fallbacks.** Default: **never. Pin `provider.only = [tag]` and
   `allow_fallbacks: false`, single `model`.**
7. **Sidecar schema.** Default: **rename to provider-neutral fields (D17) and accept the
   legacy `openai_policy_url` on read for one release.**
8. **AI copy.** Default: **stays out (S4).**
9. **Reference-image screening for trademarks and likeness.** Default: **not in this
   program; state the gap in the consent notice.**
10. **Curated house-style reference library.** Default: **waits for the L2 illustrator
    commission.** Model breadth is not a substitute (CAI:23).

## 10. Decisions log

Each entry is dated and is never silently changed. Amend with a new dated line.

| # | Decision (2026-09-30) | How decided |
|---|---|---|
| O1 | **Scope:** Phases 0 (a, b, c), 1, 2, 3 (`--max-cost` + curated `ai-asset models`) and 4 (panel background AI art) are all in. | Owner answered Q1 |
| O2 | **Curated, checked-in allowlist** of OpenRouter models (M1). Unknown ids are refused. | Owner answered Q2 |
| O3 | **Use `POST /images`.** Data retention is an account-level OpenRouter setting, stated in the consent notice with a link. The chat-completions path (T5) is not used. | Owner answered Q3 |
| O4 | **No install extra for OpenRouter.** The gate is `--provider openrouter` + `OPENROUTER_API_KEY` + per-provider consent. | Owner answered Q4 |
| O5 | Default provider stays **`openai`**. OpenRouter is used only on explicit `--provider` / `HOLIDAY_CARD_AI_PROVIDER`. | Default adopted; owner may override |
| O6 | **No fallbacks.** `provider.only = [tag]`, `allow_fallbacks: false`, single `model`. | Default adopted; owner may override |
| O7 | Provider-neutral `LicenseRecord`; legacy `openai_policy_url` is **read for one release**. | Default adopted; owner may override |
| O8 | AI copy **stays out** (S4). | Default adopted (it is a standing decision) |
| O9 | Reference images are **not screened** for trademarks or likeness in this program; the gap is stated in the consent notice. | Default adopted; owner may override |
| O10 | The curated house-style reference library **waits for the L2 illustrator**. | Default adopted; owner may override |

### Amendment 2026-09-30: decisions made while splitting into issues

These refine §6 and §8. Each issue body is authoritative for its slice.

- **A1.** `ProviderError`, `redact` and the provider-text sanitizer live in a new stdlib-only
  `core/ai_errors.py`, not in `core/ai_openrouter.py` (§6.1). The OpenAI adapter needs them
  before the OpenRouter client exists. `ProviderError` is raised `from None`, so the SDK's
  unredacted text never lands in a chained traceback.
- **A2.** §6.2's request is refined: `output_format` (like `seed` and `resolution`) is sent
  **only when the pinned endpoint advertises it**. `google/gemini-3-pro-image` does not.
  That is a sixth unknown for the live check (Phase 0a).
- **A3.** §6.5's mappings are refined:
  - a 402 whose `limit_source` is `openrouter_in_flight_budget` → exit 7 (transient); every
    other 402 → 4;
  - a 403 whose `error_type` is neither `content_policy_violation` nor `refusal` → 4;
  - an OpenAI 403 (unverified org or region) → 4, since OpenAI moderation arrives as a 400
    `moderation_blocked` → 6.
- **A4.** `AIProvider.OPENROUTER` and its `ProviderInfo` are added in Phase 2 by the
  CLI-wiring issue, not earlier (D17: no dead enum members). Until then:
  - the allowlist issue ships a standalone `choose_aspect_shape(entry, w, h)`;
  - the client issue leaves out the `provider` property.

  `ProviderInfo` gains `policy_urls` and `consent_blurb` in the provenance issue, where
  they are first read.
- **A5.** Allowlist pricing is `pricing: tuple[OpenRouterPrice(billable, unit, cost_usd), ...]`,
  one row per endpoint price component, not a scalar. `--max-cost` adds upper-bound fields.
  `--max-cost` with `--provider openai` exits 2 until an OpenAI price bound is verified and
  recorded.
- **A6.** `DEFAULT_AI_MODEL` is deleted in Phase 1; `PROVIDERS[AIProvider.OPENAI].default_model`
  replaces it.
- **A7.** AI assets carry an uncompressed PNG `iTXt` marker `holiday-card:ai-generated`,
  written by the bake. A sidecar-less or mismatched marked asset raises
  `AIProvenanceError(ImageSourceError)` → exit 2. The list of embedded models travels in the
  IR as one `SetMetadata(key="ai_imagery", …)`; no new IR command is added.
- **A8.** `urllib_transport` becomes `make_urllib_transport(*, require_https=True)`, so the
  loopback tests can use http. A guard test ensures `src/` never passes `require_https=False`.

## 11. Sources (all accessed 2026-09-30)

[IMG] https://openrouter.ai/docs/guides/overview/multimodal/image-generation ·
[IMG-API] https://openrouter.ai/docs/api/api-reference/images/generate-an-image ·
[IMG-MODELS] https://openrouter.ai/docs/api/api-reference/images/list-image-generation-models ·
[IMG-EP] https://openrouter.ai/docs/api/api-reference/images/list-endpoints-for-an-image-model ·
[QS] https://openrouter.ai/docs/quickstart ·
[AUTH] https://openrouter.ai/docs/api_reference/authentication ·
[ATTR] https://openrouter.ai/docs/app-attribution ·
[ERR] https://openrouter.ai/docs/api_reference/errors-and-debugging ·
[LIMITS] https://openrouter.ai/docs/api_reference/limits ·
[USAGE] https://openrouter.ai/docs/cookbook/administration/usage-accounting ·
[ROUTE] https://openrouter.ai/docs/guides/routing/provider-selection ·
[ZDR] https://openrouter.ai/docs/guides/features/zdr ·
[DATA] https://openrouter.ai/docs/guides/privacy/data-collection ·
[META] https://openrouter.ai/docs/guides/features/router-metadata ·
[TOS] https://openrouter.ai/terms (updated 2026-08-31) ·
live `GET https://openrouter.ai/api/v1/images/models` and `/images/models/{id}/endpoints`.
