"""``list_models``: the curated image models, per provider, from checked-in tables (#152)."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from datetime import date

import pytest

from holiday_card.core import ai_assets, ai_providers
from holiday_card.core.ai_assets import MODEL_SIZE_POLICIES, MODEL_SIZE_POLICIES_VERIFIED
from holiday_card.core.ai_openrouter_models import (
    OPENROUTER_IMAGE_MODELS,
    OpenRouterPrice,
    upstream_vendor_name,
)
from holiday_card.core.ai_providers import (
    MODELS_SCHEMA_VERSION,
    PROVIDERS,
    AIProvider,
    ModelListing,
    PixelSizeRule,
    known_models,
    list_models,
    model_listing_payload,
)

FIXED_RULE = PixelSizeRule(
    fixed=((1024, 1024), (1536, 1024), (1024, 1536)),
    multiple=None,
    max_edge=None,
    max_aspect=None,
    min_pixels=None,
    max_pixels=None,
)
FLEXIBLE_RULE = PixelSizeRule(
    fixed=None,
    multiple=16,
    max_edge=3840,
    max_aspect=3.0,
    min_pixels=655_360,
    max_pixels=8_294_400,
)


def _row(provider: AIProvider, model_id: str) -> ModelListing:
    (row,) = [r for r in list_models(provider) if r.id == model_id]
    return row


def test_one_row_per_curated_model_sorted_by_provider_then_id() -> None:
    rows = list_models()
    assert len(rows) == len(MODEL_SIZE_POLICIES) + len(OPENROUTER_IMAGE_MODELS)
    keys = [(r.provider.value, r.id) for r in rows]
    assert keys == sorted(keys)


@pytest.mark.parametrize("provider", list(AIProvider))
def test_exactly_one_default_per_provider_and_it_is_the_registry_default(
    provider: AIProvider,
) -> None:
    defaults = [r.id for r in list_models(provider) if r.default]
    assert defaults == [PROVIDERS[provider].default_model]


@pytest.mark.parametrize("provider", list(AIProvider))
def test_a_provider_filter_lists_exactly_the_ids_generate_accepts(provider: AIProvider) -> None:
    rows = list_models(provider)
    assert rows, "every provider has at least one row"
    assert {r.provider for r in rows} == {provider}
    assert [r.id for r in rows] == list(known_models(provider))


@pytest.mark.parametrize("model_id", sorted(OPENROUTER_IMAGE_MODELS))
def test_openrouter_row_maps_its_allowlist_entry(model_id: str) -> None:
    entry = OPENROUTER_IMAGE_MODELS[model_id]
    row = _row(AIProvider.OPENROUTER, model_id)
    assert row == ModelListing(
        provider=AIProvider.OPENROUTER,
        id=entry.id,
        default=model_id == PROVIDERS[AIProvider.OPENROUTER].default_model,
        route=entry.provider_tag,
        upstream=upstream_vendor_name(entry),
        input_references=(entry.input_refs_min, entry.input_refs_max),
        aspect_ratios=entry.aspect_ratios,
        resolutions=entry.resolutions or None,
        pixel_sizes=None,
        seed=entry.seed,
        output_formats=entry.output_formats,
        pricing=entry.pricing,
        terms_urls=(*PROVIDERS[AIProvider.OPENROUTER].policy_urls, entry.upstream_terms_url),
        snapshot_date=entry.snapshot_date,
    )


def test_an_endpoint_without_tiers_lists_none_not_an_empty_tuple() -> None:
    assert _row(AIProvider.OPENROUTER, "black-forest-labs/flux.2-pro").resolutions is None
    assert _row(AIProvider.OPENROUTER, "google/gemini-3-pro-image").resolutions == ("1K", "2K", "4K")


@pytest.mark.parametrize(
    ("model_id", "rule"),
    [
        ("gpt-image-1", FIXED_RULE),
        ("gpt-image-1-mini", FIXED_RULE),
        ("gpt-image-1.5", FIXED_RULE),
        ("gpt-image-2", FLEXIBLE_RULE),
        ("gpt-image-2.5-sunburst", FLEXIBLE_RULE),
        ("gpt-image-2.5-flare", FLEXIBLE_RULE),
    ],
)
def test_openai_row_carries_its_size_policy(model_id: str, rule: PixelSizeRule) -> None:
    assert _row(AIProvider.OPENAI, model_id) == ModelListing(
        provider=AIProvider.OPENAI,
        id=model_id,
        default=model_id == "gpt-image-2",
        route="openai",
        upstream="OpenAI",
        input_references=(0, 1),
        aspect_ratios=None,
        resolutions=None,
        pixel_sizes=rule,
        seed=False,
        output_formats=("png",),
        pricing=(),
        terms_urls=PROVIDERS[AIProvider.OPENAI].policy_urls,
        snapshot_date=MODEL_SIZE_POLICIES_VERIFIED,
    )


def test_openai_rows_cover_every_size_policy() -> None:
    assert {r.id for r in list_models(AIProvider.OPENAI)} == set(MODEL_SIZE_POLICIES)


def test_a_recorded_openai_max_price_is_listed_as_one_output_image_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    priced = replace(MODEL_SIZE_POLICIES["gpt-image-2"], max_price_usd=0.25)
    monkeypatch.setitem(ai_assets.MODEL_SIZE_POLICIES, "gpt-image-2", priced)
    assert _row(AIProvider.OPENAI, "gpt-image-2").pricing == (
        OpenRouterPrice("output_image", "image", 0.25),
    )


def test_openai_policies_verified_date_is_iso() -> None:
    assert MODEL_SIZE_POLICIES_VERIFIED == "2026-09-29"


def test_no_row_lists_auto_as_an_aspect_ratio() -> None:
    assert all("auto" not in (r.aspect_ratios or ()) for r in list_models())


def test_every_row_has_https_terms_and_an_iso_snapshot_date() -> None:
    for row in list_models():
        assert row.terms_urls, row.id
        assert all(url.startswith("https://") for url in row.terms_urls), row.id
        date.fromisoformat(row.snapshot_date)
        assert row.upstream, row.id


# --- payload (the JSON / YAML document) ----------------------------------------------


def test_payload_is_versioned_and_plain_json_types() -> None:
    payload = model_listing_payload(list_models(AIProvider.OPENROUTER))
    assert MODELS_SCHEMA_VERSION == 1
    assert list(payload) == ["schema_version", "models"]
    assert payload["schema_version"] == 1
    first = payload["models"][0]
    assert first == {
        "provider": "openrouter",
        "id": "black-forest-labs/flux.2-pro",
        "default": False,
        "route": "black-forest-labs",
        "upstream": "Black Forest Labs",
        "input_references": {"min": 0, "max": 8},
        "aspect_ratios": ["1:1", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16", "21:9"],
        "resolutions": None,
        "pixel_sizes": None,
        "seed": True,
        "output_formats": ["png", "jpeg"],
        "pricing": [{"billable": "output_image", "unit": "megapixel", "usd": 0.03}],
        "terms_urls": [
            *PROVIDERS[AIProvider.OPENROUTER].policy_urls,
            "https://bfl.ai/legal/developer-terms-of-service",
        ],
        "snapshot_date": "2026-09-30",
    }


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        (
            "gpt-image-1",
            {"fixed": [[1024, 1024], [1536, 1024], [1024, 1536]], "multiple": None,
             "max_edge": None, "max_aspect": None, "min_pixels": None, "max_pixels": None},
        ),
        (
            "gpt-image-2",
            {"fixed": None, "multiple": 16, "max_edge": 3840, "max_aspect": 3.0,
             "min_pixels": 655360, "max_pixels": 8294400},
        ),
    ],
)  # fmt: skip
def test_payload_pixel_sizes_of_openai_rows(model_id: str, expected: dict[str, object]) -> None:
    payload = model_listing_payload([_row(AIProvider.OPENAI, model_id)])
    (row,) = payload["models"]
    assert row["pixel_sizes"] == expected
    assert row["aspect_ratios"] is None
    assert row["resolutions"] is None


def test_listing_loads_no_adapter_and_no_http_client() -> None:
    # OpenAI rows read ai_assets.MODEL_SIZE_POLICIES (as known_models does), which loads Pillow.
    code = (
        "import sys\n"
        "import holiday_card\n"
        "before = set(sys.modules)\n"
        "from holiday_card.core.ai_providers import list_models, model_listing_payload\n"
        "model_listing_payload(list_models())\n"
        "added = set(sys.modules) - before\n"
        "bad = [m for m in ('openai', 'urllib.request', 'holiday_card.core.ai_openrouter',\n"
        "                   'holiday_card.core.ai_openai') if m in added]\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=120)


def test_module_exports() -> None:
    assert {"ModelListing", "PixelSizeRule", "list_models", "model_listing_payload",
            "MODELS_SCHEMA_VERSION"} <= set(ai_providers.__all__)  # fmt: skip
    assert "MODEL_SIZE_POLICIES_VERIFIED" in ai_assets.__all__
