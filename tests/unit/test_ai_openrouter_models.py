"""The curated OpenRouter image-model allowlist (issue #148, spec §3 / O2 / O6).

Every entry pins one endpoint (``provider_tag``) and records exactly what
that endpoint advertises, so a request can be refused locally instead of
clamped. A bad entry fails at import (D4).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from datetime import date

import pytest

from holiday_card.core.ai_assets import RESOLUTION_LONG_EDGE_PX, aspect_ratio_value
from holiday_card.core.ai_openrouter_models import (
    OPENROUTER_IMAGE_MODELS,
    OpenRouterModel,
    OpenRouterPrice,
    openrouter_model,
)

CURATED = {
    "google/gemini-3-pro-image",
    "google/gemini-3.1-flash-image",
    "black-forest-labs/flux.2-pro",
    "bytedance-seed/seedream-4.5",
    "openai/gpt-image-2",
}

ENTRIES = sorted(OPENROUTER_IMAGE_MODELS.values(), key=lambda e: e.id)


def _base() -> OpenRouterModel:
    return OPENROUTER_IMAGE_MODELS["google/gemini-3-pro-image"]


class TestAllowlist:
    def test_keys_are_the_entry_ids(self) -> None:
        assert all(key == entry.id for key, entry in OPENROUTER_IMAGE_MODELS.items())

    def test_exactly_the_curated_models(self) -> None:
        assert set(OPENROUTER_IMAGE_MODELS) == CURATED

    def test_the_mapping_is_read_only(self) -> None:
        with pytest.raises(TypeError):
            OPENROUTER_IMAGE_MODELS["x/y"] = _base()  # type: ignore[index]

    @pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.id)
    def test_every_aspect_ratio_parses_and_none_is_auto(self, entry: OpenRouterModel) -> None:
        assert entry.aspect_ratios
        assert "auto" not in entry.aspect_ratios
        assert all(aspect_ratio_value(r) > 0 for r in entry.aspect_ratios)

    @pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.id)
    def test_resolutions_are_known_tiers(self, entry: OpenRouterModel) -> None:
        assert set(entry.resolutions) <= set(RESOLUTION_LONG_EDGE_PX)

    @pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.id)
    def test_reference_range_is_sane(self, entry: OpenRouterModel) -> None:
        assert 0 <= entry.input_refs_min <= entry.input_refs_max <= 16

    @pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.id)
    def test_pricing_is_present(self, entry: OpenRouterModel) -> None:
        assert entry.pricing
        assert all(p.cost_usd >= 0 for p in entry.pricing)

    @pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.id)
    def test_terms_url_is_the_vendors(self, entry: OpenRouterModel) -> None:
        assert entry.upstream_terms_url.startswith("https://")
        assert "openrouter.ai" not in entry.upstream_terms_url

    @pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.id)
    def test_snapshot_date_is_iso(self, entry: OpenRouterModel) -> None:
        date.fromisoformat(entry.snapshot_date)


class TestPinnedEndpointFacts:
    def test_gemini_pro_is_pinned_to_ai_studio_for_4k(self) -> None:
        entry = openrouter_model("google/gemini-3-pro-image")
        assert entry.provider_tag == "google-ai-studio/global"
        assert "4K" in entry.resolutions

    def test_gemini_flash_tag_has_no_global_suffix(self) -> None:
        assert openrouter_model("google/gemini-3.1-flash-image").provider_tag == "google-ai-studio"

    @pytest.mark.parametrize("model", ["black-forest-labs/flux.2-pro", "bytedance-seed/seedream-4.5"])
    def test_seeded_models(self, model: str) -> None:
        assert openrouter_model(model).seed is True

    @pytest.mark.parametrize(
        "model", ["google/gemini-3-pro-image", "google/gemini-3.1-flash-image", "openai/gpt-image-2"]
    )
    def test_unseeded_models(self, model: str) -> None:
        assert openrouter_model(model).seed is False

    def test_gpt_image_2_has_no_transparent_background(self) -> None:
        assert openrouter_model("openai/gpt-image-2").background_transparent is False

    def test_flux_advertises_output_formats_and_no_resolution(self) -> None:
        entry = openrouter_model("black-forest-labs/flux.2-pro")
        assert entry.output_formats == ("png", "jpeg")
        assert entry.resolutions == ()

    def test_gpt_image_2_keeps_every_price_row(self) -> None:
        billables = {p.billable for p in openrouter_model("openai/gpt-image-2").pricing}
        assert billables == {"input_image", "input_text", "output_image"}


class TestUnknownModel:
    def test_unknown_id_lists_every_curated_id(self) -> None:
        with pytest.raises(ValueError, match="unknown OpenRouter image model 'nope/nope'") as err:
            openrouter_model("nope/nope")
        assert all(model_id in str(err.value) for model_id in CURATED)
        assert "only reviewed models are allowed" in str(err.value)


class TestPostInitRefusals:
    @pytest.mark.parametrize(
        ("changes", "field"),
        [
            ({"aspect_ratios": ("3:4", "auto")}, "aspect_ratios"),
            ({"aspect_ratios": ("3:4", "x:y")}, "aspect_ratios"),
            ({"aspect_ratios": ()}, "aspect_ratios"),
            ({"resolutions": ("1K", "8K")}, "resolutions"),
            ({"input_refs_min": 3, "input_refs_max": 2}, "input_refs"),
            ({"input_refs_min": -1}, "input_refs"),
            ({"input_refs_max": 17}, "input_refs"),
            ({"pricing": ()}, "pricing"),
            (
                {"pricing": (OpenRouterPrice("output_image", "image", -0.01),)},
                "pricing",
            ),
            ({"snapshot_date": "30/09/2026"}, "snapshot_date"),
            ({"upstream_terms_url": "TODO-REVIEW"}, "upstream_terms_url"),
            ({"upstream_terms_url": "http://example.com/terms"}, "upstream_terms_url"),
            ({"upstream_terms_url": "https://openrouter.ai/terms"}, "upstream_terms_url"),
            ({"upstream_terms_url": "https://www.openrouter.ai/terms"}, "upstream_terms_url"),
            ({"provider_tag": ""}, "provider_tag"),
            # --max-cost upper bounds (#151); the base entry records tokens.
            ({"max_output_megapixels": 0.0}, "max_output_megapixels"),
            ({"max_output_megapixels": float("nan")}, "max_output_megapixels"),
            ({"output_image_tokens": {"512": 747}}, "output_image_tokens"),
            ({"output_image_tokens": {"default": 1120}}, "output_image_tokens"),
            ({"output_image_tokens": {}}, "output_image_tokens"),
            ({"output_image_tokens": {"1K": 0}}, "output_image_tokens"),
            ({"input_image_tokens": 0}, "input_image_tokens"),
            ({"bound_source": None}, "bound_source"),
            ({"bound_source": "https://ai.google.dev/pricing"}, "bound_source"),
            ({"bound_source": "2026-09-30 Google said so"}, "bound_source"),
            ({"output_image_tokens": None, "input_image_tokens": None}, "bound_source"),
        ],
    )
    def test_bad_entry_is_refused_naming_id_and_field(
        self, changes: dict[str, object], field: str
    ) -> None:
        with pytest.raises(ValueError, match=field) as err:
            replace(_base(), **changes)  # type: ignore[arg-type]
        assert "google/gemini-3-pro-image" in str(err.value)


def test_import_loads_only_the_standard_library() -> None:
    # `import holiday_card` itself loads pydantic (the package __init__), so
    # the check is on what importing the allowlist *adds*.
    code = (
        "import sys\n"
        "import holiday_card\n"
        "before = set(sys.modules)\n"
        "import holiday_card.core.ai_openrouter_models\n"
        "added = set(sys.modules) - before\n"
        "third = sorted(m for m in added if m.split('.')[0] not in sys.stdlib_module_names\n"
        "               and not m.startswith('holiday_card'))\n"
        "assert not third, third\n"
        "bad = [m for m in ('PIL', 'pydantic', 'openai', 'urllib.request') if m in added]\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


class TestUpstreamVendor:
    @pytest.mark.parametrize("entry", list(OPENROUTER_IMAGE_MODELS.values()), ids=lambda e: e.id)
    def test_every_pinned_route_has_a_vendor_name(self, entry: OpenRouterModel) -> None:
        from holiday_card.core.ai_openrouter_models import upstream_vendor_name

        assert upstream_vendor_name(entry).strip()

    def test_names(self) -> None:
        from holiday_card.core.ai_openrouter_models import upstream_vendor_name

        names = {e.id: upstream_vendor_name(e) for e in OPENROUTER_IMAGE_MODELS.values()}
        assert names["google/gemini-3-pro-image"] == "Google (AI Studio)"
        assert names["black-forest-labs/flux.2-pro"] == "Black Forest Labs"
