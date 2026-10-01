# Engineering log

Per-PR engineering detail, newest first: what changed, why, what was
regenerated on purpose, and which tests guard it. Moved out of
`CLAUDE.md` on 2026-09-30 (it had grown past the context-file size
limit). New entries go at the top of this file; `CLAUDE.md` gets at
most a one-line pointer. User-facing notes belong in `RELEASE_NOTES.md`.

- **2026-09-30 — `ai-asset generate --max-cost USD` (issue #151, spec
  §6.7)**: new stdlib-only `core/ai_cost.py`. `estimate_max_cost` sums one
  upper bound per allowlist `pricing` row, offline: `image` rows cost
  `× 1` (output) or `× n_refs` (input); a `megapixel` output costs
  `× max_output_megapixels`, else the tier's `L × round(L × short/long)`
  px, and a megapixel input `×` the probed reference's exact MP; a `token`
  output costs `× output_image_tokens[tier or "default"]`, a token input
  image `× n_refs × input_image_tokens`, and `input_text` `× (UTF-8 bytes
  + 16)`, a bound, not a count. Any missing bound or unknown unit /
  billable raises `NoPriceOnRecordError` (D4); OpenAI reads
  `ModelSizePolicy.max_price_usd`, which stays `None` for every model (no
  verified per-request upper bound), so `--max-cost` with OpenAI exits 2.
  `TIER_LONG_EDGE_PX` *is* `RESOLUTION_LONG_EDGE_PX`. `OpenRouterModel`
  gains `max_output_megapixels`, `output_image_tokens`,
  `input_image_tokens` and a structured `bound_source` ("YYYY-MM-DD
  https://…"), required exactly when a bound is set and checked at import,
  as are token keys ⊆ the entry's tiers. Bounds (read 2026-09-30):
  gemini-3-pro-image 1K/2K 1120, 4K 2000 output tokens, 560 per input
  image; gemini-3.1-flash-image 512 747, 1K 1120, 2K 1680, 4K 2520
  (ai.google.dev/gemini-api/docs/pricing); flux.2-pro 2048×2048 =
  4.194304 MP (BFL: "up to 4MP (e.g., 2048x2048)", so **not** the issue's
  round 4.0). Worked moo-a6 numbers (3:4 at 2K, one 8×8 reference):
  seedream-4.5 $0.0400, flux.2-pro $0.1258, gemini-3-pro-image $0.1355,
  gemini-3.1-flash-image $0.1008; openai/gpt-image-2 has no token bound.
  `generate_ai_asset(max_cost_usd=…)` checks after consent and rails,
  before the call (re-probing the reference only when a cap is set), and
  records `cost_cap_usd` / `cost_estimate_usd` in the sidecar; the CLI
  validates the cap (finite, > 0) before consent and maps both refusals to
  exit 2, and after the call warns when the reported cost is above the cap
  or unknown. The refresh script treats the bounds like
  `upstream_terms_url` (`REVIEWED_FIELDS`: carried over, never drift;
  token bounds for a tier the endpoint dropped are trimmed). Guarded by
  `tests/unit/test_ai_cost.py` (worked examples, one test per formula row,
  a Hypothesis monotonicity property, a drift guard over every entry ×
  target × reference), `TestMaxCost` in `test_ai_assets.py` and both
  `ai-asset` CLI test files. Collected tests 3857 → 3930.
- **2026-09-30 — `ai-asset generate --provider openrouter` end to end
  (issue #150, OpenRouter program Phase 2)**: `AIProvider.OPENROUTER`
  and its `ProviderInfo` (key `OPENROUTER_API_KEY`, provisional default
  `google/gemini-3-pro-image` pending #140, policy URLs = OpenRouter ToS
  + the account privacy settings `https://openrouter.ai/workspaces/default/settings`,
  verified 2026-09-30 from the data-collection guide, which no longer
  links `/settings/privacy`). Every `match provider` gained its branch:
  `known_models` / `supports_seed` / `policy_urls_for` (+ the vendor's
  `upstream_terms_url`) read the allowlist through the module at call
  time; new `reference_limits` (the CLI's per-model S2 check, before
  consent) and `upstream_vendor` (vendor name from the new
  `ai_openrouter_models.upstream_vendor_name`, keyed by the
  `provider_tag` slug). `make_image_client` builds
  `OpenRouterImageClient` function-locally with
  `transport=ai_openrouter.urllib_transport` read at call time (so tests
  monkeypatch the module attribute); its missing-key error never
  mentions the `[ai]` extra (O4). `OpenRouterImageClient.provider` is
  added, and a `TYPE_CHECKING` assignment `_conforms: type[ImageClient] =
  OpenRouterImageClient` makes mypy (which runs on `src/` only) check it
  against `ImageClient`. A client-construction `ProviderError` (a key with
  inner whitespace) exits by its kind, not with a traceback. Vendor names
  are checked at import (D4). `consent_notice` takes
  `model=` and, for a routed model, adds a bullet naming the vendor,
  route and terms. `GenerationResult` gains `provider_route`
  for the CLI summary (`Provider: openrouter (route: …)`, `Model: …`).
  `ai_disclosure_label` is now `<model> via openrouter` for OpenRouter
  records. Help text: provider/keys/env var in the group help, the
  stale `--export-for` "(300 DPI, /16)" is "(trim+bleed at 300 PPI)",
  and an OpenRouter docstring example. `FakeTransport` moved to
  `tests/openrouter_fixtures.py`. Guarded by
  `tests/integration/test_ai_asset_cli_openrouter.py` (issue rows 1–18
  through the real factory and client), the new cases in
  `test_ai_providers.py`, `test_ai_provenance.py`,
  `test_ai_openrouter_models.py`, `test_ai_assets.py` and
  `test_ai_disclosure.py`, and the opt-in `tests/live/test_openrouter_live.py`
  (`live_ai`, skipped unless `HOLIDAY_CARD_LIVE_OPENROUTER=1` and a key).
  Under `--debug` a `ProviderError` still exits with its code (the #142
  contract); it sits redacted in the exit's exception context.
- **2026-09-30 — AI imagery disclosed in PDF / SVG / PNG metadata
  (issue #145, OpenRouter program)**: `render_ir` gains
  `AI_DISCLOSURE_PREFIX`, `ai_disclosure(labels)` and
  `ai_imagery_labels(commands)`, the one disclosure text every backend
  writes from #144's `SetMetadata(ai_imagery)`. PDF: the ReportLab
  backend's `/Subject` is the disclosure and wins over `theme_id` in either
  command order (a per-`render()` flag, reset each call because the
  per-panel generator reuses one renderer). New
  `renderers/pdf_metadata.py` holds `build_xmp`, **moved** from
  `pdfx_postprocess._build_xmp` (D17) with `_xml_escape` / `_iso_date` (now `xml_escape` / `iso_date`):
  `dc:description` whenever `/Subject` exists, `pdfx:` keys only for
  PDF/X, `hc:aiGenerated` / `hc:aiModels` /
  `Iptc4xmpExt:DigitalSourceType` only with AI imagery. The IPTC term is
  `compositeSynthetic` ("mix or composite of several elements, at least
  one of which is Generative AI", cv.iptc.org read 2026-09-30), not the
  issue's `compositeWithTrainedAlgorithmicMedia`, which IPTC defines as
  genAI inpainting/outpainting of one image. `CardGenerator._finish_pdf`
  routes a PDF/X file through `apply_pdfx1a(ai_imagery=)` and any other
  PDF with AI imagery through `write_disclosure_xmp`; a PDF without AI
  imagery never imports pikepdf and is byte-identical. Every moo-a6 XMP
  now carries `dc:description` (it was missing although `/Info /Subject`
  was set) and `pdfx_preflight._check_xmp` compares it with `/Subject`.
  SVG: `<desc id="ai-disclosure">` + an RDF `<metadata>` (namespaces
  registered at import, hoisted onto `<svg>` by ElementTree); pikepdf is
  kept out of the SVG import (a subprocess test). PNG: `Description` text
  chunk; the asset marker key never reaches a preview. CLI: `create` /
  `preview` print `AI imagery: <labels> (disclosed in file metadata)`.
  Tests: `tests/unit/test_pdf_metadata.py`,
  `tests/integration/test_ai_disclosure.py`; no snapshot, golden or
  visual baseline changed.

- **2026-09-30 — Provider-neutral provenance sidecar and per-provider
  consent (issue #147, OpenRouter program)**: `ProviderInfo` gains
  `policy_urls` and `consent_blurb` (the spec §6.1 final shape) and
  `ai_providers.policy_urls_for(provider, model)` is the one source of a
  bake's policy URLs (#150 makes OpenRouter's per-model). The OpenAI URL
  now lives only in `PROVIDERS`; `OPENAI_USAGE_POLICY_URL` and
  `CONSENT_NOTICE` are deleted (D17). `consent_notice(provider, path=)`
  is `_HEADER + blurb + _COMMON_BULLETS + _TRAILER`, and the OpenAI notice
  is byte-identical to v1.3.0 (a literal-text test pins it). The consent
  file is `{"providers": {"<id>": {acknowledged, timestamp,
  policy_urls}}}`, read once by `_read_consent` (fail closed; strict
  `acknowledged is True`; unknown provider keys kept on write; a v1.3.0
  flat file reads as OpenAI only). `record_consent(path, provider)` writes
  atomically (temp file + `os.replace`) and keeps an existing
  acknowledgement's timestamp, so migrating a v1.3.0 file keeps the date
  the user actually consented. `LicenseRecord` is `extra="forbid"`
  and requires `provider` / `requested_model` / `policy_urls`; it adds
  `provider_route`, `request_shape` (`ai_assets.request_shape_record`),
  `generation_id` and `media_type`. A `# LEGACY(v1.3.0 sidecar, O7)`
  before-validator reads `openai_policy_url` (and refuses it mixed with
  new keys); **delete it in the first release after the one that ships
  this**. `write_sidecar` dumps `mode="json"` (a `StrEnum` breaks
  `yaml.safe_dump`). `GeneratedImage.generation_id` / `provider_route`
  are now required keyword-only fields, and `GenerationResult` carries
  `policy_urls`, which the CLI prints as `Policy:` lines. Fixtures:
  `tests/fixtures/ai/v1.3.0-border.license.yaml`, `v1.3.0-ai-consent.json`.
  `ai_disclosure_label` is unchanged: the provider joins the label in
  #150, where `<model> via openrouter` first means something.


- **2026-09-30 — AI assets are marked, need an intact sidecar, and never
  fill a photo slot (issue #144, OpenRouter program)**: the sidecar was
  never checked (`read_sidecar` had no caller in `src/`), a baked PNG
  carried nothing that said "AI", and `create -i ai.png` put an AI asset
  in a photo slot past the prompt-side rail 8. The bake now passes
  `pnginfo=` an uncompressed `iTXt` chunk `holiday-card:ai-generated`
  (`AI_MARKER_KEY`) holding `marker_text(AIMarker(v=1, sidecar=<basename>,
  model=client.model, timestamp=…))`: compact sorted-key JSON, the sidecar
  by basename only (the validator refuses `/` and `\`), so no directory
  leaks. New in `core/ai_provenance.py`: `AIProvenanceError(ImageSourceError)`
  (so the CLI's `ValueError` branch makes it `Error: …`, exit 2, with no CLI
  change, and `validate` reports it as `<compile>`), `read_ai_marker(path)`
  (`None` for a non-PNG or an unmarked PNG; an unparsable or `v != 1`
  payload raises, D4; call it only after `probe_image`), `is_ai_asset`
  (marked, **or** a sibling sidecar: the legacy rule, since v1.3.0 assets
  and editor re-saves have no marker), `require_sidecar(path) ->
  LicenseRecord` (refuses: not an AI asset, renamed (marker's sidecar ≠
  `sidecar_path_for(path).name`), missing, unparsable / invalid YAML, marker
  `model` / `timestamp` ≠ the sidecar's; `raise … from e`),
  `photo_slot_refusal(path)` (the one rail-8 message, `model unknown: <why>`
  when the sidecar is unreadable) and `ai_disclosure_label(record)` (the
  model; #147 adds the provider; the only place a label is built). The
  binding is model + timestamp, not a file hash, so a colour tweak still
  renders (open question 2's default). `compiler.embedded_ai_assets(card)
  -> list[AIAssetUse(path, where, record)]` walks every image element in
  panel then element order, skips relative paths (`_compile_image` refuses
  them), probes, and for an AI asset raises with `where` =
  `<template>/<panel>/image_elements[i] (id 'x')` when it sits in a `slot`
  (rail 8, even a template placeholder) or its sidecar check fails.
  `compile_card` calls it **after** the panels (probe errors keep their
  order) and, when non-empty, inserts one `SetMetadata(key=
  AI_IMAGERY_METADATA_KEY ("ai_imagery", new in `render_ir`), value=
  "; ".join(sorted labels))` right after the card metadata; with no AI
  asset nothing is added, so all compile snapshots and visual baselines
  are unchanged. No new IR command or `ImageRef` field (disclosure is per
  document; paths stay out of the IR). The PNG backend already writes it as
  a `tEXt` chunk; PDF / SVG ignore it until #145. `fill_photo_slots` probes
  each photo through `_probe_photo`, which refuses any AI asset before any
  element changes (not `PhotoSlotError`: its "Templates with photo slots"
  advice is wrong here). Not done (default of open question 1): refusing AI
  assets in sympathy-class templates at render time. New shared helper
  `tests/ai_fixtures.py` (`bake_fake_ai_asset`: the real bake with an
  in-test client, no network or key; #145 / #153 reuse it). Guarded by
  `TestAIMarker` / `TestIsAIAsset` / `TestRequireSidecar` in
  `test_ai_provenance.py`, `TestBakeMarker` in `test_ai_assets.py`, the new
  `tests/unit/test_compiler_ai_assets.py` (placement, sorted / deduplicated
  labels, refusals (a tampered marker names its element), order, and no
  `ai_imagery` for all 21 templates),
  `TestAIAssetRefused` in `test_generators_photo_slots.py` and
  `tests/integration/test_ai_asset_embed.py` (`create` / `validate` with and
  without the sidecar, per-panel-pdf and moo-a6 export, `create` / `preview
  -i` with a marked and a legacy asset: exit 2, no file, no traceback).
  Tests 3804 → 3870 (collected).

- **2026-09-30 — OpenRouter `/images` client over a hardened stdlib
  transport (issue #149, OpenRouter program)**: new `core/ai_openrouter.py`
  (stdlib + Pillow + pydantic; the **only** `src/` importer of
  `urllib.request`; not wired to the CLI until #150). `OpenRouterImageClient(*,
  api_key: SecretStr, model, transport=urllib_transport)` looks the model up
  with #148's `openrouter_model` (unknown → `ValueError` listing the curated
  ids), refuses a blank key (`ProviderError(kind="environment")`) and stores
  only the `SecretStr` (no header dict on `self`; `repr` shows the model only).
  `generate(*, prompt, reference_path, shape, seed)` refuses locally, before
  any call, as `usage`: a `PixelSize`, an aspect / tier the pinned endpoint
  doesn't advertise, a seed on a seedless model, a reference on an
  `input_refs_max == 0` entry, none on an `input_refs_min >= 1` one, and a
  `--reference` that `probe_image` refuses. The body is compact UTF-8 JSON in
  spec §6.2 order (`model`, `prompt`, `n: 1`, `aspect_ratio`, `resolution` only
  with a tier, `output_format: "png"` only when advertised, `seed` only when
  given, `input_references` as a `data:image/{png|jpeg};base64,` URL from the
  probe, `provider: {only: [tag], allow_fallbacks: false}` plus `options.<slug>.
  moderation = "auto"` only when `moderation` is a passthrough); `size` /
  `models` / `stream` / `quality` / `background` / `user` / `session_id` are
  never sent. Headers are exactly `Authorization`, `Content-Type`, `Accept`,
  `User-Agent: holiday-card/<version>` and the three `ATTRIBUTION_HEADERS`;
  the key is unwrapped only in `_request_headers` and `_key_redactor` (an AST
  test holds it). One transport call, never retried (§6.3.6).
  `make_urllib_transport(*, require_https=True)` (production:
  `urllib_transport`; a test greps `src/` so nothing relaxes it): scheme
  check before any socket (`https` only; `file:` / `ftp:` / `data:` refused),
  `_NoRedirect` (a 3xx is returned, so no second host sees `Authorization`),
  `ssl.create_default_context()`, connect under `CONNECT_TIMEOUT_S = 10` then
  every read under `timeout_s` via `http.client` connection subclasses built
  with `functools.partial`, a `timeout_s` wall-clock deadline between reads
  (**`read1`, not `read`**: `HTTPResponse.read(n)` blocks until `n` bytes, so a
  trickling server never hit the deadline; found by the trickle test), an
  oversize `Content-Length` refused before reading, else 64 KiB chunks refused
  past `max_bytes` (`MAX_RESPONSE_BYTES = 48 MiB`); non-2xx statuses are
  returned; every socket / TLS / URL / protocol error is
  `ProviderError(kind="transient", status=None)`. `parse_images_response(
  response, *, entry, redact)` returns a `GeneratedImage` or raises
  `ProviderError`, nothing else (Hypothesis-checked): 3xx / 408 / 429 / 5xx /
  other → `transient` (with `Retry-After` delta-seconds or HTTP-date,
  clamped ≥ 0); 400 / 404 / 413 / 422 → `usage`; 401 → `environment`; 402 →
  `transient` for `limit_source == "openrouter_in_flight_budget"`, else
  `environment`; 403 → `refused` for `error_type` `content_policy_violation`
  / `refusal`, else `environment`; a 200 that is not `application/json`, not
  valid JSON or not an images response → `transient`; a 200 error envelope →
  its `code` through the same table; 0 or > 1 images, or a `url` /
  URL-shaped `b64_json` (never fetched) → `refused`; missing `b64_json`, a
  non-PNG/JPEG/WebP `media_type`, oversize base64 (`MAX_B64_CHARS`, before
  decoding), invalid base64, magic bytes that don't match (or, with no
  `media_type`, identify none of the three), or a failed header-only open →
  `transient`. Provider text (`message`, `error_type`, `provider_code`,
  `reasons`, `remedy_hint`) goes through `sanitize_provider_text` with the
  literal key (escapes stripped *before* redaction, so a split key is caught);
  a key containing whitespace or control characters (a CRLF `.env`) is refused
  as `environment` before `http.client` could echo it; a pydantic `ValidationError` (which echoes its
  input) is never chained. `cost_usd` is `usage.cost` when finite and ≥ 0
  (`"reported"`), else `None` (`"unknown"`; a string cost is a malformed
  response); `generation_id` is `x-generation-id` only when it matches
  `[A-Za-z0-9_-]{1,128}`; `provider_route` is the pinned tag. Response
  models are frozen with `extra="ignore"` (a third-party payload may gain
  fields). `ai_assets`: `GeneratedImage` gains `generation_id` /
  `provider_route` (default `None`), and new `probe_generated_image(bytes,
  media_type) -> (w, h)` shares `open_generated_image`'s checks through
  `_checked_image` without decoding a pixel. Fixtures:
  `tests/fixtures/openrouter/*.json` (`{"status", "headers", "body" |
  "body_text"}`, all ≤ 2 KiB, 8×8 images): `ok_{png,jpeg,webp}`,
  `two_images`, `empty_data`, `svg`, `mime_mismatch`, `bad_base64`,
  `remote_url`, `bomb_png` (IHDR 20000×20000), `not_json`, `err_{400,401,402,
  402_in_flight,403_policy,403_refusal,403_permission,429,502,524,
  200_envelope}`, plus `reference_8x8.png` and the golden
  `request_moo_a6.json` (gemini-3-pro-image, `3:4` / `2K`, no
  `output_format`); the image-bearing ones come from the new
  `scripts/make_openrouter_fixtures.py`, loaded by `tests/openrouter_fixtures.py`.
  Guarded by `tests/unit/test_ai_openrouter.py`,
  `tests/unit/test_ai_openrouter_transport.py` (`ThreadingHTTPServer` on
  127.0.0.1: headers / body seen, 403 returned, 301–308 never followed and
  server B sees no connection, `max_bytes` exact / Content-Length / chunked,
  stall, trickle, silent server, closed port, garbage, plain http and other
  schemes refused by the production transport, TLS verified, and HTTPS
  against a throwaway `openssl` cert), `tests/unit/test_openrouter_fixtures.py`,
  `TestOpenRouterResponseParser` in `test_parsers_properties.py`,
  `TestProbeGeneratedImage` in `test_ai_assets.py` and new rows in
  `test_ai_import_confinement.py` (`urllib.request` only in
  `core/ai_openrouter.py` among `src/`, plus the dev refresh script; no
  `openai` / `httpx` / `requests` there; importing the CLI loads neither
  `urllib.request` nor the client). Branch coverage of the module: 99%, no
  `pragma: no cover`. Tests 3487 → 3804 (collected).

- **2026-09-30 — Tests enforce AI import confinement, scrub API keys and
  block the network (issue #143, OpenRouter program)**: three safety
  properties of the AI feature were held by convention only. New
  `tests/ast_imports.py` holds the one AST import walker (moved out of
  `test_core_purity.py`, D17), now also seeing `importlib.import_module("x")`
  / `__import__("x")` with a constant name. New
  `tests/unit/test_ai_import_confinement.py`: `openai_violations(rel_path,
  source)` over every `src/holiday_card/**/*.py` and `scripts/*.py` allows
  `openai` only function-locally in `core/ai_openai.py` and reports `path:line
  imports openai`; a subprocess puts a recording finder at `sys.meta_path[0]`
  and asserts `import holiday_card.cli.commands` never looks up `openai`
  (holds whether or not the extra is installed). New autouse
  `_ai_test_isolation` in `tests/conftest.py`: unless a test is marked
  `live_ai`, it `delenv`s both keys (subprocesses inherit the scrubbed
  environment) and wraps `socket.socket.connect` / `connect_ex` so anything but
  `AF_UNIX`, `127.0.0.0/8`, `::1` or `"localhost"` raises
  `RuntimeError("network access is blocked in tests: …; mark the test live_ai
  to allow it")` (a `RuntimeError` so error handling under test cannot swallow
  it; in-process only, DNS and subprocesses are not guarded). The `live_ai`
  marker is registered (no test uses it until #150).
  `tests/unit/test_test_isolation.py` checks the guard: TEST-NET-3 connects
  raise at once, a loopback HTTP server works, and nested pytest runs with
  sentinel keys exported prove non-`live_ai` tests see no key while `live_ai`
  ones keep the keys and the original `connect`. `test_workflow_policy.py`
  gains `test_no_workflow_enables_live_ai_calls` (no `HOLIDAY_CARD_LIVE_`) and
  `test_no_workflow_references_an_ai_provider_secret` (no
  `secrets.*OPENROUTER|OPENAI*`), each proven on injected text. The redundant
  per-test `delenv("OPENAI_API_KEY")` calls in `test_ai_providers.py` are gone.
  No existing test needed the network. Tests 3398 → 3487 (collected).

- **2026-09-30 — Curated OpenRouter image allowlist, the aspect / tier
  chooser and a dev-only refresh script (issue #148, OpenRouter program)**:
  OpenRouter sizes images by an aspect-ratio enum plus a resolution tier,
  per endpoint. New stdlib-only `core/ai_openrouter_models.py`: frozen
  `OpenRouterPrice(billable, unit, cost_usd)` and `OpenRouterModel` (`id`,
  the **one** pinned `provider_tag`, `aspect_ratios` without `"auto"`,
  `resolutions` / `output_formats` (`()` = never send), `input_refs_min/max`,
  `seed`, `background_transparent`, `passthrough`, every `pricing` row,
  `upstream_terms_url`, `snapshot_date`), whose `__post_init__` refuses a
  bad entry at import naming the id and field (`"auto"`, an unknown tier,
  refs outside `0 ≤ min ≤ max ≤ 16`, empty or negative pricing, a non-ISO
  date, a non-https or `openrouter.ai` terms URL, so `"TODO-REVIEW"` fails,
  an empty tag). `OPENROUTER_IMAGE_MODELS` (read-only) holds 5 entries
  fetched 2026-09-30: gemini-3-pro-image @ `google-ai-studio/global` (4K),
  gemini-3.1-flash-image @ `google-ai-studio`, flux.2-pro and seedream-4.5
  (the two with `seed`), openai/gpt-image-2. `openrouter_model(id)` refuses
  an unknown id listing them. Also there: `RESOLUTION_LONG_EDGE_PX` (a
  tier's nominal long edge; an assumption until #140 measures it) and
  `aspect_ratio_value("9:19.5")`, both re-exported from `ai_assets` (they
  live in the stdlib module so the entries validate without Pillow).
  `ai_assets.choose_aspect_shape(entry, w, h) -> AspectSize`: nearest aspect
  in log space, ties to the narrower ratio then the smaller string (order
  independent), and the smallest tier covering the long edge, else the
  largest, else `None`. Every curated model picks 3:4 for letter (4K) and
  moo-a6 (2K). Not wired into `choose_request_shape` yet: no
  `AIProvider.OPENROUTER` before #150 (D17). The terms review replaced every
  `/providers` URL with the page that governs output ownership (Gemini API
  terms, BFL developer terms, BytePlus AI-services terms, the OpenAI
  services agreement); it is recorded in the new
  `docs/industry-review/openrouter-image-api-snapshot.md` (#140 fills in the
  rest). New `scripts/refresh_openrouter_models.py` (stdlib `urllib`, https
  only, no key): `--from-dir` / `--save-dir` recordings, `--add
  ID[@TAG]` (ambiguous → exit 2), `--emit table` (drift rows; 0 / 1 / 2)
  or `python` (paste-ready literals; unreviewed terms print `TODO-REVIEW`);
  it never compares the reviewed `upstream_terms_url`. Guarded by
  `tests/unit/test_ai_openrouter_models.py` (drift guard on the 5 ids, every
  refusal, pinned facts, a subprocess check that the import adds no
  non-stdlib module), `TestChooseAspectShape` in `test_ai_assets.py` (every
  entry × every geometry target, pinned rows, ties in both orders, tier
  fallback), `tests/unit/test_refresh_openrouter_models.py` (replays
  `tests/fixtures/openrouter/catalogue{,-drifted}/`: 0 differences, exactly
  3 drift rows, `TODO-REVIEW` refused on `eval`, no `Authorization`) and a
  `test_workflow_policy.py` row (no workflow runs the script).
  Tests 3060 → 3199.

- **2026-09-30 — AI provider registry, request shapes and a
  provider-neutral `ImageClient`; `--provider` / `--model`; `--seed`
  refused for OpenAI (issue #146, OpenRouter program)**: the AI seam was
  pixel-typed and OpenAI-shaped (`generate(width_px, height_px,
  moderation, …)`, the CLI imported the OpenAI factory). New stdlib-only
  `core/ai_providers.py`: `AIProvider` (`OPENAI` only; #150 adds
  `OPENROUTER`), frozen `ProviderInfo(name, api_key_env, default_model)`,
  the read-only `PROVIDERS` map (the **one** home of the `gpt-image-2`
  default), `AIDependencyError` (moved here, not re-exported from
  `ai_openai`), `UnknownModelError(ValueError)`, `known_models`,
  `resolve_model` (`None` → default; unknown → `unknown openai image model
  'dall-e-9'; known: …`), `supports_seed` (False for every OpenAI model)
  and `make_image_client(provider, model=None)`: model resolved first, then
  the key (unset / blank → `AIDependencyError` naming the variable), then a
  function-local adapter import. `match` + `assert_never` everywhere a
  provider is switched on, so a new member is a mypy error until wired
  (`assert_never\(` is in coverage `exclude_lines`). `ai_assets.py`:
  frozen `PixelSize` / `AspectSize(aspect_ratio, resolution)`,
  `RequestShape`, `choose_request_shape(provider, model, w, h)`;
  `AIRequest` has `shape` / `provider` / `model` (no `request_width_px` /
  `request_height_px` / `moderation`); `build_ai_request` requires
  `provider=` / `model=`; `ImageClient` is `provider`, `model`,
  `generate(*, prompt, reference_path, shape, seed)`; `generate_ai_asset`
  refuses a request sized for another provider / model before calling the
  client. `DEFAULT_AI_MODEL` is deleted (D17). `ai_openai.py`:
  `make_openai_client(*, api_key, model)` holds the lazy SDK import and
  #142's pinned settings; `OpenAIImageClient(client, model)` (model
  required) has `provider`, refuses an `AspectSize` or any `seed` before
  the SDK, and always sends `moderation="auto"`. CLI `ai-asset generate`:
  `--provider` (envvar `HOLIDAY_CARD_AI_PROVIDER`, empty = unset) and
  `--model`, no short flags; right after the occasion check (before the
  reference probe and consent), an unknown model or `--seed` on a seedless
  model exits 2. **Breaking:** `--seed` with OpenAI (RELEASE_NOTES).
  Guarded by `tests/unit/test_ai_providers.py` (registry, resolve, seed,
  factory order, missing extra via `sys.modules["openai"] = None`,
  subprocess: importing it loads neither `openai` nor `PIL`),
  `TestChooseRequestShape` / the mismatch refusal in `test_ai_assets.py`,
  the shape / seed / provider cases in `test_ai_openai.py`,
  `TestProviderAndModel` / `TestSeedRefused` in `test_ai_asset_cli.py`
  and two `TestShortFlags` rows. Tests 3007 → 3060.

- **2026-09-30 — `ai-asset` decodes model output as untrusted input,
  records only a reported cost, and content-checks `--reference` (issue
  #141)**: `generate_ai_asset` opened the model's bytes with a bare
  `Image.open` (any Pillow decoder, EPS → Ghostscript included; a 400 MP
  header only warned; animations flattened to frame 0), the OpenAI adapter
  `b64decode`d with no length cap or validation, every live call wrote an
  invented `_FALLBACK_COST_USD = 0.04` to the sidecar (openai 3.19.2's
  `ImagesResponse` has token `usage`, no USD cost field), and
  `--reference` was only `exists()`-checked before being uploaded
  (`--reference .env` would upload a secrets file). New in
  `core/ai_assets.py`: `ImageMediaType` (`image/png|jpeg|webp`),
  `MAX_IMAGE_BYTES = 32 MiB`, `ImagePayloadError(ValueError)`,
  `decode_b64_image(b64, *, max_bytes)` (length refused before decoding,
  then `validate=True`) and `open_generated_image(bytes, media_type)`
  (`formats=["PNG", "JPEG", "WEBP"]`, `DecompressionBombWarning` as an
  error, the Pillow format must match `media_type` (MPO = JPEG), `w × h ≤
  images.MAX_IMAGE_PIXELS` before `load()`, one frame, truncation
  refused; returns a loaded RGB copy; messages name the reason, never the
  bytes). The bake calls it before `mkdir`, so a refusal writes neither
  asset nor sidecar. `GeneratedImage` is `image_bytes` (was `png_bytes`,
  no alias), `media_type`, `cost_usd: float | None`, `cost_source:
  "reported" | "unknown"` (`__post_init__` refuses a mismatch);
  `GenerationResult` gains `cost_source`. The OpenAI adapter always
  returns `cost_usd=None, cost_source="unknown"` and takes `media_type`
  from `response.output_format` (default PNG). `LicenseRecord.cost_source`
  defaults to `"unknown"`, so a v1.3.0 sidecar still loads and reads as
  unknown. CLI: `Cost: $0.13 (reported)` or `Cost: unknown (the provider
  did not report one)`; `--reference` goes through `images.probe_image`
  (PNG / JPEG only, so WebP references are now refused) before consent or
  any client, `ImageSourceError` → `Error: --reference: …`, exit 2, and
  the resolved path is what gets uploaded; `ImagePayloadError` → `Error:
  the model's image was refused: …`, exit 7 (`PROVIDER_ERROR`, #142 was
  already on `main`), never a traceback, even under `--debug`. Guarded by
  `TestGeneratedImage` / `TestDecodeB64Image` / `TestOpenGeneratedImage`
  (EPS with Ghostscript patched to fail, GIF, type mismatch, APNG /
  animated WebP, a hand-built 20000² and 8000×7000 IHDR with
  `ImageFile.load` patched to fail, truncation) /
  `test_open_generated_image_returns_or_refuses` (Hypothesis, 200
  examples each: PNG / JPEG / WebP magic + random bytes, and byte-flipped / truncated real images) / `TestBakePayload`
  in `tests/unit/test_ai_assets.py`, the #141 block in `test_ai_openai.py`,
  the v1.3.0 sidecar case in `test_ai_provenance.py` and
  `TestUntrustedPayload` / `TestReferenceIsProbed` in
  `test_ai_asset_cli.py`. Tests 2968 → 3007.

- **2026-09-30 — `ai-asset` provider errors exit cleanly with redacted
  messages; exit codes 6 / 7 (issue #142)**: an OpenAI `AuthenticationError`,
  `RateLimitError`, timeout or moderation 400 escaped `ai-asset generate`
  as a raw traceback (exit 1) whose text could echo a masked key, the SDK
  honoured `OPENAI_BASE_URL`, retried the billed call twice and waited up
  to 600 s. New stdlib-only `core/ai_errors.py`: `ProviderError(message, *,
  kind, status, retry_after_s, secrets)` whose constructor keeps only
  `sanitize_provider_text(message)` (strip ANSI / OSC / C0 / C1 controls
  except `\n\t`, **then** `redact` every literal secret ≥ 8 chars and the
  `sk-or-v1-…` / `sk-…` patterns, **then** truncate to
  `MAX_PROVIDER_TEXT = 500` + `…`; stripping first so a key split by an
  escape is glued back before redaction), `parse_retry_after`
  (delta-seconds only). `OpenAIImageClient(..., *, api_key: SecretStr)`
  (the redaction secret) wraps the SDK call; `_map_openai_error` (a
  function-local `import openai`; `ImportError` or a non-SDK exception →
  `None`, re-raised unchanged) maps connection / timeout → `transient`,
  400 + `moderation_blocked` / `content_policy_violation` → `refused`,
  401 / 403 → `environment`, a 429 whose code is `insufficient_quota` or
  one of the guide's billing / spend-limit codes (`credit_balance_exhausted`,
  `organization_spend_limit_exceeded`, `project_spend_limit_exceeded`,
  `organization_usage_limit_exceeded`; `_QUOTA_CODES`) → `environment`,
  other 429, 408, 409, ≥ 500 and a bare `APIError` → `transient`, any
  other 4xx → `usage`, and raises `from None` **after** the handler, so the
  SDK error is neither `__cause__` nor `__context__`. An empty `data` or
  no `b64_json` → `refused` (was `IndexError`). `make_image_client` pins
  `base_url="https://api.openai.com/v1"`, `max_retries=0`,
  `timeout=OPENAI_TIMEOUT_S` (300). `ExitCode` gains `PROVIDER_REFUSED = 6`
  and `PROVIDER_ERROR = 7` (help epilog + README table). The CLI prints
  `Error: <what> (HTTP <status>): <text>` (+ `Retry after N s.`) and exits
  by kind even under `--debug`; anything else in the call goes through
  `_unexpected_error` (exit 1). Both Typer apps set
  `pretty_exceptions_show_locals=False`. #141 was not on `main`, so its
  `ImagePayloadError` → 7 mapping is left to #141. Tests use
  `tests/openai_sdk_stub.py` (the SDK exception hierarchy, installed as
  `sys.modules["openai"]`); `tests/unit/test_ai_openai_sdk_contract.py`
  checks it against the real SDK (skips without the `ai` extra; run
  `uv sync --extra dev --extra ai`). Guarded by `tests/unit/test_ai_errors.py`,
  the #142 block in `test_ai_openai.py`, `TestProviderErrors` /
  `TestSecretSentinel` in `test_ai_asset_cli.py` and `TestExitCodes`.
  Tests 2887 → 2968.

- **2026-09-30 — christmas-photo-ornament's inside-left caption is on its
  panel; no shipped text leaves its panel (issue #134)**: the
  centre-aligned `message` ("Treasured moments from our family to yours")
  was anchored at `x: 0.5"` with `width: 3.25`, so it hung 72 pt off the
  panel's left edge on every target (moo-a6 warned 1.5" past the safe
  zone, #73). The anchor is now the panel centre, `x: 2.125`; moo-a6 no
  longer warns for this template. New guard
  `tests/unit/test_template_text_in_panel.py`: every panel of all 21
  templates compiled natively (per-panel-pdf, trim-relative IR), and every
  `DrawText` run's measured box (advance × ascent/descent, through any
  group) stays inside its panel's trim; it failed only on this template.
  Regenerated on purpose: the photo-ornament `letter_content_sha256.json`
  entry and its PNG + PDF visual baselines (`visual-baselines` workflow,
  eyeballed; only the caption line moved). Tests 2866 → 2887.

- **2026-09-30 — Shape `rotation` is honoured for every shape type
  (issue #135)**: `BaseShape.rotation` loaded for every shape, but only
  `_compile_svg_path` read it, so five rotated rectangles printed
  unrotated: the 30° / 60° confetti on birthday-balloons and birthday-photo
  and the 15° pattern-filled gift box on christmas-holiday-masterpiece.
  `_compile_shape` now passes rectangle / circle / triangle / star / line
  commands through `_rotate_about_bbox_centre`, which wraps them (a
  `DrawShape`, or a pattern fill's whole clip + group sequence) in
  `BeginGroup(Transform(pivot = bbox centre, rotate_deg))` / `EndGroup`;
  a line pivots on its midpoint (`_shape_bbox_pts` pads a flat line to
  1 pt). SVG paths keep their own path-bbox pivot. `check_template`'s
  bounds check turns rectangle / triangle / line corners by `rotation`
  (circles and stars are rotation-invariant boxes). moo-a6 flattening and
  every `pdfx` test are unaffected. Regenerated on purpose: the
  birthday-balloons compile snapshot (two added groups, nothing else),
  three `letter_content_sha256.json` entries and the PNG + PDF visual
  baselines of the three templates (`visual-baselines` workflow,
  eyeballed; only the rotated shapes' areas moved). Guarded by
  `tests/unit/test_compiler_shape_rotation.py` (group per shape type,
  none at 0°, a rotated pattern rotates whole, the list of rotated shipped
  shapes, each compiles to its group, rotated bounds, PNG + PDF pixels).
  Tests 2848 → 2866.

- **2026-09-30 — Photo slots cover-fit: a clip larger than the photo's
  contain box is filled, not cut flat (issue #98)**: mothers-day-photo
  clips its 2.6×3.4" slot with a 2.0×3.1" ellipse; `preserve_aspect`
  contain-fit a square photo to 2.6×2.6", so the ellipse was flat at the
  top and bottom (on `main` too). New `ImageElement.fit: "contain" |
  "cover" | None` and the `resolved_fit` property (`"stretch"` when
  `preserve_aspect` is false; else `fit`; else `"cover"` for a `slot`
  element, `"contain"` otherwise). `fit` with `preserve_aspect: false` is
  a validation error. The compiler lowers cover (`_cover_rect`): the
  `DrawImage` rect grows to the image's aspect about the slot's centre and
  a `BeginClip` of the element rect wraps the clip mask, so the IR and all
  three backends are unchanged (like patterns, D13). When the aspects
  already match, the rect is the slot and no clip is added, so the other
  four photo templates (all square slots) compile byte-identically.
  `effective_ppi` sees the covering rect, so #66 measures the cropped
  photo's real PPI (the 1200 px placeholder is 353 PPI in the 3.4" slot).
  `docs/template-schema.json` regenerated; `docs/template-authoring.md`
  documents `fit`. Regenerated on purpose: the mothers-day-photo entry of
  `letter_content_sha256.json` and its PNG + PDF visual baselines
  (`visual-baselines` workflow, eyeballed: full ellipse). Guarded by
  `tests/unit/test_compiler_image_fit.py` (defaults, refusal, cover rect
  and clip order, matching aspect, PPI) and
  `tests/integration/test_image_cover_fit.py` (PNG + PDF pixels inside the
  ellipse but outside the old contain box are the photo). Tests 2833 →
  2848.

- **2026-09-30 — README, CLAUDE.md and help text reconciled with the
  code; README examples run in CI (expert-panel §P15 / D16 / D17, issue
  #88)**: New `tests/integration/test_readme_examples.py` pulls every
  `holiday-card …` line out of README.md's fenced `bash` blocks (joins
  `\` continuations, strips `#` comments shell-style via `shlex`,
  skips `ai-asset`, `pipx`, `pip` and `uv run` lines), runs each through
  `CliRunner` in a `tmp_path` cwd seeded with `letter.md`,
  `my-template.yaml` (christmas-classic), `cover.jpg` / `star.jpg` /
  `~/me.jpg` (the placeholder photo; `HOME` points at the tmp dir and `~`
  is expanded as the shell would), an isolated `XDG_DATA_HOME` holding a
  `my-card` user template, and `--no-open` on `preview`, and requires exit
  0 (15 examples; at least 6 or the test fails). Appending a
  `create --format png` example turns it red. New
  `tests/unit/test_docs_counts.py`: the template count in README ("21
  ship-quality templates") and CLAUDE.md (`# YAML card templates (21)`,
  "All 21 shipped templates") equals `len(discover_templates(<bundled>))`;
  README states no test count; the "Six things" heading matches its
  numbered items; the Output formats row says PNG is `preview`-only; the
  Markdown example mentions italic; no `motif.png`; `create --output` /
  `--inside-message-md` help, `init --help` (every `OccasionType`), root
  `--help` (PDF, SVG, PNG); no `"Helvetica"` in `commands.py`; every
  `specs/*/quickstart.md` starts with the historical banner. Fixed: README
  (Five → Six things, italic / bold-italic, PNG is `preview`-only, the hard
  test counts are gone, `--reference path/to/reference.png`); CLI help
  (`--output` names .pdf/.svg and per-panel directories,
  `--inside-message-md` lists italic and bold-italic and which families
  render them, `init --occasion` is generated from `OccasionType`, the
  root help and docstring name PDF / SVG / PNG, the `ai-asset` example
  reference); the `init` scaffold uses `PlayfairDisplay` (cover) and
  `Lato` (body); CLAUDE.md (Pillow 10.3+, 4 unlisted test files). Already
  fixed before this PR, verified: R1 `preview --voice` (#78), R2 `create
  ./my-template.yaml` (#79), R7 `ruff … scripts/`, R9 moo-a6 fill (#73),
  R10 exit codes / search path / `--debug`, H6 (`preview` docstring no
  longer claims WYSIWYG), C1–C5, and #83's dead-module rows. No CLI
  behaviour changed. Tests 2800 → 2833.

- **2026-09-29 — Domain models validate on assignment; the generator
  reassigns instead of mutating (expert-panel §P14 / D4 / D17, issue
  #81)**: every invariant was checked only at construction, so
  `t.font_size = 500` on a `TextElement` (`le=144`) went through, and
  nothing stopped a `TextElement` holding both `letter_content` and
  `rich_content` once built. Every mutable model in `core/models.py` now
  has `ConfigDict(extra="forbid", validate_assignment=True)`: all 18
  that already had `extra="forbid"`, plus `Theme` and `AdjustmentResult`,
  which had no config (neither is loaded from raw YAML, so `forbid` is
  safe). New `TextElement.with_inside_content(*, content="", rich=None,
  letter=None)` returns a `model_validate`d copy with exactly one inside
  surface set (not `model_copy(update=)`, which skips validation).
  `generators._find_or_add_inside_target` returns `(panel, index)`, and
  the new `_set_inside_content` swaps the copy in by index, so
  `apply_inside_letter` / `apply_inside_rich_content` /
  `_apply_inside_message` are one step each and order-independent. The
  two `text_elements.append` sites (front greeting and the inside
  auto-add) reassign the list. A front greeting over 1000 characters now
  raises at assignment. `Card.created_at` / `updated_at` and
  `model_post_init` (its docstring said "on any change", but it ran only
  at construction) are deleted: nothing read them (D17).
  `per_panel.py`'s two `model_copy(update=)` calls set constants
  (#73 already deleted the scaling), so they stay. Compile snapshots
  and visual baselines are unchanged, and suite time is the same
  (139.7 → 139.0 s). Guarded by `TestValidateAssignment` (the issue's
  four cases plus colour / theme / shape / list reassignment, and every
  non-frozen model in `models.py` has `validate_assignment` and
  `extra="forbid"`), `TestWithInsideContent` and
  `TestCardHasNoTimestamps` in `tests/unit/test_models.py`, and the new
  `tests/unit/test_generators_mutation.py` (an AST scan finds no
  `.append` / `.extend` / item assignment on a model list in
  `generators.py` or `card_request.py`, the inside surfaces switch in
  any order, the element and list are replaced rather than edited).
  Tests 2726 → 2800.

- **2026-09-29 — The gallery emits only commands `create` accepts:
  curated voices, a photo field, script-safe JSON (expert-panel §P14 /
  D15 / D4, issue #82)**: `scripts/build_microsite.py` hard-coded all five
  voices on every page, so `sympathy-spare` offered Witty / Irreverent
  (exit 2 since #60), photo templates had no way to pass `-i`, and the
  page metadata went into `<script>` through a bare `json.dumps`.
  `sentiments.available_voices(occasion, sentiments_dir=None)` now returns
  voices **in `VOICES` order** for which **both** `cover.yaml` and
  `inside.yaml` exist (was: sorted voice directories). The CLI's rule-11
  refusal uses it too, so its list reads `Available: warm, spare,
  devotional`, and a half-shipped voice (one role file) is refused as "not
  available" (was `has no inside sentiment`). The gallery renders an
  `<option>` per available voice and omits the `f-voice` select (and its
  JS) when there are none; `_VOICES` is deleted. `TemplateCard.
  has_photo_slot` is true when an `ImageElement` has a `slot` (what `-i`
  fills, #65; `image_elements: []` is false), and those five pages get a
  `Photo path` input `f-image` that pushes `-i <shellEscaped>`.
  `_script_json` (`ensure_ascii`, then `<` / `>` / `&` → `<` /
  `>` / `&`) encodes the `TEMPLATE` literal. **Found by the
  hostile-name test:** the page `<title>` interpolated `card.name`
  unescaped; it now goes through `html.escape`. Thumbnails are
  `build_card(CardRequest(template=id), templates_dir=builtin)` →
  `compile_card` → `PNGRenderer` (no `CardGenerator`; the `chdir` was
  already gone). Guarded by `test_available_voices_*` in
  `tests/unit/test_sentiments.py` and `TestVoiceOptions` /
  `TestPhotoField` / `TestScriptSafeJson` / `TestFormFlags` (every flag a
  page's `buildCommand` can push is a `create` option, read from the
  Typer command's params) / `TestSharedPipeline` in
  `tests/integration/test_microsite_build.py`. Tests 2712 → 2726.

- **2026-09-29 — AI imagery requests only model-supported sizes and bakes
  exactly trim+bleed at 300 PPI (expert-panel §P15 / D4, issue #87)**:
  the live client called `gpt-image-1` (fixed 1024², 1536×1024,
  1024×1536) with `size="1312x1824"` for moo-a6, which the API rejects,
  while the sidecar recorded `gpt-image-2`; the returned image was
  written as-is and the CLI printed the *requested* size. OpenAI docs
  re-verified 2026-09-29 (recorded in
  `docs/industry-review/openai-image-api-snapshot.md`). New in
  `core/ai_assets.py`: `DEFAULT_AI_MODEL = "gpt-image-2"` (the only
  default: `OpenAIImageClient`, `make_image_client(model=…)`,
  `build_ai_request(model=…)`; `LicenseRecord.model` has no default and
  `generate_ai_asset` records `client.model`, now part of the
  `ImageClient` Protocol), frozen `ModelSizePolicy` and
  `MODEL_SIZE_POLICIES` (gpt-image-1 / -1-mini / -1.5 fixed; gpt-image-2 /
  2.5-sunburst / 2.5-flare flexible: /16, aspect ≤ 3, edge ≤ 3840,
  655,360–8,294,400 px), `size_is_allowed(model, w, h)` and
  `choose_request_size(model, w, h)` (fixed: closest log-aspect, ties to
  the larger area; flexible: the target if valid, else aspect-clamped,
  scaled into limits and snapped to /16 preferring round-up so no axis
  under-resolves). An unknown model raises `ValueError` (D4), and
  `OpenAIImageClient` refuses a disallowed `size` before calling the API.
  `AIRequest` gains `request_width_px` / `request_height_px` / `model`;
  `width_px` / `height_px` are now exactly `round(in × dpi)` (moo-a6
  1314×1824, was 1312). The bake centre-crops to the target aspect and
  LANCZOS-resizes to the target, saving with `dpi=(300, 300)` + sRGB
  ICC; `LicenseRecord` gains `generated_width_px` / `generated_height_px`
  / `native_ppi` (`min(returned / target px) × 300`) and
  `GenerationResult` gains `width_px` / `height_px` / `native_ppi`. The
  CLI builds the request after creating the client (so it sizes for
  `client.model`), prints the written size and native PPI, and a yellow
  warning below 300 (the asset is still written). moo-a6 on gpt-image-2
  requests 1328×1824 and bakes at 300.0 native PPI; on gpt-image-1 it
  requests 1024×1536 (233.8 PPI, warned). `round_to_multiple` is deleted
  (D17). Guarded by `TestBuildAIRequest` / `TestModelSizePolicy` /
  `TestResampleToTarget` in `tests/unit/test_ai_assets.py`, the new
  `tests/unit/test_ai_openai.py` (every policy model × generate / edit
  sends an allowed `size`; refusals) and the written-size / low-PPI cases
  in `tests/integration/test_ai_asset_cli.py`. Tests 2678 → 2712.

- **2026-09-29 — Tag-driven PyPI release via trusted publishing; trimmed
  sdist; complete metadata (expert-panel §P15 / D1 / D2, issue #86)**:
  the project had never been published (PyPI 404, no tags, no publish
  workflow) and the version was hand-edited in two places. `pyproject.toml`
  now has `dynamic = ["version"]` + `[tool.hatch.version] path =
  "src/holiday_card/__init__.py"` (the literal `version =` is gone; `uv.lock`
  records the project as dynamic). New `.github/workflows/release.yml`
  (tags `v[0-9]+.[0-9]+.[0-9]+`, plus `pull_request` on its own paths;
  top-level `contents: read`, SHA pins): `build` runs `uv build`, refuses
  root-level `data/ docs/ .claude/ .specify/ .devcontainer/ specs/ output/`
  in the sdist, runs `uvx twine==7.0.0 check --strict`, installs the
  wheel in a clean venv, and on tags only checks `scripts/
  check_release_version.py check "$GITHUB_REF_NAME" <--version>` and that
  `RELEASE_NOTES.md` has a section for the tag, then renders
  christmas-classic (letter + moo-a6) from `$RUNNER_TEMP`; `publish`
  (`environment: pypi`, `permissions: id-token: write`, tag-only) uses
  `pypa/gh-action-pypi-publish` with no `password`; `github-release`
  (`contents: write`, tag-only) runs `gh release create --verify-tag
  --notes-file` with the notes from `check_release_version.py notes`. On
  a PR only `build` runs. `[tool.hatch.build.targets.sdist] include` is
  root-anchored (`/src/`, `/tests/`, `/LICENSE`, `/README.md`,
  `/RELEASE_NOTES.md`, `/pyproject.toml`, `/uv.lock`): **hatch treats
  them as gitignore patterns, so an unanchored `README.md` also pulls
  in every `.claude/**/README.md`**. Measured sdist 11.1 → 10.1 MB
  (fonts, the ICC profile and the visual baselines dominate; the gate is
  the exclusion list). Metadata: `authors` = Chris Lostaunau (no email),
  `[project.urls]` (Homepage / Source / Issues / Changelog /
  Documentation), a 3.13 classifier, no `License ::` classifier next to
  PEP 639 `license = "MIT"`, `license-files` (root LICENSE, Liberation
  LICENSE, the six curated `*-LICENSE.txt`, the ICC NOTICE), and
  `openai>=1.0,<4` (the lock resolves 3.19.2; the AI tests pass with the
  `ai` extra installed). `__author__` matches. Wheel METADATA is still
  `Version: 1.3.0`. Guarded by `tests/unit/test_packaging_metadata.py`
  (version single-sourced, `importlib.metadata.version == __version__`,
  classifiers, URLs, license files, openai cap, sdist include list
  anchored and clutter-free, release.yml triggers / permissions / OIDC /
  no password / tag gating, the tag check where `v1.3.1` vs `1.3.0` exits
  1, notes extraction) and, via `test_workflow_policy.py`, the #85 pins /
  permissions / no-`${{`-in-`run:` rules. Tests 2642 → 2678. `requires = ["hatchling>=1.27"]` (PEP 639).

- **2026-09-29 — CI hardening: least-privilege tokens, SHA-pinned actions,
  Dependabot, pip-audit, fork-PR guard (expert-panel §P15 / D2, issue #85)**:
  `ci.yml` and `latest-deps.yml` had no `permissions:` and every workflow
  used mutable tags. Now `ci.yml` / `latest-deps.yml` /
  `visual-baselines.yml` are top-level `contents: read` (render-cards and
  microsite keep their existing scopes) and every `uses:` in
  `.github/workflows/` is a 40-hex commit SHA with a `# vX.Y.Z` comment
  (each major tag resolved to its latest patch, so no behaviour changed).
  Every `actions/checkout` sets `persist-credentials: false`. New CI job
  `audit` (not in `build`'s `needs`, so the job graph is unchanged):
  `uv export --frozen --all-extras --no-emit-project` of `uv.lock` →
  `uvx pip-audit==2.10.1 --disable-pip --require-hashes --strict`; a known
  vulnerability fails it, and a suppression must be `--ignore-vuln <ID>`
  with a `#` justification on the same line. `latest-deps.yml` runs the
  same audit weekly, because new advisories land against an unchanged
  lock. New `.github/dependabot.yml`: `github-actions` (all actions in one
  group) and `uv` (minor + patch grouped), both weekly at `/`; it updates
  `uv.lock`, not the floors (D2). `render-cards.yml` stays on
  `pull_request` (never `_target`, spec §4); the two `peter-evans/` steps
  also require `github.event.pull_request.head.repo.full_name ==
  github.repository`, and a fork PR instead appends `comment-body.md` to
  `$GITHUB_STEP_SUMMARY`, so the read-only fork token no longer turns the
  check red with a 403. No `run:` script contains `${{ … }}` any more:
  values go through step `env:` (`BASE_REF`, `COUNT`, `RUN_NUMBER`,
  `RUN_URL`, `HEAD_SHA`, visual-baselines' `BACKEND`). The pre-commit
  `check-added-large-files` keeps `--maxkb=500` and excludes
  `^src/holiday_card/data/(fonts|icc)/` (the 3.4 MB ICC profile and 1.2 MB
  Cormorant). Guarded by `tests/unit/test_workflow_policy.py` (every
  workflow: SHA pins + version comments, a `permissions` mapping and no
  `write-all`, no `${{` in `run:`, credential-less checkouts; render-cards
  trigger, fork guard and summary fallback; the pinned strict audit in CI
  and latest-deps; justified suppressions; Dependabot ecosystems / grouping;
  the large-file exclude). Tests 2606 → 2642.

- **2026-09-29 — Branch-coverage floor of 92%; `preview` / `init`,
  shrink-to-fit and parser-property tests; a live fail-loud watchdog
  (expert-panel §P12 / D4 / D17, issue #84)**: coverage was measured in
  CI but never enforced. `[tool.coverage.report]` now has `fail_under =
  92` (the measured TOTAL, 92.20% branch coverage, rounded down; every CI
  leg measured the same) and `show_missing = true`, so the CI `pytest
  --cov` step fails below it with `FAIL Required test coverage`. Raise the
  floor when coverage rises; never lower it to pass a PR. New
  `tests/unit/test_cli_preview_init.py`: `preview` writes an `8.5·dpi ×
  11·dpi` PNG, a missing template exits 2 and writes nothing, `.png` is
  appended, voice + letter flags work, `--open` / `--no-open` and
  `_open_in_default_viewer` per platform with `subprocess.run` /
  `os.startfile` patched (plus the failure message); `init` round-trips
  through `load_template_from_file` with `check_template` clean, honours
  `--fold-type` and `--output`. `test_text_fitting.py` gains a half-em
  `HalfEmMeasurer`: the wrap strategy's binary search returns the largest
  size that fits (re-measured at `size` and `size + 1`, and equal to a
  brute-force search), never goes below `min_font_size`, and
  `apply_shrink_strategy` truncates maximally at the floor. First
  `hypothesis` use, `tests/unit/test_parsers_properties.py`
  (`max_examples=200, deadline=None`, < 1 s): generated
  `M/L/H/V/C/S/Q/T/Z` paths (abs + rel) round-trip, arbitrary text either
  parses or raises `ValueError` for `SVGPathParser.parse` and
  `parse_markdown`, plain lines round-trip as unstyled runs, and
  `***x***` is one bold-italic run. **Found by it:** `parse("Z0")` raised
  `ZeroDivisionError` (`len(params) % 0` for a zero-arity command); a
  parameter on `Z`/`z` is now the same arity `ValueError` as any other
  command. The watchdog `test_unsupported_features_raise_loudly` was an
  empty parametrize (the suite's one skip); it now adds an absolute and a
  relative SVG arc to christmas-classic and requires
  `UnsupportedFeatureError`. `SUPPORTED_REJECTING_TEMPLATES` is gone.
  Not done here: `per_panel._scale_shape` no longer exists (#73), so it
  gets no tests (D17); `tests/performance_validation.py` was already
  deleted by #83. Tests 2572 → 2606. Coverage: `cli/commands.py` 83 →
  87%, `core/text_fitting.py` 76 → 92%, `utils/svg_parser.py` 92 → 98%.

- **2026-09-29 — Dead modules, dead APIs and stale comments deleted
  (expert-panel §P15 / D17, issue #83)**: Removed, with no importers
  anywhere: `core/validators.py`, `utils/gradient_utils.py`,
  `renderers/image_effects.py` (the `ImageEffects` *model* stays; the
  compiler refuses it), `utils/validators.py` (every function left after
  #65 was unused, including `validate_dpi`; #66 owns the real PPI check)
  and the uncollected `tests/performance_validation.py` (it wrote
  `/tmp/perf_test` at import). Removed APIs: `TextElement.
  get_adjustment_result` / `set_adjustment_result` / `_adjustment_applied`
  (`AdjustmentResult` stays; `text_fitting` uses it), `CardGenerator.
  generate_pdf` and `create_and_generate` (use `create_card(...)` then
  `generate(card, out)`; the 9 `test_full_generation.py` callers were
  migrated). Compiler comments no longer cite the deleted
  `reportlab_renderer.py` / `shape_renderer.py`, the `_ = SVGCommand`
  import silencer is gone, and `_compile_image`'s docstring no longer
  lists heart / svg_path clip masks (`ClipMask` never had them). Tests:
  2587 → 2572 (−20 `test_validators.py`, −1 adjustment tracking, −2
  `test_core_purity` cases for `core/validators.py`, +8 guard cases).
  Guarded by `tests/unit/test_no_dead_modules.py` (the four modules raise
  `ModuleNotFoundError`; the four APIs are absent).

- **2026-09-29 — PNG backend: anti-aliased coverage masks, centred
  strokes, vectorized gradients, bbox-sized layers (expert-panel §P6 /
  D12 / D4 / D17, issue #77)**: `preview` drew every edge aliased,
  painted strokes inside the geometry (Pillow `outline=`) at whole-pixel
  widths (min 1), filled gradients pixel by pixel in Python and gave every
  translucent or clipped draw its own page-sized RGBA layer. Now every
  fill, stroke and clip is a per-shape `"L"` mask from
  `_coverage_mask(geom, bbox_px, *, stroke_width_px=None, dash=())`,
  drawn at `PNGRenderer.SUPERSAMPLE = 4`× inside the shape's pixel box and
  `reduce`d. Each supersample is painted when its centre is inside:
  rects / rounded rects / ellipses via `_pixel_span`, polygons and paths
  via the new nonzero scanline filler `_scan_fill` (Pillow's polygon
  filler floors vertices and fills both ends, a ¼ px bias per edge at 4×;
  a path is now one nonzero fill over all subpaths, as in PDF/SVG).
  Strokes: rect / circle / ellipse = the shape grown by `w/2` minus it
  shrunk by `w/2` (exact, fractional widths); polygons, polylines, paths
  and dashes = `_stroke_polygons` (a quad per segment plus a miter join,
  bevel past SVG's limit of 4, butt caps). Neither PDF nor SVG sets a
  join or cap, so a `line_cap` other than `butt` now raises
  `NotImplementedError` (D4 / D12; the compiler only emits `butt`).
  Bezier flattening scales with the control polygon (≥ 16, one sample per
  4 px, ≤ 512). The colour composites through the mask on a layer the
  size of that box (`_paint_mask` → `_composite(layer, dest, alpha)`,
  which crops the clip mask and the canvas overlap); text uses its ink box
  (`font.getbbox`), images their own size. Fold lines are a 0.5 pt stroke
  like PDF/SVG (were 1 px). Gradients: `_gradient_t` builds `255·t` as an
  `"L"` image with `ImageMath.lambda_eval` over pixel-centre ramps
  (clamped, rounded) and `_draw_shape_with_complex_fill` maps it through
  256-entry `_interp_stops` LUTs per channel (±1/255 of the per-pixel
  reference, now sampled at pixel centres; 1000×1000 px in ~50 ms; paths
  can take gradients now). A group overlay is transformed over its
  content's box only (`getbbox` + the forward `_pixel_affine`), not the
  page. `PNGRenderer(dpi, antialias=True)`; `antialias=False` samples once
  per pixel (every pixel in or out, strokes ≥ 1 px) for exact-pixel tests.
  Deleted (D17): `_draw_in_layer` / `_in_layer`, `_draw_text_in_layer`,
  `_shape_needs_alpha_compositing`, `_geom_mask`, `_draw_geom_mask`,
  `_geom_bbox_px`, `_render_complex_fill_into`, `_draw_path`,
  `_stroke_outline`, `_draw_dashed_polyline`, `_inverse_pixel_affine`,
  `self._draw`. Timing at 300 DPI (render only, macOS): winter-sky 2.36 →
  0.42 s, holiday-masterpiece 4.96 → 0.67 s, festive-stripes 1.03 →
  0.99 s; `preview christmas-winter-sky --dpi 300` 2.80 → ~1 s wall
  and lower peak RSS. Conformance: PNG tolerance 2.0% → **1.0%**
  (`TOLERANCE` moved to `capabilities.py` and printed in
  `docs/conformance-matrix.md`), `stroke_rect_6pt` PNG flipped
  `known_diff` → `match` (7.35% → 0%); every stroke / edge / clip /
  gradient / pattern case is now ≤ 0.05% (was up to 1.23%); the worst PNG
  case is `group_square_scale2_*` at 0.75% (bicubic overlay resampling).
  The 15 PNG visual panels that moved were regenerated by the
  `visual-baselines` workflow and eyeballed against the PDF render (all
  but three moved closer to it; those three are half-pixel stripe and
  checker edges, now exact area coverage as in resvg, where pdfium
  snaps). PDF baselines and compile snapshots are unchanged. Guarded by
  the #77 block in `tests/integration/test_png_backend.py` (centred 10 pt
  stroke, 0.5 pt partial coverage, ≥ 3 AA levels / exactly 2 with
  `antialias=False`, centre-rule polygon, 4 pt line rows, miter corner,
  `line_cap` refusal, bbox-sized allocations via an `Image.new` spy,
  content-box group transform, short Bezier chords),
  `tests/unit/test_png_gradients.py` (linear / radial vs the reference at
  5 points, < 0.5 s for 1000×1000, no `for y in range(h)`) and
  `test_png_draws_pattern_primitives_on_one_layer`.

- **2026-09-29 — Core measures text through an injected `TextMeasurer`;
  no core module imports ReportLab or the renderers (expert-panel §P13 /
  §4 / D4 / D17, issue #75)**: the compiler measured through a throwaway
  ReportLab `Canvas` and imported `renderers.font_registry`, `flatten`
  and `template_checks` did the same, and `generators.py` imported all
  three backends at module level, so the decision layer depended on the
  PDF backend and tests could not inject deterministic metrics. New
  stdlib-only `core/text_measure.py`: `TextMeasurer` Protocol
  (`string_width(text, font_id, size_pt)`, `ascent_descent(font_id,
  size_pt)` for the #73 safe-zone check, `known_font_ids()` for the #60
  font refusal and `validate`'s font check; the issue named only
  `string_width`, but those two call sites landed after it was written),
  `set_default_text_measurer(factory)` and `default_text_measurer()`
  (`RuntimeError("no TextMeasurer registered…")` when unset, D4). New
  `renderers/reportlab_measurer.ReportLabTextMeasurer` registers the
  fonts and calls `pdfmetrics.stringWidth` / `getAscentDescent` on the IR
  `font_id`, exactly what `Canvas.stringWidth` did. `holiday_card/
  __init__.py` is the composition root: it registers a factory that
  imports that module on first call, so `import holiday_card` loads no
  ReportLab. `CompileContext.measurer: TextMeasurer | None`; `compile_card`
  uses `ctx.measurer or default_text_measurer()`; `_make_measurer` is
  deleted (D17). `text_utils` / `text_fitting` take a `measurer:
  TextMeasurer` where they took a canvas (same positions).
  `Flattener(measurer=None)` / `flatten_transparency(..., measurer=None)`
  measure text boxes on the IR `font_id` (it used the resolved Liberation
  name, up to 0.03% wider; no flatten decision changed).
  `generators.Renderer` is now a `runtime_checkable` Protocol
  (`file_extension`, `color_space`, `render`); the default PDF renderer is
  built by `_pdf_renderer()` with a function-local import, and the CMYK
  swap checks `file_extension == ".pdf"` instead of `isinstance`. SVG and
  PNG backends gained `color_space = "srgb"`. A regression oracle hashed
  the compiled IR of all 21 templates × 4 content modes (default, long,
  Markdown, structured letter) × {letter, letter + flatten, per-panel-pdf,
  moo-a6 fill, moo-a6 letterbox} × every panel (1176 entries) before and
  after: byte-identical. Snapshots and visual baselines unchanged; the
  christmas-classic PDF rasterizes pixel-identically to `main`. Guarded
  by `tests/unit/test_core_purity.py` (AST scan of every `core/*.py`,
  nested imports included, and subprocess checks that importing the
  package, the compiler and every core module loads neither `reportlab`
  nor `holiday_card.renderers`), `tests/unit/test_text_measure.py` (a
  `FixedWidthMeasurer` drives wrap points, known fonts, safe-zone and
  flatten boxes; the unregistered default raises),
  `tests/unit/test_reportlab_measurer.py` (== `Canvas.stringWidth` for
  every `FONT_MAP` + `CURATED_FONTS` id at 3 sizes) and
  `tests/unit/test_generators_renderer.py` (every backend satisfies the
  Protocol; a Protocol-only renderer generates; the CMYK swap).

- **2026-09-29 — SVG output embeds glyph subsets of the fonts the
  compiler measured (expert-panel §P13 / D4 / D12, issue #76)**: the SVG
  backend wrote a bare `font-family="Caveat"` with no font data, so each
  viewer substituted its own font (33% wider than Caveat at 18 pt) and the
  text overflowed the boxes the compiler wrapped with ReportLab. New
  `renderers/svg_fonts.py`: `subset_font_bytes(ttf_path, text, *,
  family_name)` runs `fontTools.subset` with fixed options (the chars
  drawn plus `.notdef`; no GSUB / GPOS / GDEF / kern, because ReportLab
  measures unkerned advances; no hinting; source `head.modified` kept, so
  output is byte-stable) and renames the subset to its CSS family
  `hc-<font_id>`, keeping the copyright / license name records. That
  rename is how non-browser tools find it: resvg, rsvg and Inkscape ignore
  `@font-face` and match the font's own name table. **Variation tables
  (`fvar` / `gvar` / `avar` / `HVAR` / `MVAR` / `STAT` …) are dropped**,
  so a variable master is embedded as its static default instance. The
  issue assumed viewers render the default axes, but browsers and resvg
  apply `font-optical-sizing: auto`, which drew Inter (`opsz` 14 by
  default) at `opsz` 32 for 32 pt text, visibly narrower than the PDF.
  `font_face_css(font_id, ttf_path, text)` gives the rule, `css_family` /
  `svg_font_family` the names, and `GENERIC_FAMILY` maps every font_id to
  serif / sans-serif / cursive / monospace. `SVGRenderer` collects the
  chars per font_id and at `EndPage` inserts one `<style>` with one
  `@font-face { … url(data:font/ttf;base64,…) format("truetype"); }` per
  font_id (sorted), preceded by an XML comment naming each face and the
  SIL OFL 1.1. `<text>` now says `font-family="'hc-Caveat', cursive"`. A
  font_id with no TTF (`ttf_path_for` → `None`) raises `NotImplementedError
  ("SVG backend cannot embed font 'NoSuchFont'")` at the `DrawText`. The
  christmas-classic SVG is 12.9 KB (11 KB of base64 font data) and
  byte-identical across runs. New dependency `fonttools>=4.47` (in
  `uv.lock`; mypy override `fontTools.*`). Conformance: the SVG rasterizer
  pulls the embedded subsets out of the SVG and passes them to resvg as
  `font_files`, with no `font_dirs`, so the oracle draws text only with
  what the file carries. `text_curated_family` (known_diff #76) became 7
  `text_family_*` cases (Cormorant, Cormorant-Italic, PlayfairDisplay,
  Inter, Caveat, Comfortaa, Helvetica), all `match` on PDF and PNG;
  `docs/conformance-matrix.md` regenerated. **OFL note:** Lato, Comfortaa,
  Playfair Display and Liberation declare Reserved Font Names (the issue
  said none do); the embedding is treated like the PDF's per-document
  subsets (`ABCDEF+Lato`), with the `hc-` tag and the original copyright /
  license records kept. Snapshots and visual baselines are unchanged (both
  are PDF / PNG). Guarded by `tests/unit/test_svg_fonts.py`, the `#76`
  block in `tests/integration/test_svg_backend.py` (every `<text>` names an
  embedded face + generic, one `@font-face` per family, each cmap covers its
  chars, the license comment, byte stability, the refusal, and
  christmas-classic advances within 0.5% of `pdfmetrics.stringWidth`) and
  `tests/conformance/test_template_text_parity.py` (all 21 templates' text,
  SVG vs PDF per panel, ±2 px; 21 of 21 fail on the old backend).

- **2026-09-29 — Pattern fills are lowered by the compiler; the three
  backend tilers are deleted (expert-panel §P13 / D13, issue #74)**: PDF,
  SVG and PNG each tiled `PatternPaint` differently. On festive-stripes
  the 90° ribbon was mostly missing in PNG and mostly solid in PDF, 45°
  stripes lost their corners, and SVG grid / checker used half the PDF
  spacing. New `compiler._lower_pattern_fill(fill, geometry, bbox_pts,
  stroke, opacity, *, where=)` emits `BeginClip(shape)` →
  `BeginGroup(Transform(pivot = bbox centre, rotate_deg), opacity =
  shape opacity)` → a `colors[0]` background → `colors[1]` primitives →
  `EndGroup` → `EndClip` → the stroke (fill `None`), if any. The group is
  always emitted, so opacity composites once. Semantics (docstring):
  `period = spacing × scale` in pt; tiles hang from the bbox top-left;
  stripes are one full-width band `period/2` tall per row, dots a circle
  of radius `period/4` at each tile centre, grid one 1 pt vertical and
  one horizontal line per tile, checkerboard `period/2` squares at the
  tile's top-left and bottom-right; a rotated pattern covers the bbox's
  circumscribed square. A single-colour pattern is just the background.
  Period < 2 pt, or > 20 000 primitives, raises `UnsupportedFeatureError`
  naming the shape (`Rectangle id 'ribbon'`) and the numbers. Rectangle,
  circle, triangle, star and SVG-path shapes route through `_draw_filled`
  (the SVG path's bbox is its transformed control-point hull); lines take
  `_resolve_stroke` only. Deleted (D17): `PatternPaint` (class, `PaintU`
  member, `__all__`), `_pattern_to_paint`, the PDF `_draw_pattern_tile`,
  the SVG `_register_pattern`, the PNG `_render_pattern_into` and their
  dispatch branches, and the flattener's pattern blending. Consequences:
  CMYK needs no pattern code (primitives are `SolidPaint`); a
  translucent pattern on a PDF/X target is refused by the flattener (its
  background and primitives overlap inside a translucent group), and
  `BeginGroup.opacity < 1` still raises in PDF / PNG. The flattener drops
  rotated bands its clip box culls entirely. **PNG changes found on the
  way:** (1) an identity `BeginGroup` opened under a clip now gets its own
  overlay, so a pattern's primitives draw directly and are clipped once
  (festive-stripes went 0.11 s → 2.0 s with one canvas-sized layer per
  clipped primitive; now 0.24 s); (2) Pillow's box end is inclusive, so a
  fill-only rect drew one pixel too wide (a 2 px grid line was 3 px):
  unstroked rects now fill the pixels whose centres are inside
  (`_pixel_span`; abutting checker cells get exactly one owner per
  pixel), and fill-only circles / ellipses inset their box by 0.5 px.
  Measured against the SVG oracle, PNG moved closer on every template it
  changed. Both are interim until #77's coverage masks. Conformance: the
  4 `pattern_*` cases became 12 (`pattern_{kind}_{0,45,90}`, built with
  `_lower_pattern_fill`), all `match` on PDF and PNG;
  `docs/conformance-matrix.md` regenerated. Regenerated on purpose: the
  festive-stripes compile snapshot, the festive-stripes and
  holiday-masterpiece entries of both PDF goldens, and the visual
  baselines for festive-stripes and holiday-masterpiece (PNG + PDF) plus
  10 other PNG sheets whose rect / disc edges moved by a pixel
  (0.005–0.56% of a panel; menorah, balloons and artist were over the
  gate), generated by the `visual-baselines` workflow and eyeballed. Guarded by
  `tests/unit/test_compiler_patterns.py`, `test_pattern_is_not_an_ir_paint`
  in `test_render_ir.py`, `TestFestiveStripesRibbon` /
  `test_png_draws_pattern_primitives_on_one_layer` in
  `test_gradients_patterns.py`,
  `test_png_fill_only_rect_covers_exactly_its_pixels` in
  `test_png_backend.py`, `test_translucent_pattern_is_refused` in
  `test_compiler_flatten.py` and the pattern conformance cases.

- **2026-09-29 — `validate` checks fonts, bounds, theme and compiles;
  `holiday-card schema`; template-authoring guide (expert-panel §P3 / D3 /
  D4, issue #57)**: `validate` only loaded the YAML, so an unknown font or
  an element at `x: 99` said `Template valid` and failed at `create`. New
  pure `core/template_checks.py`: `check_template(template) ->
  list[TemplateProblem(path, message)]` reports every problem: a
  `font_family` outside `known_font_ids()` (unless `font_file` is set), a
  text anchor, shape bbox (rect / circle / star outer radius / triangle /
  line unrotated; SVG path from `_compile_svg_path`, rotation included) or
  image rect outside `[0, width] × [0, height]` (1e-6 in slack), a
  `default_theme_id` that `load_theme` can't find, and a compile smoke
  (`create_card_from_template` + `compile_card`; `UnsupportedFeatureError`
  / `KeyError` / `ValueError` → a `<compile>` problem; an `UnknownFontError`
  already reported by the font check is not repeated). Paths read
  `panels[front].text_elements[greeting].font_family`, using the element
  `id` only when the YAML set one (else the index). `TemplateLoadError`
  gained `.problems: list[(path, message)]`, and loader locations are now
  `panels[0].text_elements[0].colr` (was dotted `panels.0.…`) in the
  message too; an unreadable file is one `<file>` problem. `validate`
  prints `Template invalid: <ref>` plus `  - <path>: <message>` lines on
  stdout and exits 2 (was a one-line stderr message), or the old summary.
  New `holiday-card schema [-o PATH]` prints
  `core/template_schema.render_template_schema()`: `Template.
  model_json_schema()` with a draft 2020-12 `$schema`, sorted, indent 2,
  plus every `AliasChoices` spelling as a property (a required field
  needs any one, via `allOf`/`anyOf`), because Pydantic lists only the
  first and the shipped `x1`/`y1` lines failed `additionalProperties:
  false`. Committed as `docs/template-schema.json`; regenerate with
  `holiday-card schema -o docs/template-schema.json`. `jsonschema` joins
  the dev extras. New `docs/template-authoring.md` (linked from README);
  `specs/004-*/contracts/yaml-schema.md` is marked superseded. **Found by
  the theme check:** christmas-geometric (`christmas-earth-tones`) and
  christmas-metallic-ornaments (`christmas-gold-burgundy`) named themes
  that never existed; both now say `christmas-gold` (the id only reaches
  PDF/SVG metadata, so 2 compile snapshots changed in `theme_id` and
  nothing else). `create_card_from_template` (#78) stands in for the
  issue's `card_from_template`. Guarded by
  `tests/unit/test_template_checks.py` (every check, all at once, all 21
  templates clean), `TestValidateCommand` / `TestSchemaCommand` in
  `test_cli.py`, `tests/unit/test_template_schema.py` (drift guard; every
  shipped YAML validates against the committed JSON; alias spellings) and
  `tests/unit/test_template_authoring_doc.py` (every YAML example in the
  guide passes `check_template`, the font table is complete).

- **2026-09-29 — BREAKING: `-o` means `--output` everywhere; listing
  tables lead with the ID; grouped help; documented exit codes
  (expert-panel §P14 / D16, issue #80)**: `templates`, `themes` and
  `init` used `-o` for `--occasion` while `create`, `preview` and
  `ai-asset generate` used it for output. Now `--occasion` has **no short
  flag** (`templates -o christmas` is `No such option: -o`, exit 2),
  `init -o DIR` is `--output`, and `ai-asset generate --out` is renamed
  `--output` (no alias, D17). The `templates` table is `ID OCCASION FOLD
  [SOURCE] NAME` (SOURCE only when a user / env layer contributes, #79),
  `themes` is `ID OCCASION NAME`; both are sorted by `(occasion, id)`,
  sized to their widest cell with nothing truncated, and drop the
  description (`--format json|yaml` payloads are unchanged).
  `--format` is a `ListFormat` `StrEnum`, so `--format xml` is a click
  usage error (exit 2) instead of a silent table. `create` / `preview`
  options sit in Rich panels Content / Inside letter / Layout / Output
  (panel order follows parameter order, so the signatures were
  reordered; `--panel-fit` is Layout, `--allow-low-res` Output).
  New `cli/exit_codes.py`: `ExitCode` (OK 0, ERROR 1, USAGE 2,
  CONSENT_REQUIRED 3, ENVIRONMENT 4, RAIL_REFUSED 5; numbers unchanged)
  and `EXIT_CODES_HELP`, the root `--help` epilog. Every `typer.Exit` in
  `commands.py` uses `ExitCode.*`; a test greps for `typer.Exit(<digit>`.
  README gains an "Exit codes" table. Guarded by `TestShortFlags`,
  `TestListingTables` (every listed id `create`s, all 21),
  `TestHelpPanels` and `TestExitCodes` in `tests/unit/test_cli.py`.

- **2026-09-29 — Template paths and a layered template search path;
  `init` → `create` works (expert-panel §P14 / D1 / D15, issue #79)**:
  `holiday-card init foo` wrote `templates/generic/foo.yaml` under the
  cwd, which nothing searched, so the suggested `create foo` failed.
  `create ./my-template.yaml` (README example 5) failed too, because
  `load_template` never treated its argument as a path. New in
  `core/templates.py`: `user_templates_dir()`
  (`$XDG_DATA_HOME/holiday-card/templates`, default
  `~/.local/share/…`; an empty `XDG_DATA_HOME` counts as unset),
  `template_search_path() -> [(source, dir)]` (each `os.pathsep` entry of
  `HOLIDAY_CARD_TEMPLATES` as `"env"`, then `"user"`, then `"builtin"`;
  missing dirs are skipped like `PATH`), `is_template_path(ref)` (ends
  `.yaml`/`.yml`, contains `/` or `os.sep`, or starts with `.`/`~`) and
  `resolve_template(ref, *, templates_dir=None) -> (Template, abs path)`.
  A path ref loads the file directly; a missing file raises
  `TemplateNotFoundError("Template not found: <ref>")`. An id ref is
  looked up by `id:` across all layers, then by file stem across all
  layers, so an id match in a later layer beats a stem match in an
  earlier one. `templates_dir=` makes that one dir the only layer (source
  `"dir"`). Layers are walked recursively for `*.yaml`/`*.yml`.
  `discover_templates()` adds `source` and, for a template whose id
  appears in a later layer too, `shadows` (the first one wins and is
  listed once). It reads `occasion` from the YAML, not the directory, and
  skips non-mapping YAML. `load_template(id, dir)` is a thin wrapper;
  `get_templates_dir` is deleted (D17). **`HOLIDAY_CARD_TEMPLATES` no
  longer replaces the bundled templates**: it is gone from
  `data_paths.ENV_OVERRIDES`, so `data_path("templates")` is always the
  bundled dir (themes and sentiments still replace). `templates` with no
  filter exits 1 when no template has `source == "builtin"`.
  Consumers: `build_card` calls `resolve_template` (so `--voice` on a
  path-loaded template uses its own `occasion`), `validate` too (its
  path special case is deleted; it now also prints `Path:`), and
  `scripts/build_microsite.py` passes the bundled dir explicitly, so a
  user's or an env layer's templates never reach the gallery.
  `init`: defaults to `user_templates_dir()/<occasion>/`, refuses an
  `--occasion` outside `OccasionType` (exit 2, lists them), refuses to
  overwrite without the new `--force` (exit 2), and prints `holiday-card
  create <name>` only when `resolve_template(name)` finds the new file,
  otherwise the (shell-quoted) path. `tests/conftest.py` points
  `XDG_DATA_HOME` at a fresh temp dir in `pytest_configure`, so the suite
  never reads the real user layer. Guarded by the search-path / discover /
  resolve classes in `tests/unit/test_templates.py`,
  `TestInitThenCreate` / `TestTemplatePaths` in `test_cli.py`,
  `test_templates_env_var_does_not_replace_the_bundled_dir` in
  `test_data_paths.py` and
  `test_gallery_shows_only_the_builtin_templates` in
  `test_microsite_build.py`.

- **2026-09-29 — Print targets warn below 300 and refuse below 150
  effective PPI (expert-panel §P8 / D4 / D8, issue #66)**: nothing checked
  photo resolution, so `create -i thumb.jpg --export-for moo-a6` shipped a
  soft print silently (the 400 px `tests/fixtures/sample_photo.jpg` in
  family-photo's 2.95" slot is 136 PPI). `core/images.py` gains
  `RECOMMENDED_PRINT_PPI = 300`, `MIN_PRINT_PPI = MIN_DPI` (150;
  `utils/measurements.MIN_DPI` stays as the one value), the frozen
  `ResolutionFinding(source, ppi, level, needed_width_px,
  needed_height_px)` (pixels needed at 300 PPI at the placed size),
  `effective_ppi(ref, group_scale=1.0)` (`preserve_aspect` "meet" → `max`
  of the axis PPIs, stretch → `min`; rotation ignored),
  `check_print_resolution(commands, *, warn_below=300, fail_below=150)`
  (a `BeginGroup` stack of `sqrt(|scale_x·scale_y|)`, so the #73 fill
  scale counts: 136 → 128 PPI under moo-a6; fail beats warn),
  `describe_finding`, `LowResolutionWarning(UserWarning)` and
  `LowResolutionImageError(ValueError)` (carries `.findings`).
  `ExportTarget.checks_print_resolution: bool = True` (all three targets).
  `CardGenerator.generate(..., allow_low_res: bool = False)` checks the
  compiled IR in `_generate_imposition` / `_generate_per_panel` (all
  panels, before any file or directory is written) only when
  `renderer.file_extension == ".pdf"` and the target opts in: any `fail`
  raises `LowResolutionImageError` unless `allow_low_res`, and every
  remaining finding (deduplicated by message) is a
  `warnings.warn(..., LowResolutionWarning)`, the same channel as
  `SafeZoneWarning`. SVG, PNG and `preview` are never checked. CLI
  `create --allow-low-res` (`CardRequest.allow_low_res`) is for proofs
  only; warnings print as `Warning: me.jpg is 237 PPI at its placed size
  (300 recommended; need ≥ 885×885 px)` and the error maps to exit 2 via
  the existing `ValueError` branch. The shipped placeholders are ≥ 375 PPI
  on letter. Guarded by `tests/unit/test_images_resolution.py`,
  `TestPrintResolutionGate` in `test_image_rendering.py` (CLI exit codes,
  no file written, moo-a6 fill scale, SVG skip, target opt-out) and
  `TestShippedTemplatesPrintResolution` in `test_full_generation.py`
  (21 templates × 3 targets, zero findings).

- **2026-09-29 — moo-a6 fills the A6 trim via one compiler scale group;
  letterbox is opt-in (expert-panel §P11 / §P8 / D8, issue #73)**: MOO A6
  panels had ~0.24" of white paper top and bottom, because
  `per_panel.prepare_scaled_panel` scaled by `min(4.13/4.25, 5.83/5.5)`
  and centred the result, and bleed only extended edges that touched the
  trim. Its per-type rescaling also skipped images, SVGPath `x`/`y`,
  radial-gradient geometry, strokes, borders, pattern spacing and
  letter/rich text sizes, and it rounded `font_size`. `ExportTarget.
  scale_panels_to_fit` is replaced by `panel_fit: Literal["native",
  "fill", "letterbox"]` (`PanelFit`): `per-panel-pdf` is `native` and
  `moo-a6` is `fill`, with the description and docstring rewritten.
  `CompileContext.panel_fit` makes `compile_card` require exactly one
  panel at the origin with no rotation (otherwise `ValueError`). It then
  replaces that panel's group transform with `Transform(scale = s,
  offset = centre)`, pivot (0,0), where `s = max(tw/pw, th/ph)` for fill
  (1.0600 letter→A6) and `min` for letterbox (0.9718). Every element,
  photos included, scales inside that one group, so no per-type code is
  left. `_fitted_bleed_rect` extends the background by `bleed / s` in the
  native frame on every edge the scaled panel reaches: all four under
  fill, left/right only under letterbox. `_warn_outside_safe_zone`
  maps each `DrawText` run's measured box (advance width ×
  ascent/descent, through the fit group and any text-rotation group) and
  emits `SafeZoneWarning(UserWarning)` naming
  `<template>/<panel>/<element>` and the overshoot in inches when the
  box leaves the ArtBox. It fires only for `panel_fit != "native"`. The
  CLI prints each warning as `Warning: …` on stderr and exits 0. Six
  shipped templates warn under moo-a6: the classic, festive-stripes,
  modern, winter-sky and mothers-day greetings (0.005–0.17"), and
  photo-ornament's inside message (1.5"). The last is a template bug: it
  is centre-aligned at x=0.5", so it hangs off the panel on every target.
  New `create --panel-fit fill|letterbox` goes through
  `CardRequest.panel_fit`. On a native target it is refused with exit 2
  (D4). Otherwise `plan_output` returns `replace(target,
  panel_fit=…)`. Deleted (D17): `prepare_scaled_panel`, `_scale_text`,
  `_scale_shape` and `build_per_panel_card`'s `target` argument; the
  panel always stays native. MediaBox is unchanged at 315.36×437.76 pt.
  Compile snapshots and visual baselines are unchanged (both are
  letter-only). Guarded by `TestPanelFit` / `TestSafeZoneWarning` in
  `test_compiler.py`, `TestMooA6FillsTrim` (PNG + pdfium edge pixels on
  all 4 panels), `TestMooA6Photo` (image rect native inside the scale
  group; a pixel inside the ornament clip matches the native photo) and
  `test_moo_a6_has_no_white_band_the_native_panel_lacks` (all 21
  templates: every white row/column in the A6 trim maps to a white one in
  the native render) in `test_per_panel_output.py`, `TestPanelFit` in
  `test_card_request.py` and `TestPanelFitOption` in `test_cli.py`.

- **2026-09-29 — Per-panel 144 DPI visual gate on PNG and PDF (expert-panel
  §P12 / D12, issue #68)**: The old gate hashed the whole 72 DPI PNG sheet
  (64-bit phash, threshold 5), so "all fonts → Lato" (distance 6) and
  inside-panel changes slipped through, and PDF had no pixel baseline.
  `tests/visual/test_visual_regression.py` now renders every shipped template
  × {png, pdf} on the letter target (fold marks off) at 144 DPI (PDF via
  pypdfium2), crops each panel where `imposition.panel_placements` puts it
  (inset 2 px), and fails a panel when more than 0.25% of its pixels differ by
  more than 32 on any channel: 21 × 2 × 4 = 168 comparisons. Helpers and the
  calibrated constants (`DPI`, `CHANNEL_DELTA`, `MAX_PANEL_RATIO`,
  `CROP_INSET_PX`) live in `tests/visual/visual_gate.py`, shared with
  `scripts/regenerate_visual_baselines.py` (now `--backend {png,pdf,all}`,
  `--template ID`, prints per-panel ratios vs the old baseline).
  `test_visual_gate_sensitivity.py` applies the calibration mutations to
  christmas-classic on both backends and requires every touched panel to trip
  (smallest: inside text removed, 0.51% PNG), so raising the limit fails it.
  Baselines are full sheets in `fixtures/reference_cards/{png,pdf}/`
  (1.9 MB), **generated on ubuntu-latest** by the new `visual-baselines`
  workflow (`workflow_dispatch`, uploads an artifact to eyeball and commit);
  the old root-level 72 DPI PNGs are deleted. On failure the CI test job
  uploads fresh sheets, crops and red diff heatmaps (`visual-out-*`,
  `HOLIDAY_CARD_VISUAL_OUT`). **Cross-host finding:** PDF rasters are
  identical on macOS and Ubuntu, but PNG text depends on whether Pillow can
  load libfribidi, which switches on its raqm (kerning) layout: without it
  text panels differ by up to 1.64%. ubuntu-latest has it; CI installs
  fribidi on macOS (exported `DYLD_FALLBACK_LIBRARY_PATH`, since SIP strips
  it from `/bin/bash`), which brings macOS to ≤ 0.102%, so both OSes are
  gated. `HOLIDAY_CARD_REQUIRE_PNG_VISUAL=1` (set in CI) turns the no-raqm
  skip into a failure, and the regenerate script refuses PNG without raqm.
  `tests/rasterize.py` now holds the pdfium rasterizer shared with the
  conformance suite. `imagehash` (and with it numpy) left the dev deps.
  Guarded by `test_visual_gate_sensitivity.py`,
  `test_visual_gate_crops.py` (boxes tile the sheet, 612×792 px each) and
  `test_regenerate_baselines_script.py`.

- **2026-09-29 — IR `Transform` is an explicit affine: pivot, rotate,
  scale about the pivot, offset (expert-panel §P11 / §P7 / D14, issue
  #72)**: `Transform.translate_x/y` held the rotation pivot, and the
  backends disagreed on `scale`: PDF scaled about the page origin, SVG
  about the pivot, and PNG raised. `core/render_ir.Transform` now has
  `pivot_x/y`, `rotate_deg`, `scale_x/y` (`gt=0`) and `offset_x/y` and is
  defined as `p' = T(offset)·T(pivot)·R(rotate, CCW)·S(scale)·T(−pivot)·p`.
  `is_identity()` ignores the pivot and `to_matrix()` returns the PDF `cm`
  tuple. The old names are removed, not aliased (D17), so
  `Transform(translate_x=…)` fails `extra="forbid"`. The four producers
  (panel, SVGPath, image and text rotation) pass `pivot_*`. PDF emits one
  `canvas.transform(*t.to_matrix())`. SVG keeps its decomposed string, with
  `translate(offset_x −offset_y)` in front. PNG replaced `overlay.rotate` with an
  AFFINE `overlay.transform` whose inverse coefficients come from
  `to_matrix()` conjugated by the IR→pixel map; its non-unit-scale raise is
  gone. `core/flatten` uses `to_matrix()` too (its copy of the old PDF
  order is deleted). The compiler still emits no scale (#73). The 16
  compile snapshots changed only by key rename plus default `offset_*`
  (checked with a key-renaming diff). Visual baselines are unchanged, and
  `christmas-classic` PDF rasterizes pixel-identically to `main`. The one
  `letter_content_sha256` entry that changed is
  christmas-holiday-masterpiece: a 45° `cm` translation moved from
  −29.93745 to −29.93729 (float rounding; ≤ 2/255 of AA noise at 300
  DPI). Guarded by `TestTransformMatrix` in `test_render_ir.py`, the
  `group_square_*` conformance cases (scale about the pivot, +rotate,
  +offset, nested scale-in-rotate; `group_scale_pivot` flipped to `match`
  for PDF and PNG), `tests/conformance/test_group_transform.py` (the SVG
  oracle vs a step-by-step formula) and
  `test_group_scale_is_about_the_pivot` in `test_compiler_flatten.py`.

- **2026-09-29 — PDF/X output has no transparency and no RGB images;
  every PDF/X file is preflighted (expert-panel §P9 / D10, issue #71)**:
  moo-a6 files carried ExtGState `/ca`/`/CA` < 1 (13 templates) and
  DeviceRGB photos with SMasks (5), both forbidden by PDF/X-1a.
  (1) New `CompileContext.flatten_transparency` (set by
  `build_per_panel_context` and `_generate_imposition` when
  `target.pdfx` is set) runs each panel's draws through
  `core/flatten.Flattener`: effective alpha = opacity × paint alpha ×
  every enclosing group opacity (groups are re-emitted at 1). A draw
  below 1 needs a known solid backdrop: the topmost earlier draw whose
  box meets the draw's box (panel frame; group transforms and clips
  applied as axis-aligned boxes; a stroke-only untransformed rect only
  "meets" boxes that touch its stroke band) must be an opaque solid
  rect / circle / ellipse fill that contains the box (rect: box
  inside, circle/ellipse: 4 corners inside, both inset by half the
  stroke); nothing earlier → paper white. The colour is composited in
  sRGB (`a·src + (1−a)·backdrop`, gradient stops and pattern colours
  too) and emitted opaque. Anything else (gradient, pattern, polygon,
  path, image or text backdrop, partial overlap, rotated or
  non-rect-clipped backdrop, a translucent group whose children
  overlap) raises `UnsupportedFeatureError` naming
  `<template>/<panel>/<list>[i] (<type>, id '…')` and the backdrop, e.g.
  "sits over a solid rect that does not fully contain it". A fully
  transparent draw is dropped. `flatten_transparency(commands, where=)`
  flattens hand-built IR. `DrawImage` records the solid backdrop on the
  new `ImageRef.backdrop: RGBA | None` (and carries the effective
  opacity); an image with alpha or opacity < 1 and no solid backdrop
  raises. (2) `IRReportLabRenderer(color_space="cmyk")` raises
  `NotImplementedError` ("compile with …flatten_transparency=True") for
  any alpha < 1 (shape, stroke, text, gradient stop, pattern colour)
  and never sets alpha; `CMYKColor` no longer takes `alpha`.
  `_draw_cmyk_image` opens the source with Pillow, composites alpha ×
  opacity over `ImageRef.backdrop` (raises without one), converts with
  `CMYKConverter.convert_image` (embedded ICC honoured) and embeds the
  CMYK image unmasked. The sRGB path is unchanged. (3)
  `CardGenerator._maybe_apply_pdfx` runs `preflight_pdfx1a` after
  `apply_pdfx1a` and raises the new
  `pdfx_preflight.PDFXConformanceError(path, violations)`; the CLI maps
  it to exit 2 listing each rule. (4) Templates: christmas-winter-sky
  (hills, trees, snowflakes), christmas-geometric (tiers, baubles),
  christmas-artist (one tree), christmas-holiday-masterpiece (two
  snowflakes; an invisible `opacity: 0` "star border" deleted) and
  birthday-photo (the photo halo) replaced `opacity` with colours
  pre-blended against the sampled preview backdrop. Previews differ by
  at most 29/255 on 0.6% of pixels (overlap tints of stacked
  translucent shapes are gone); the winter-sky and geometric visual
  baselines were regenerated and eyeballed, 3 compile snapshots and the
  5 affected entries of the letter content / PDF alpha goldens were
  regenerated. birthday-balloons, metallic-ornaments and the other
  translucent templates flatten automatically and keep live alpha in
  `letter`/SVG/PNG. The `test_pdfx_preflight_all_templates.py` xfails
  are gone: every moo-a6 file preflights clean and `pdfimages -list`
  says `cmyk`. Guarded by `tests/unit/test_compiler_flatten.py`,
  `TestCmykImages` / `TestCmykRefusesLiveAlpha` in
  `test_cmyk_operators.py`, `TestFlattenWiring` / `TestPhotoOrnamentFront`
  / `TestPdfxSelfCheck` / `TestLiveAlphaOutsidePdfx` in
  `test_pdfx_moo_a6.py` and `TestTranslucencyOnPdfxTargets` in
  `test_cli.py`. **Template authors: translucency over anything but a
  containing solid fill is refused for POD targets** (to be noted in the
  #57 authoring guide).

- **2026-09-29 — ICC-managed sRGB → CMYK with a 300% ink cap and
  press black rules (expert-panel §P10 / D9, issue #70)**: `moo-a6`
  wrote DeviceCMYK from the naive "black removal" formula, and a RIP
  prints DeviceCMYK as-is (the OutputIntent only names the condition),
  so pure blue printed purple (100/100/0/0), the christmas-classic red
  brick-orange (0/87.5/87.5/20) and large blacks a washed-out K-only
  grey. `rgb_to_cmyk` is deleted (D17). New `color_management.
  CMYKConverter(profile_path=None, *, total_ink_limit=3.00,
  rich_black=(.6,.4,.4,1), rich_black_min_area_pt2=5184)`:
  `convert(r, g, b, *, role="fill"|"stroke"|"text", area_pt2=None)`
  sends pure black text/strokes to `0 0 0 1`, a pure-black fill whose
  bbox is ≥ 1 in² to rich black and a smaller or area-less fill to K-only;
  every other colour is quantised to 8 bits and converted by one
  LittleCMS transform (Pillow `ImageCms`, sRGB → bundled GRACoL2013,
  relative colorimetric + BPC; `lru_cache` per triplet), then capped: if
  C+M+Y+K > limit, C/M/Y scale by `(limit − K)/(C+M+Y)` and K stays.
  `convert_image(img)` (the #71 seam) applies transform + cap per pixel,
  honours an embedded `icc_profile` and returns mode `CMYK`; black rules
  don't apply to rasters. A missing profile raises
  `ICCProfileNotFoundError`, an unreadable or non-CMYK one `ValueError`
  (D4, no naive fallback). `IRReportLabRenderer(color_space="cmyk")`
  shares one process-wide converter (Pillow's `ImageCmsTransform.apply`
  re-serialises the 3.4 MB output profile on every call, ~12 ms, so the
  memo must outlive a single panel); `_set_fill` takes `role` /
  `area_pt2` (`_draw_shape` passes the `_shape_bbox` area, paths
  `None`), `_draw_text` passes `role="text"`, `_set_stroke` and fold
  lines `role="stroke"`, and the gradient / pattern helpers share
  `_rl_color` (gradient stops and the pattern background carry the
  bbox area; pattern tiles count as small). `_draw_image` and alpha are
  untouched (#71). Result: classic front bg `0 .988 .925 .122 k`, blue
  100/85.5/0/0, `#0A0A0A` 77.3/69.5/59.0/94.1 (TAC exactly 300). The
  sRGB `letter` path is byte-identical: its content streams match
  `tests/integration/__golden__/letter_content_sha256.json`, captured
  before the change (regenerate only on purpose with
  `HOLIDAY_CARD_REGEN_LETTER_CONTENT_GOLDEN=1`). Snapshots and visual
  baselines unchanged. Guarded by `tests/unit/test_color_management.py`
  (the issue's ±2-point table, a 9×9×9 TAC grid, roles and the 5184 pt²
  boundary, profile errors, `convert_image` with a Display-P3 tag),
  `tests/integration/test_cmyk_operators.py` (per-role operators,
  gradient `C0`, pattern tiles, fold line, TAC ≤ 3.0 for every `k`/`K`
  in all 21 templates' moo-a6 output, the sRGB golden) and
  `TestPdfxMooA6::test_front_background_is_icc_converted`.

- **2026-09-29 — PDF/X-1a: embedded initial font, correct Info/XMP
  identification, and a rule preflight gated in CI (expert-panel §P9 /
  D11, issue #69)**: (1) `IRReportLabRenderer` created its canvas with
  ReportLab's default initial font, base-14 Helvetica, which it never
  embeds, so every page of every PDF (sRGB and CMYK) opened with `/F1 12
  Tf` on an unembedded font. The canvas now passes `initialFontName=
  resolve_font_id("Helvetica")` (LiberationSans); `pdffonts` shows
  `emb yes` on every row. (2) `apply_pdfx1a` writes `/Info
  /GTS_PDFXVersion` and `/GTS_PDFXConformance` = `PDF/X-1a:2003`; the
  XMP `pdfx:GTS_PDFXVersion` is `PDF/X-1a:2003` (ISO 15930-4; it said the
  2001 identifier `PDF/X-1:2001` and the old test enforced that) and gains
  `xmp:CreateDate` / `ModifyDate` / `MetadataDate` converted from the Info
  `D:` dates. The OutputIntent says `/OutputConditionIdentifier
  (CGATS21-2-CRPC6)` and `/OutputCondition (GRACoL 2013, CRPC6 — CGATS
  21-2)`, matching the bundled profile (was `CGATS TR 006`). (3) New
  `renderers/pdfx_preflight.py`: `preflight_pdfx1a(path) ->
  list[PreflightViolation(rule, page, detail)]` checks header 1.4, `/ID`,
  no `/Encrypt`, Info keys + `Trapped` + `GTS_PDFXVersion`, XMP ↔ Info
  equality, exactly one `/GTS_PDFX` OutputIntent with an `N=4` profile,
  MediaBox ⊇ BleedBox ⊇ TrimBox ⊇ ArtBox, embedded fonts (Form XObjects,
  tiling patterns and Type 0 descendants included), transparency
  (`/ca`/`/CA` < 1, `/BM`, `/SMask`, image `/SMask`, transparency
  groups), RGB-family colour spaces (DeviceRGB / CalRGB / ICCBased / Lab)
  in content operators, images and shadings, and JavaScript / JPX /
  transfer functions. It reports; it never raises, and the generator does
  not call it yet (#71 wires it in). (4) New CI job `pdfx-preflight`
  (ubuntu + `poppler-utils` + `ghostscript`) runs `pytest -m pdfx` with
  `HOLIDAY_CARD_REQUIRE_PREFLIGHT_TOOLS=1`, which turns a missing tool
  into a failure (elsewhere those tests skip); `build` needs it. The new
  `pdfx` marker covers `tests/unit/test_pdfx_preflight.py` (one hand-built
  PDF per rule, mutated from a clean CMYK render),
  `test_pdfx_moo_a6.py` and `tests/integration/
  test_pdfx_preflight_all_templates.py` (moo-a6 for all 21 templates:
  font / metadata / box rules clean, `pdffonts` all `emb yes`, `gs
  -sDEVICE=inkcov` 4 values per page, plus the default `letter` PDF's
  fonts). `transparency.*` is a strict xfail for 13 templates and
  `colorspace.rgb_image` for the 5 photo templates; #71 trims
  `TRANSPARENCY_TEMPLATES` / `RGB_IMAGE_TEMPLATES` as it fixes them.
  D11 was already amended (veraPDF has no PDF/X profile). Removing
  `initialFontName` turns 52 `pdfx` tests red. Snapshots and visual
  baselines unchanged.
- **2026-09-29 — Cross-backend conformance suite + capability matrix
  (expert-panel §P12 / D12, issue #67)**: New `tests/conformance/` (no
  `__init__.py`). `cases.py` holds 37 frozen `Case`s, each a 144×144 pt
  page (bleed 0, except `page_bleed_background`) built straight from
  `render_ir` types that exercises one feature: fills, strokes, dash
  arrays on a line, gradients, the four patterns, clips, group
  rotate/scale/opacity, alpha, Lato/Cormorant text, JPEG images, fold
  line and bleed. `test_conformance.py` renders every case through SVG
  (the oracle, rasterized by `resvg-py` with `skip_system_fonts=True` +
  the bundled fonts) and through PDF (rasterized by `pypdfium2`) and PNG,
  all at 144 DPI, and applies `capabilities.CAPABILITIES[case][backend]`:
  `match` must be within tolerance, `raises` must raise
  `NotImplementedError`, and `known_diff` must be **outside** tolerance,
  so fixing the bug fails the test until the matrix is flipped (explicit
  strict-xfail). Tolerances are in `conftest.py`: a pixel mismatches at a
  channel delta > 48; `match` means mismatch ratio ≤ 1.0% (PDF) / 2.0%
  (PNG, no AA until #77) **and** a mean ink colour within 48 per channel.
  The ink check exists because a 0.5 pt fold line is 0.35% of the page, so
  a ratio alone missed an inverted fold-line colour. Text cases compare
  the ink bbox (±3 px per edge) plus the mean ink colour. Drift guards:
  every case has both backends, no orphans, every `known_diff` names an
  owner. `docs/conformance-matrix.md` must equal `render_markdown(
  CAPABILITIES)`; regenerate with `python -m tests.conformance.capabilities
  > docs/conformance-matrix.md`. Observed matrix: everything `match`
  except `stroke_rect_6pt` PNG (#77), `pattern_stripes` PDF and
  `pattern_grid` / `pattern_checkerboard` on both (#74), `group_scale_pivot`
  PDF (#72; PNG raises), `text_curated_family` (#76: the SVG oracle draws
  nothing for `font-family="Cormorant"`; `conftest` points every resvg
  generic family at a sentinel name so an unmatched family draws nothing on
  every host, because resvg's default fallback resolved on Linux but not
  macOS), and `group_opacity` (both
  raise). `pattern_dots` and `pattern_stripes` PNG match with this
  fixture; PNG dots sit at 1.98% of the 2.0% limit. Dev deps:
  `pypdfium2` and `resvg-py` added (wheels only, no system packages, so
  CI is unchanged); the unused `pdf2image` is gone. The suite adds 80
  tests and ~1 s.

- **2026-09-29 — PNG backend honours clips, dashes and text alpha, or
  raises (expert-panel §P6 / §P5 / D4, issue #61)**: `preview` uses
  `PNGRenderer`, which silently rendered a different card than PDF/SVG.
  (1) `BeginClip` only pushed a geometry that `_draw_image` alone read,
  and nested clips were unioned. Now `_begin_clip` builds a canvas-sized
  "L" mask (`_geom_mask`: rect / rounded rect / circle / ellipse /
  polygon / path) intersected (`ImageChops.multiply`) with the enclosing
  mask at the same group level; `_clip_stack` holds `(level, mask)`,
  where level counts open non-identity groups. `DrawShape`, `DrawText`,
  `DrawImage` and `DrawFoldLine` under a mask draw on a transparent
  layer (`_draw_in_layer`) and `_composite` through it; `_end_group`
  composites the rotated overlay through the parent level's mask, so a
  clip opened outside a rotated group still applies. `PolylineGeom`
  clips raise `NotImplementedError` at `BeginClip`. `_stamp_clip_geom`
  and `_draw_shape_with_alpha_compositing` are gone. (2) `Stroke.dash`
  was never read. `_stroke_outline` flattens the outline
  (`_outline_polylines`; circles/ellipses ≥ 64 samples, paths via the new
  `_flatten_path`) and module-level `_dash_runs` walks it with PDF/SVG
  semantics (odd arrays repeat, phase 0, restart per subpath); fold lines
  use the same walker. (3) Text ignored `opacity` and `color.a`; the
  effective alpha `opacity × color.a` is now applied by drawing opaque
  glyphs on a layer pre-filled with the text colour at alpha 0 (no dark
  fringes) and compositing. (4) `_get_font` resolves only through
  `font_registry.ttf_path_for` and raises `NotImplementedError` naming
  the font_id otherwise; `_FONT_FALLBACKS`, `_GENERIC_FALLBACKS` and
  `ImageFont.load_default()` are deleted. (5) Found while diffing every
  template before/after: gradient/pattern fills were pasted with
  themselves as mask, which also lowered the canvas alpha, so translucent
  gradients washed toward white at save time. They now `alpha_composite`.
  Only `christmas-winter-sky` (0.7/0.6 mountains) and
  `christmas-metallic-ornaments` (translucent back ornaments) changed;
  both visual baselines were regenerated and eyeballed; the other 19
  templates render pixel-identical. Guarded by
  `tests/integration/test_png_ir_fixtures.py` (importable module-level
  fixtures for #67: `CLIP_SHAPE_IN_CIRCLE`, `CLIP_TEXT_IN_RECT`,
  `CLIP_NESTED_INTERSECT`, `CLIP_IMAGE_NESTED`, `CLIP_UNDER_ROTATED_GROUP`,
  `CLIP_POLYLINE`, `DASHED_RECT`, `DASHED_CIRCLE`, `TEXT_OPACITY_OVER_RED`,
  `GRADIENT_OPACITY_OVER_RED`, `UNKNOWN_FONT`). AA, centred strokes,
  `line_cap` and gradient speed stay with #77.
- **2026-09-29 — ReportLab backend: correct quadratics, dash arrays and
  scoped alpha (expert-panel §P7 / D4 / D12, issue #62)**: Four latent
  `IRReportLabRenderer` bugs that shipped templates dodged only because the
  compiler drops colour alpha. (1) Quadratic path ops lifted from the
  control point (`path.contour` doesn't exist on ReportLab paths);
  `_geometry_to_path` now tracks the current point and subpath start
  (`close` returns to it) and a `quadratic` with no current point raises
  `ValueError`. (2) `_apply_fill` called `setFillAlpha(c.a)` and nothing
  reset it, so one translucent fill made every later fill and text
  translucent; `opacity` replaced the colour alpha instead of multiplying;
  stroke colour alpha, text colour alpha and `DrawImage.opacity` were
  ignored. Now each draw whose effective alpha is < 1 (fill / stroke / text
  = `opacity × color.a`, image = `opacity`) is wrapped in
  `saveState`/`restoreState` (q/Q); no manual "reset to 1.0". `opacity`
  scales both `/ca` and `/CA`. (3) `setDash(*dash)` emitted `[4 0]` (solid)
  for a 1-element dash and raised `TypeError` for 3–4 elements; it is now
  `setDash(list(dash), 0)`. (4) `BeginGroup.opacity != 1` raises
  `NotImplementedError` (needs a transparency-group XObject), matching the
  PNG backend. New `tests/integration/test_pdf_ir_fixtures.py`: importable
  module-level IR fixtures (`QUAD_*`, `FILL_ALPHA_NO_LEAK`,
  `ALPHA_MULTIPLY`, `STROKE_ALPHA`, `TEXT_ALPHA`, `IMAGE_OPACITY`,
  `DASH_ARRAYS`, `GROUP_OPACITY`) for the #67 parity matrix, an
  `ops_with_alpha` pikepdf walker that tracks (ca, CA) across q/Q/gs, and a
  golden (`__golden__/pdf_alpha_sequence.json`, captured before the fix)
  of the `(op, ca, CA)` sequence for every paint op in all 21 templates'
  letter PDFs. That golden is unchanged. Regenerate it only on purpose,
  with `HOLIDAY_CARD_REGEN_PDF_ALPHA_GOLDEN=1`. Group scale about the pivot
  is left to #72.
- **2026-09-29 — Text `font_style` and `rotation` are honoured (expert-panel
  §P3 / D4, issue #63)**: after #56 the loader passed `font_style` and
  `rotation` through, but the compiler still used `text.font_family`
  verbatim and never read `text.rotation`, so the 33 `font_style` uses
  across the shipped templates printed regular. `_compile_text` now resolves the font with
  `_styled_font_id(text)`, which calls `markdown.font_id_for_run` (Cormorant +
  italic → `Cormorant-Italic`; Inter/Caveat/Comfortaa/Lato-italic degrade
  to regular, the documented limitation). Wrapping and shrink-to-fit measure
  the **resolved** font, so the mothers-day greeting (Playfair italic, 30 pt)
  no longer shrinks to 29 pt. The letter path uses the element's style as
  the base for every part; a `--signature-font` override is used verbatim.
  Rich text (`--inside-message-md`) ignores `font_style`, because the
  Markdown run flags decide each run's style. It does not raise, since the CLI sets
  `rich_content` on template elements that carry a style. A non-zero text
  `rotation` wraps the element's `DrawText`s (plain, letter or rich) in
  `BeginGroup(Transform(pivot = text anchor, rotate_deg))` / `EndGroup`.
  `_compile_text` is now a thin wrapper over `_compile_text_body`. 10
  compile snapshots changed in `font_id` only, plus that one `size_pt`.
  13 visual baselines were regenerated and eyeballed: the headings are now
  visibly bold or italic. Guarded by `TestTextFontStyle`,
  `TestShippedTemplateFontStyles` (every styled element in all 21
  templates), `TestTextRotation` in `test_compiler.py` and
  `TestLetterFontStyle` in `test_compiler_letter.py`.
- **2026-09-29 — The `letter` target is a true 8.5×11 page with no bleed
  (expert-panel §P4 / D7, issue #59)**: `holiday-card create` wrote a
  630×810 pt page (8.75×11.25") because `PageGeometry.us_letter()`
  defaulted to 0.125" of bleed and `CropBox = MediaBox`. Home print
  dialogs "fit to page" that onto Letter, shrinking it ~2.9% and moving
  the fold lines off the physical centre. `PageGeometry.us_letter(bleed_in=
  0.0)` is now the default; the `letter` target uses `us_letter()`; the
  default `CompileContext` (`preview`, `--debug-emit-ir`, the visual
  suite, the scripts) therefore produces a bleed-free Letter page. The
  PDF declares MediaBox = CropBox = TrimBox = BleedBox = `[0 0 612 792]`
  and ArtBox `[18 18 594 774]`; SVG is `width="612" height="792"
  viewBox="0 0 612 792"`; `preview` at 144 DPI is 1224×1584. In
  `_bleed_extended_panel_rect` the extension is `min(panel-or-card bleed,
  geometry.bleed_in)`, so with a zero-bleed page no background rect
  leaves the trim (before, they sat at −9 pt off the page). POD output is
  unchanged: `per-panel-pdf` and `moo-a6` keep their 0.125" geometries and
  TrimBox stays inset 9 pt. `svg_backend._fmt` normalises IEEE `-0.0`
  to `0` (a zero bleed produced `viewBox="-0 -0 …"`). **Tests that
  exercise bleed must pass an explicit `PageGeometry.us_letter(bleed_in=
  0.125)`** (`test_compiler._NO_IMPOSE` does). All 16 compile snapshots
  (`BeginPage.bleed` 9 → 0, rects unextended) and all 21 visual baselines
  (630×810 → 612×792) were regenerated and eyeballed. Guarded by
  `TestLetterPageBoxes` in `test_full_generation.py` (pikepdf boxes + SVG
  canvas), `TestBeginPageBleedFields` / `TestBleedExtension` in
  `test_compiler.py` (default bleed 0, every rect inside the trim,
  explicit-bleed geometry still extends, cap at geometry bleed),
  `test_preview_command_at_144_dpi_is_letter_sized` in
  `test_png_backend.py`, and a `moo-a6` MediaBox ≠ TrimBox guard in
  `test_per_panel_output.py`.
- **2026-09-29 — Letter imposition is computed from the fold type; inside
  panels land on the correct pages (expert-panel §P4 / D6, issue #58)**:
  Every shipped template placed `inside_left` top-left and `inside_right`
  top-right of the sheet. After the two folds the top-right quadrant is the
  back of the cover leaf, i.e. the *left* inside page, so every printed
  card had its inside pages swapped (christmas-modern also printed its back
  cover and inside-right upside down). New `core/imposition.py`:
  `letter_slot(fold_type, position) -> PanelSlot` (front→BR, back→BL,
  inside_left→**TR** r180, inside_right→**TL** r180), `impose_letter(panels,
  fold_type)` (model_copy of x/y/rotation) and the public
  `panel_placements(card) -> dict[PanelPosition, PanelPlacement]` (trim-
  relative rects in points; #68 crops with it). `tri_fold` and `center`
  raise `UnsupportedFeatureError`, which moved to `core/errors.py` (the
  compiler re-exports it). `CompileContext.impose: bool = True`;
  `compile_card` runs `impose_letter` before the bleed-edge pass, and
  `per_panel.build_per_panel_context` sets `impose=False`, so per-panel /
  MOO output is unchanged. **Tests that hand-place a panel must pass
  `CompileContext(impose=False)`**; otherwise a `front` panel lands in BR.
  `half_fold` is now a documented legacy alias of the 4-up `quarter_fold`:
  both emit **two** fold marks and `templates --fold-type half_fold` lists
  the same 21 templates as `quarter_fold`. Panel coordinates are derived:
  `Panel.x`/`y` default to 0.0, all 210 panel-level `x`/`y`/`rotation`
  lines were deleted from the 21 templates (all now say `quarter_fold`),
  and the `init` scaffold defaults to `quarter_fold` with no panel
  coordinates. A YAML that still sets them and disagrees with the computed
  slot raises `TemplateLoadError` naming the panel, both values and "delete
  x/y/rotation; imposition is computed from fold_type"; matching values are
  accepted. All 16 compile snapshots and all 21 visual baselines were
  regenerated and eyeballed (inside message now in the top half, upside
  down, on the side its panel maps to). Guarded by
  `tests/unit/test_imposition.py` (parametrized slot table, a paper-fold
  simulator as an independent oracle, placements == compiled background
  rects, loader checks, every shipped template), the two PNG pixel tests in
  `test_png_backend.py` (quadrant colours + a corner marker proving the
  180° rotation) and the fold-mark tests in `test_compiler.py` /
  `test_per_panel_output.py`. Letter bleed / MediaBox stays with #59.
- **2026-09-28 — `CardRequest` + `build_card` / `plan_output`: one pipeline
  behind `create`, `preview` and `--debug-emit-ir` (expert-panel §P14 /
  D15, issue #78)**: `create()` was a 437-line Typer function that owned
  every precedence rule; `preview` accepted only `-m/-o/--dpi/--open`
  (so `preview --voice spare` was `No such option`) and `_emit_ir_debug`
  forwarded 5 of ~20 inputs. New `core/card_request.py`: `CardRequest`
  (frozen, `extra="forbid"`; every `create` input minus the debug switch)
  refuses the flag conflicts in a `model_validator` in `create()`'s old
  order (unknown `--export-for` → unknown `--voice` → `--inside-message`
  + `--inside-message-md` → the #60 combos → letter part + Markdown →
  unparsable Markdown); `--fold-type` and `--format` are parsed by field
  validators with the old messages. `build_card_with_report(request,
  templates_dir=) -> (Card, BuildReport)` owns theme check, template
  load, voice picks (occasion read from `Template.occasion`, so a
  template in the wrong directory no longer gets `generic` copy),
  `--blank-inside`, letter / Markdown / plain inside modes, fold-type fit
  and photos; `build_card(r)` is `[0]`. `plan_output(request, now=) ->
  OutputPlan(target, output_format, path)` owns format inference, the
  timestamped default path and the `-o` checks. Errors are plain
  `ValueError`s (no `Error:` prefix); `validation_message` /
  `unwrap_validation_error` pull the original error out of a
  `ValidationError`. `CardGenerator.create_card` now delegates to a new
  `create_card_from_template(template, ...)`; the unreachable
  `front_message` kwarg is gone from `create_card` / `create_and_generate`.
  CLI: `create` = build request → `plan_output` → `build_card_with_report`
  → `generate` → summary; `preview` takes every content option (shared
  `_*_OPTION` objects, same short flags) and its docstring no longer
  claims WYSIWYG for inputs it ignored; `--debug-emit-ir` is
  `compile_card(build_card(request))`. `_exit_for_card_error` is the one
  error→exit mapping for both commands (`ValidationError` / `ValueError`
  → exit 2). Deleted from the CLI: `_template_occasion`,
  `_resolve_output_format`, `_check_flag_combinations`, `_pick_voice_line`,
  `_check_fold_type_fits`, `_validate_output_path`. Every exit-2 message
  is byte-identical to before, including the quoted `Error: "unknown
  export target …"` (a `KeyError` `str()` artifact, kept on purpose).
  One ordering change: a missing `--inside-message-md` file is now
  reported before other flag conflicts, because the CLI reads the file
  before it builds the request. Guarded by `tests/unit/test_card_request.py`
  (one test per precedence rule, 69 tests), `TestPipelineParity` in
  `tests/unit/test_cli.py` (the three entry points build the same request;
  `--debug-emit-ir` output equals the compiled `build_card`) and
  `TestPreviewVoiceFlag` in `tests/integration/test_voice_flag.py`.
- **2026-09-26 — `create`/`preview` fail loud on ignored or contradictory
  inputs; global `--debug` (expert-panel §P5 / D4, issue #60)**: Each of
  these used to exit 0 with the input ignored, or exit 1 with a bare
  `KeyError`. They now print `Error: …`, write nothing, and exit 2: unknown
  `--theme` (lists the sorted ids; the generator's `except
  ThemeNotFoundError: pass` is gone), a `--voice` the occasion doesn't ship
  (lists `sentiments.available_voices()`, with no library path; the two
  yellow warnings are gone), `--blank-inside` with `--inside-message` or
  `--inside-message-md`, `--seed` without `--voice`, `--signature-font`
  without `--signature`, a `--fold-type` whose panel set the template
  lacks (half/quarter need front/back/inside_left/inside_right, tri needs
  left/center/right), and bad `-o` paths via `_validate_output_path` (an
  extension other than `.pdf`/`.svg`, with a `preview` hint for `.png`; a
  `--format` / extension clash; a file path for a per-panel target). A
  suffix-less `-o` still gets `.pdf`/`.svg`. In the compiler, `_compile_panel`
  raises `UnsupportedFeatureError` for a panel `background_image` or a
  text `font_file`. It raises `UnknownFontError(UnsupportedFeatureError)`
  (via `_require_known_font`, before any measurement) for a `font_family`
  or `signature_font_family` outside `font_registry.known_font_ids()`, and
  names `<template>/<panel>/<element>`. The CLI maps
  `UnsupportedFeatureError` to exit 2. The generator now compiles before it
  creates any output dir, and `preview` / `create` no longer `mkdir output/`
  up front, so a failed run leaves nothing behind. The new root `--debug`
  option (`HOLIDAY_CARD_DEBUG`) makes every command's catch-all re-raise
  the original error. Without it, the one-line message ends with `(re-run
  with --debug for a traceback)`. Guarded by `TestCreateFailsLoud` /
  `TestDebugFlag` in `tests/unit/test_cli.py`, `TestFailLoud` in
  `test_compiler.py`, `test_generators_theme.py`, and new cases in
  `test_sentiments.py` / `test_font_registry.py`.
- **2026-09-26 — `-i/--image` fills the template's photo slots; 1200 px
  placeholder; PNG upscales photos (expert-panel §P8/§P6, issue #65)**:
  `create -i me.jpg` used to fail on every template (`ImageElement
  requires explicit width and height`). The CLI built a height-less
  element and `_apply_images` stacked it on the front panel over the
  placeholder. `ImageElement` gained `slot: str | None` (pattern
  `^photo(-[2-9])?$`). New `core/generators.fill_photo_slots(card,
  photos)` puts the k-th photo on **every** element whose slot is `photo`
  (k=1) or `photo-k`. Only `source_path` changes; geometry, clip and
  z-order stay the template's, and unfilled slots keep the placeholder.
  Each photo is checked with `probe_image` first. Too many photos, or any
  photo on a template without slots, raises `PhotoSlotError(ValueError)`.
  The CLI maps that to exit 2 and lists `templates_with_photo_slots()`
  (new, in `core/templates.py`). `CardGenerator.create_card(photos=…)`
  replaces `images=`. `_apply_images`, the CLI's stacking code and
  `utils.validators.validate_image_format` (extension-only) are deleted
  (D17). Slots: photo-ornament `photo`…`photo-5` (cover, star, three
  circles), holiday-masterpiece `photo` + `photo-2`, the other three just
  `photo`. The 400 px `sample_photo.jpg` copies became a 1200×1200
  `placeholder-photo.jpg` (CC0), generated by
  `scripts/make_placeholder_photo.py`. A test checks that all three copies
  are byte-identical. `png_backend._draw_image` now resizes to the fit
  scale up **or** down. `thumbnail` never enlarged, so photos were drawn
  at 42% size at 300 DPI. `probe_image` accepts Pillow `MPO` (dual-camera
  phone JPEGs) as `jpeg` and says `image file not found` for a missing
  path. The 5 photo-template visual baselines were regenerated and
  eyeballed. Compile snapshots are unchanged. Still to do: `preview -i`
  (#78) and PPI warnings (#66). Guarded by
  `tests/unit/test_generators_photo_slots.py`, `tests/unit/test_templates.py`,
  `test_image_rendering.py::TestCLIImageFillsPhotoSlot` and
  `test_png_backend.py::test_png_upscales_small_photo_to_fill_rect`.
- **2026-09-26 — Template images resolve against the template file;
  image bytes are probed before embedding (security, expert-panel §P8 /
  D5, issue #64)**: A template or `Card` whose `image_elements[].source_path`
  named any readable file (e.g. `secret.env`) got it base64-embedded into
  SVG output as `data:application/octet-stream`. New `core/images.py`:
  `resolve_template_image_path` rejects absolute paths, `..` components and
  symlink escapes; `probe_image` requires Pillow to read a whole PNG or
  JPEG (never trusts the extension; truncated, GIF, text and >50 MP files
  refused) and raises `ImageSourceError`. `load_template_from_file`
  rewrites every image `source_path` to an absolute path inside the
  template's dir (failures → `TemplateLoadError`, so `validate` fails too).
  `_compile_image` refuses relative paths (**no cwd fallback**), probes the
  file and puts `format` / `width_px` / `height_px` on `ImageRef` (#66
  consumes the pixel size). The SVG backend takes its MIME type from
  `ImageRef.format`; the extension map and `octet-stream` fallback are
  gone. `sample_photo.jpg` (now `placeholder-photo.jpg`, #65) ships next to the christmas / birthday /
  mothers_day templates, and the six `contextlib.chdir(tests/fixtures)`
  workarounds in scripts and tests are deleted. CLI `create` / `preview`
  map `ImageSourceError` to `Error: …` + exit 2. The CI smoke job renders
  `christmas-photo-ornament` to SVG from the installed wheel. Visual
  baselines and compile snapshots unchanged. Guarded by
  `tests/unit/test_images.py`, `tests/unit/test_templates_images.py`,
  `test_svg_backend.py::test_svg_refuses_non_image_source` and
  `test_image_rendering.py::TestShippedPhotoTemplateFromAnyCwd`.
- **2026-09-26 — Templates load via `Template.model_validate` with
  `extra="forbid"` (expert-panel §P3 / D3, issue #56)**: The hand-written
  YAML parsers in `core/templates.py` (`_parse_template` / `_panel` /
  `_text_element` / `_fill_style` / `_shape_element`) re-listed model
  fields and silently dropped the rest: SVGPath `x`/`y`, text `z_index` /
  `font_style` / `rotation`, panel `border`, Line `rotation`/`fill`. Unknown
  shape or fill types, and malformed shapes, became skipped `None`s. They
  are deleted (D17). `load_template_from_file` now calls
  `Template.model_validate` and raises `TemplateLoadError` listing every
  Pydantic error `loc` (e.g. `panels.0.text_elements.0.colr: Extra inputs
  are not permitted`). **Every domain model reachable from `Template`, plus
  `Card`, has `model_config = ConfigDict(extra="forbid")`**. A typo'd key
  is an error, and so is an unknown kwarg in Python (several test fixtures
  had been passing a non-existent `Card(occasion=…)`). YAML aliases live on
  the models via `validation_alias=AliasChoices(...)`: `Line`
  `x1/y1/x2/y2`, `PatternFill` `angle` → `rotation`. `default_content` is
  gone. With `x`/`y` honoured, holly-wreath and holiday-masterpiece paths
  escaped their panels (authored values were leaf centres, not path
  origins), so the template coordinates were fixed. The model semantics
  stayed as they were. Compiled IR is byte-identical for the other 19
  templates. Regenerated: `compile_card__christmas-holly-wreath.json` and
  both visual baselines (eyeballed). Guarded by
  `tests/unit/test_templates_loading.py` and the new
  `test_shipped_svg_path_bbox_inside_panel` in `test_compiler_svg_path.py`.
  The compiler still ignores text `font_style` / `rotation` (#63) and
  `font_file` (#60).
- **2026-09-26 — A closed stdout pipe exits 0 quietly (issue #92)**:
  `holiday-card themes | grep -q x` used to print `Error listing themes:
  [Errno 32] Broken pipe` plus interpreter flush noise and exit 1, which
  broke `pipefail` pipelines at random. The root group is now `_CLIGroup`
  (`typer.Typer(cls=…)` in `cli/commands.py`). It catches
  `BrokenPipeError` from any command or subcommand, points fd 1 at
  `/dev/null` and exits 0. The eager `--version` callback uses the same
  helper, and the per-command re-raise clauses are now `except
  (typer.Exit, BrokenPipeError)`. **A new command with an `except
  Exception` block must let `BrokenPipeError` through the same way.** The
  CI smoke job uses `cli | grep -q` again. Guarded by
  `tests/integration/test_cli_broken_pipe.py`, which gives the subprocess
  a pipe whose read end is already closed, so EPIPE happens every time.
- **2026-09-26 — Ship bundled data inside the wheel + smoke the installed
  wheel (expert-panel §P1 / D1, issue #55)**: `pipx install holiday-card`
  was completely broken — the wheel carried only the ICC profile, so
  `templates`/`themes` printed nothing (exit 0) and `create` died on
  `No such file or directory: 'templates'`. `templates/`, `themes/`,
  `sentiments/`, `fonts/` and `assets/icc/` were `git mv`-ed to
  `src/holiday_card/data/` (plain package data, no `__init__.py`); the
  hatch `force-include` table and `assets/` are gone. New
  `core/data_paths.py` is the single resolver: `data_path(kind)` honors
  `HOLIDAY_CARD_{TEMPLATES,THEMES,SENTIMENTS}` (replaces the bundled dir;
  a non-directory raises `DataPathError`), else
  `importlib.resources.files("holiday_card") / "data" / kind`. No
  `__file__` walking, no cwd fallback. `get_*_dir`, `FONT_DIR` and
  `default_cmyk_icc_path` all delegate to it. `templates` / `themes`
  with no filter and an empty catalog now exit 1 with `Error: no …
  found in <dir> — installation is missing bundled data` on stderr
  (a filter that matches nothing still exits 0). Added root `LICENSE`
  (MIT) and `data/icc/NOTICE` (verbatim ICC-registry terms). CI now runs
  `lint/type-check/test → build → smoke`; `smoke` has **no checkout**:
  it installs `dist/*.whl` into a fresh venv, checks the wheel listing
  (≥21 templates, ≥70 sentiments, ≥25 TTFs, LICENSE, ICC), and runs the
  CLI from `$RUNNER_TEMP`. Its grep calls read from files, because
  `cli | grep -q` makes the CLI die of EPIPE under `pipefail`.
  `scripts/render_changed_templates.py` now treats
  `src/holiday_card/data/templates/**.yaml` as direct hits. Guarded by
  `tests/unit/test_data_paths.py` plus CLI / ICC / font-registry tests.

- **2026-09-26 — Locked dependencies with `uv.lock` + green mypy gate
  (expert-panel §P2, issue #54)**: Committed a universal `uv.lock`; CI's
  lint / type-check / test jobs and the render-cards + microsite
  workflows now install with `uv sync --locked` and run tools via
  `uv run`, and the lint job runs `uv lock --check`. Root cause of the red
  mypy job: on py3.12 the resolver pulled numpy 2.5.3 (via imagehash),
  whose stubs use the `type` statement that mypy rejects under
  `python_version = "3.11"`. Fixed with `[tool.uv] constraint-dependencies
  = ["numpy<2.5"]` and by running `type-check` on Python 3.11. Floors
  raised: `Pillow>=10.3.0` (CVE-2024-28219), `typer>=0.12` (dropped the
  removed `[all]` extra). New weekly `.github/workflows/latest-deps.yml`
  tests unpinned latest deps on 3.11 + 3.13 (allowed to go red; its
  `uv pip install --no-config` is required — without it `uv pip` inside
  the project silently applies the numpy constraint). Pre-commit
  ruff/mypy are now `repo: local` hooks running `uv run …`, so they use the
  locked versions. A `[dependency-groups] dev` group re-exports the `dev`
  extra so bare `uv run pytest` keeps the dev tools installed. Added
  `.python-version` (3.12). Guarded by `tests/unit/test_dependency_policy.py`
  (6 tests).
- **2026-06-02 — L3 AI imagery: authoring-time `ai-asset generate`
  (narrow, hard-railed form)**: Ships the panel's recommended shape from
  `consensus-ai-feature.md` — an **authoring-time** subcommand that bakes
  one image to disk and **never** runs in the render path (preserves the
  reproducibility moat). Four new `core/ai_*.py` modules, each TDD'd:
  `ai_rails.py` (the hard category gates: sympathy-class occasions refuse
  by default via `ai_imagery_allowed`; trademark / religious-iconography /
  likeness prompt blocklists; `evaluate_rails` returns `RailViolation`s),
  `ai_provenance.py` (`LicenseRecord` → `<asset>.license.yaml` sidecar +
  first-use consent gate under `$XDG_CONFIG_HOME/holiday-card/`),
  `ai_assets.py` (POD-aware `build_ai_request` — trim+2×bleed at 300 DPI;
  since #87 the bake is exact and only the API request is /16-rounded
  per `MODEL_SIZE_POLICIES`; `generate_ai_asset` orchestration over an **injectable**
  `ImageClient` Protocol, so the whole feature is testable with no network
  / no `OPENAI_API_KEY`; writes sRGB-tagged PNGs), and `ai_openai.py` (the
  only module importing `openai`, lazily, behind the `[ai]` extra).
  CLI: `holiday-card ai-asset generate` (typer sub-app) with `--subject`,
  `--reference` (required — image-reference mode is the default style
  anchor; `--unsafe-no-style-anchor` opts out), `--occasion` (drives the
  rails), `--export-for` (sizes the image), `--i-know-what-im-doing`
  (override that prints every rail reason first), and `--accept-ai-terms`
  (non-interactive consent). Refusals: rail-blocked → exit 5, consent
  missing → exit 3, missing key/extra → exit 4 (clean error, no
  traceback); since #142 a provider refusal → exit 6 and a
  provider / network error → exit 7 (a bad key / quota / region → 4,
  an invalid request → 2). New `[ai]` extra (`openai>=1.0`); project stays fully
  functional without it. README carries the panel's verbatim
  personal-use positioning paragraph. **What it deliberately does NOT
  do** (all out-of-scope per the consensus): render-time API calls,
  AI-generated copy, panel/photo replacement, free text-to-image as the
  default. 46 new tests (rails 23, provenance 7, assets 9, CLI 7).
  Completes L3; only the L2 illustrator commission (needs a human)
  remains of the panel's named leapfrogs.
- **2026-05-26 — Bold + BoldItalic TTFs for Cormorant + Playfair**:
  Mirrors the italic loop shipped in #48. The two editorial-serif
  families now have full Regular + Bold + Italic + BoldItalic statics
  in `fonts/curated/`. Static Bold and BoldItalic TTFs were instanced
  from the variable masters at weight=700 using
  `fontTools.varLib.instancer` (the upstream Google Fonts repos only
  ship variable masters; ReportLab and Pillow load variable fonts at
  the default weight, so instanced statics are what actually render
  bold). New `CURATED_FONTS` entries: `Cormorant-Bold`,
  `Cormorant-BoldItalic`, `PlayfairDisplay-Bold`,
  `PlayfairDisplay-BoldItalic`. Extends `markdown._BOLD_ITALIC_VARIANT`
  and `_KNOWN_BOLD_VARIANTS` / `_KNOWN_BOLD_ITALIC_VARIANTS`. After
  this PR all four style combinations (regular, bold, italic,
  bold-italic) render visibly on christmas-classic and the other
  9 templates that use Cormorant for inside body. Inter, Caveat,
  Comfortaa still fall back to regular for bold — documented
  limitation. Visual-eyeball confirmed: a Markdown letter on
  christmas-classic with mixed `*it*`, `**bold**`, `***both***`
  spans renders four distinct weights.
- **2026-05-25 — `--inside-message-md` / `--inside-message` panel
  targeting fix**: The three inside-content apply functions
  (`_apply_inside_message`, `apply_inside_letter`,
  `apply_inside_rich_content`) previously only searched the
  `inside_left` panel for a "message" target. But shipped templates
  put the "message" element on `inside_right` (10 of 21 templates do
  this; the rest ship no inside text). The functions hit the auto-add
  fallback every time and dropped a fresh `Lato` element onto
  `inside_left` — leaving the template's existing message untouched.
  Two simultaneous inside bodies (template's default in Cormorant +
  user's content in Lato) rendered on every `christmas-classic`
  Markdown letter. Extracted a shared `_find_or_add_inside_target`
  helper that searches `inside_right` first, then `inside_left`,
  then falls back to auto-add — and updated all three apply functions
  to use it. Side effect: italic Markdown now renders in the
  template's intended font (Cormorant-Italic on christmas-classic
  etc.) instead of falling back to Lato (which has no italic). 4 new
  integration tests pin the new targeting behavior.
- **2026-05-25 — Italic TTFs for Cormorant + Playfair (closes Italic
  Markdown loop)**: Bundles `CormorantGaramond-Italic.ttf` and
  `PlayfairDisplay-Italic.ttf` (both SIL OFL 1.1, variable-weight from
  Google Fonts) under `fonts/curated/`, registers them in `CURATED_FONTS`
  as `Cormorant-Italic` / `PlayfairDisplay-Italic`, extends
  `markdown._ITALIC_VARIANT` and `_KNOWN_ITALIC_VARIANTS` to route
  italic resolution to the new TTFs. Italic spans on the two editorial-
  serif families (the ones where italic matters most) now render real
  italic glyphs end-to-end. Inter/Caveat/Comfortaa/Lato still fall back
  to regular — same documented limitation as bold. 8 new tests
  (4 IR-level + 4 registry-coverage via the parametrized expected-set
  expansion).
- **2026-05-25 — Italic Markdown support**: `--inside-message-md` now
  parses `*italic*` and `_italic_` spans alongside the existing `**bold**`,
  plus `***bold-italic***` / `___bold-italic___` as a combined-style
  shorthand. `StyledRun` gained an `italic: bool` field. The parser
  shifted from a two-pass (bold-then-italic) regex to a recursive-
  descent walk over marker priority (triple > double > single) so
  ``***x***`` resolves cleanly without the lazy bold regex eating the
  inner asterisks. `font_id_for_run` accepts an `italic=` kwarg and
  maps to PDF base-14 conventions (`Helvetica-Oblique`, `Times-Italic`,
  `Courier-Oblique` for italic; `Helvetica-BoldOblique` and friends
  for bold-italic). Curated fonts fall back to regular — same
  documented limitation as bold — and lift once italic TTFs are added
  to `fonts/curated/`. Compiler's rich-text layout threads the italic
  flag through the wrapper (line-merge predicate now requires both
  bold AND italic to match). 14 new tests.
- **2026-05-25 — Sympathy-class occasion taxonomy (Leapfrog 2 finishing slice)**:
  Adds the four sympathy-class occasions the panel called out in
  `consensus-ai-feature.md:109` as a prerequisite for L3 AI imagery
  (so the hard-rails have categories to refuse against). New
  `OccasionType` values: `SYMPATHY`, `CONDOLENCE`, `MISCARRIAGE`,
  `PET_LOSS`. Each ships one restrained template (`sympathy-spare`,
  `condolence-spare`, `miscarriage-spare`, `pet-loss-spare`) plus
  a curated voice subset: `warm` + `spare` everywhere, plus
  `devotional` for sympathy/condolence only. Witty and irreverent
  are deliberately not shipped for any sympathy-class occasion
  ("absent rather than wrong"); devotional skipped for miscarriage
  and pet_loss because religious framing of those losses is delicate
  enough that absence beats getting it wrong. Asking the CLI for an
  un-shipped combination raises `SentimentNotFoundError` — fail
  loud. Sentiment lines are hand-curated, not v0/generated. 21 new
  templates shipping (was 17), 20 new sentiment files, +6 tests.
- **2026-05-11 — Leapfrog 5: template-gallery microsite + GitHub Pages**:
  Static site shipped: one HTML page per template (14 total) with a
  form that builds a copy-paste-ready `holiday-card create ...`
  command, plus a gallery index grouped by occasion. The Sandy
  persona escape hatch the panel endorsed in
  `docs/industry-review/consensus-general.md:163`. No backend, no
  WASM build, no in-browser PDF generation — the site is a showcase
  that surfaces the CLI's full surface (greeting / inside /
  --voice / --salutation / --signoff / --signature / --ps /
  --export-for moo-a6) as a friendly form. Vanilla CSS + JS only;
  no Jinja2, no Tailwind, no React. New file
  `scripts/build_microsite.py` generates the site; new workflow
  `.github/workflows/microsite.yml` deploys to GitHub Pages on
  every push to main. Photo-card templates render thumbnails via
  `contextlib.chdir(tests/fixtures)` so the bundled
  `sample_photo.jpg` is found at compile time. 10 new tests.
  Completes the panel's named leapfrogs 1, 2 (engineering side),
  4, and 5; only L3 (AI imagery — deferred per
  `consensus-ai-feature.md`) and the L2 illustrator commission
  (needs a human) remain.
- **2026-05-11 — SVGPath compiler support + 14/14 templates compile**:
  Closes the last two dead christmas templates (holly-wreath,
  holiday-masterpiece). `_compile_svg_path` parses the path's `d`
  string via `utils/svg_parser.SVGPathParser`, then converts each
  `PathCommand` to one or more `PathOp` entries via a new helper
  `_path_commands_to_ops` that resolves relative coords against the
  running cursor, reflects control points for `S` and `T`, applies
  `H`/`V` shortcuts, and re-emits `move` on `Z` close. `SVGPath` model
  gained `x` and `y` fields (panel-relative inches) — shipped
  templates were authoring them all along but the model was silently
  dropping the values. Arc commands (`A`/`a`) raise
  `UnsupportedFeatureError` (no shipped template uses arcs). PNG
  backend's `_draw_path` upgraded from "endpoints only" to proper
  cubic + quadratic Bezier sampling (16 samples per segment;
  `_sample_cubic_into` / `_sample_quadratic_into` helpers). 13 new
  tests covering path-op conversion (move/line/H/V/cubic/quadratic/
  smooth-reflection/close), `_compile_svg_path` (scale + offset +
  rotation wrap), arc rejection, and end-to-end compilation of both
  revived templates.
- **2026-05-11 — Gradient + pattern compiler support + 3 dead templates revived**:
  Linear gradients, radial gradients, and patterns (stripes / dots /
  grid / checkerboard) now render across all three backends. Compiler
  conversions in `core/compiler.py`: `_linear_gradient_to_paint` uses
  the shape bbox to resolve angle into absolute start/end points;
  `_radial_gradient_to_paint` interprets center/radius as panel-relative
  inches (matching the convention shipped templates actually use; the
  previous "fraction of shape" semantic was contradicted by every
  template). `RadialGradientFill` model validators loosened: center
  and radius are now panel-relative inches with no upper bound.
  SVG backend gained `_register_linear_gradient` / `_register_radial_gradient`
  / `_register_pattern` that emit `<linearGradient>` / `<radialGradient>`
  / `<pattern>` into `<defs>` and reference them via `url(#id)`. PDF
  backend gained `_draw_shape_with_complex_fill` that uses ReportLab's
  `canvas.linearGradient` / `radialGradient` inside a shape clip;
  patterns tile manually as filled shapes. CMYK mode propagates to
  gradient stops via `rgb_to_cmyk` so `--export-for moo-a6` produces
  CMYK gradients. PNG backend renders gradients via per-pixel
  interpolation into a shape-bbox-sized RGBA image, then composites
  through a shape mask (Pillow `ImageChops.multiply`). Three previously
  dead templates now compile: `christmas-winter-sky` (linear),
  `christmas-metallic-ornaments` (radial), `christmas-festive-stripes`
  (pattern). `christmas-holiday-masterpiece` still needs SVGPath
  support; `christmas-holly-wreath` is SVGPath-only. 12 new tests.
- **2026-05-11 — ImageElement compiler support + photo cards**:
  Photo cards render end-to-end through all three backends.
  `_compile_image` in `core/compiler.py` converts an `ImageElement`
  into an optional `BeginGroup` (for rotation, pivot-rotate around
  image center), optional `BeginClip` (for `clip_mask`), `DrawImage`,
  matching `EndClip` / `EndGroup`. Clip-mask types in scope:
  Circle / Rectangle / Ellipse / Star (Star → `PolygonGeom` with the
  same angular convention as `_compile_star`). Heart and SVGPath
  clip masks raise `UnsupportedFeatureError`. `image.effects`,
  `image.frame_style`, and auto-sizing (width/height = None) are
  also deferred. Backends: SVG backend gained a real `_draw_image`
  that base64-embeds the source image as a `data:image/*` URI; PNG
  backend gained `_draw_image` + clip masking via `PIL.ImageChops`
  multiplication; PDF backend already had drawImage. `templates.py`
  now parses `image_elements` from YAML (was silently dropping
  them — a latent bug that hid the photo-ornament template).
  17 new tests covering compiler IR shape, all three backend renderers,
  and pixel-correctness inside/outside the clip on PNG output.
  `christmas-photo-ornament` left out of `SUPPORTED_SNAPSHOT_TEMPLATES`
  because the snapshot would carry a machine-absolute resolved source
  path; pixel-correctness integration test covers it instead.
  Clears one of the L3 (AI imagery) prerequisites — the AI workflow's
  baked PNGs now have a working IR pipeline to render through.
- **2026-05-11 — Structured inside letter: salutation / signoff / signature / P.S. (Leapfrog 2, slice 4)**:
  Four new CLI flags (`--salutation`, `--signoff`, `--signature`, `--ps`)
  plus `--signature-font` for the handwritten-feel override. New
  `LetterContent` Pydantic model (`core/letter.py`, frozen) carries
  the five structured parts (salutation, body, signoff, signature,
  postscript). `TextElement.letter_content` is the new authoring
  surface; a model-level validator forbids it co-existing with
  `rich_content` (Markdown) since they're two different layout passes.
  Compiler emits per-part `DrawText` commands with conventional
  vertical gaps (`_LETTER_GAP_*` constants in `compiler.py`); P.S.
  renders at 85% of body size, signature accepts a font override.
  Letter parts compose freely with `--voice` / `--inside-message` /
  `--blank-inside` (those just supply the body); refuse the combo
  with `--inside-message-md` since Markdown has its own structure.
  Generator helper: `apply_inside_letter`. 33 new tests. Closes the
  engineering side of the panel's "first-class fields" item in
  `consensus-general.md:156`. Illustrator commission remains the
  outstanding piece of Leapfrog 2.
- **2026-05-10 — CMYK + ICC + PDF/X-1a:2003 (Leapfrog 1 complete)**:
  `--export-for moo-a6` now emits DeviceCMYK PDFs (k/K operators,
  no RGB), with the GRACoL2013_CRPC6 ICC profile embedded as the
  OutputIntent's `/DestOutputProfile`, an XMP metadata stream
  declaring PDF/X-1a:2003 (it wrongly said `GTS_PDFXVersion=
  "PDF/X-1:2001"` until #69), `/Info /Trapped` set to
  `/False`, and the PDF header forced to 1.4. Implementation:
  `core/color_management.py` (naive sRGB→CMYK conversion, replaced
  by the ICC `CMYKConverter` in #70, + ICC path resolution), `renderers/pdfx_postprocess.py` (pikepdf-based
  OutputIntent + XMP injection), `IRReportLabRenderer(color_space=
  "cmyk")` for the CMYK emission path. `ExportTarget` gained
  `color_space` + `pdfx` fields; the generator dispatches a
  CMYK-mode renderer and the post-processor when the target asks.
  New dependency: `pikepdf>=8.0`. Bundled asset:
  `assets/icc/GRACoL2013_CRPC6.icc` (3.4MB, ICC CGATS21 reference,
  freely redistributable). Color accuracy is deferred to the
  printer's RIP via the embedded OutputIntent — standard PDF/X-1a
  practice. 13 new tests in `tests/integration/test_pdfx_moo_a6.py`.
  Clears the prerequisite for AI-imagery Leapfrog 3.
- **2026-05-10 — GitHub Action: render-on-PR + sticky comment (Leapfrog 4, slice 2)**:
  New `.github/workflows/render-cards.yml` triggers on PRs touching
  templates/sentiments/fonts/themes/src. Detects affected templates
  via `scripts/render_changed_templates.py` (direct template change →
  just that template; indirect change → full shipping set), renders
  PNG previews at 144 DPI, uploads as a workflow artifact, and posts
  a sticky PR comment with the list and artifact link. Completes
  Leapfrog 4 alongside the Markdown mode in PR #26 — together they
  realize the panel's "cards-as-code identity" thesis.
- **2026-05-10 — Markdown mode for inside panel (Leapfrog 4, slice 1)**:
  New `--inside-message-md path/to/letter.md` flag turns the inside
  panel into a "Christmas letter" surface — paragraphs, **bold** spans,
  and hard line breaks render with proper paragraph spacing and
  bold-aware font fallback. Adds `core/markdown.py` (tiny parser, no
  new deps), `RichTextContent` field on `TextElement`, `_compile_rich_text`
  pass in the compiler, and `apply_inside_rich_content` on
  `CardGenerator`. Bold spans use the registered Bold variant (Lato-Bold
  today; other curated families are variable fonts and fall back to
  regular until additional weights are registered).
- **2026-05-10 — Panel-review cleanups bundle**: Four small items that
  had been on the list since the panel review (PR #19). (1) Gated
  `DrawFoldLine` behind `--with-fold-marks` / `--no-fold-marks` with
  per-target defaults (`letter` ON, per-panel OFF). (2) Renamed the
  six underscore-named christmas templates to use hyphens for
  filename/id consistency (`holly_wreath.yaml` → `holly-wreath.yaml`
  etc.). (3) Updated `_apply_front_message` and `_apply_inside_message`
  auto-add fallback to use `Lato` instead of `Helvetica`. (4) Rewrote
  the README around Tyler-the-engineer per Agreement 5.
- **2026-05-10 — Migrate 7 templates to curated fonts (Leapfrog 2, slice 3)**:
  Every shipped template now uses curated fonts intentionally rather than
  Liberation defaults. Pairings: christmas-classic (Playfair + Cormorant),
  christmas-geometric/-modern (Inter), christmas-artist (Caveat + Cormorant),
  birthday-balloons (Comfortaa + Caveat + Lato), hanukkah-menorah
  (Lato + Cormorant), generic-celebration (Inter + Lato), mothers-day
  (Playfair + Caveat + Lato). Zero Helvetica/Times-Roman references remain
  in `templates/`. Snapshots regenerated.
- **2026-05-10 — Curated font shipment (Leapfrog 2, slice 2)**: Six SIL OFL
  open-source fonts in `fonts/curated/` — Cormorant Garamond (editorial
  serif), Playfair Display (display serif), Lato (friendly sans, regular +
  bold), Inter (modern variable sans), Caveat (handwritten script),
  Comfortaa (rounded display). `font_registry` consults a `CURATED_FONTS`
  map alongside the Liberation default chain; `christmas-classic` is
  updated as a demonstration (PlayfairDisplay cover + Cormorant body).
  Existing templates referencing Helvetica/Times-Roman/Courier continue
  to work unchanged.
- **2026-05-10 — Sentiment library + `--voice` flag (Leapfrog 2, slice 1)**:
  Curated greeting copy organized as `sentiments/{occasion}/{voice}/{role}.yaml`
  for the five panel-recommended voices (warm, witty, spare, devotional,
  irreverent). New CLI flags `--voice`, `--blank-inside`, `--seed` resolve
  occasion + voice + role into a picked sentiment that fills front
  greeting and inside message slots not already set explicitly. Ships
  with a v0 starter content set (50 files, ~250 lines); intended to be
  replaced with hand-curated copy by an actual copywriter.
- **2026-05-10 — `--export-for` CLI flag + per-panel POD output**:
  Three named export targets — `letter` (default, today's behavior),
  `per-panel-pdf` (each panel as its own file at native trim + bleed),
  and `moo-a6` (each panel at true A6 with content uniformly scaled to
  fit). Adds `core/export_targets.py` (registry) and `core/per_panel.py`
  (panel-content scaling helpers). Lays the rails for CMYK / ICC /
  PDF/X-1a (next slice of Leapfrog 1). (Since #73, moo-a6 fills the trim
  and crops via one compiler scale group; the domain-level scaling
  helpers are gone.)
- **2026-05-10 — Bleed support + `PageGeometry` abstraction**: Backgrounds
  now extend past the trim edge by 0.125" (industry default) on edges that
  touch the page trim. `Card.bleed` and `Panel.bleed` configure it; the
  PDF declares distinct `MediaBox` / `TrimBox` / `BleedBox` / `ArtBox`;
  SVG `viewBox` and PNG canvas grow to include the bleed band. Lays the
  rails for `--export-for moo-a6` (Leapfrog 1) without shipping it yet.
  (Since #59 the default `letter` page carries no bleed; this
  behaviour now applies to the POD targets and to any explicit
  `PageGeometry` with `bleed_in > 0`.)
- **2026-05-10 — Wave 2 complete + v1.1.0 release**: IR seam
  (PRs #4-#10), three rendering backends (PRs #7/#11/#12), working
  `preview` command (PR #12), version bump + zero mypy errors + strict
  CI gates (PR #13). Net: 12 PRs, ~6,950 LOC removed, ~3,800 added.
- **2026-05 — Wave 1 DevEx audit (PR #1)**: Real CI on every push,
  `requirements.txt` deleted, 22 B904 + 10 null-deref bugs fixed.
- **2026-05 — Valentine deprecation (PR #8)**: Removed the 2026-02
  Valentine release (templates + decorative-element library) when
  porting to the IR proved non-trivial. The dead model code (HeartClipMask,
  etc.) has since been removed; no `HeartClipMask` exists in `src/`.
- **003-vector-graphics-and-decorative-elements** (specs/): Original
  spec for vector graphics. Decorative elements piece is no longer
  shipped (see Valentine deprecation).
- **001-holiday-card-generator** (specs/): Original spec.

