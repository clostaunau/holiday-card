"""The AI provider registry and client factory (issue #146).

No network and no API key: the ``openai`` module is replaced in
``sys.modules`` wherever a client is constructed.
"""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from holiday_card.core import ai_openai
from holiday_card.core.ai_assets import MODEL_SIZE_POLICIES
from holiday_card.core.ai_openai import OpenAIImageClient
from holiday_card.core.ai_providers import (
    PROVIDERS,
    AIDependencyError,
    AIProvider,
    UnknownModelError,
    known_models,
    make_image_client,
    policy_urls_for,
    reference_limits,
    resolve_model,
    supports_seed,
    supports_transparent,
    transparent_models,
    upstream_vendor,
)


class _FakeOpenAI:
    instances: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        type(self).instances.append(kwargs)
        self.images = SimpleNamespace()


class TestRegistry:
    def test_one_entry_per_member(self) -> None:
        assert set(PROVIDERS) == set(AIProvider)
        for key, info in PROVIDERS.items():
            assert info.name == key

    def test_registry_is_read_only(self) -> None:
        with pytest.raises(TypeError):
            PROVIDERS[AIProvider.OPENAI] = PROVIDERS[AIProvider.OPENAI]  # type: ignore[index]

    def test_openai_default_model_has_a_size_policy(self) -> None:
        assert PROVIDERS[AIProvider.OPENAI].default_model in MODEL_SIZE_POLICIES

    def test_openai_key_variable(self) -> None:
        assert PROVIDERS[AIProvider.OPENAI].api_key_env == "OPENAI_API_KEY"

    def test_openai_known_models_are_the_size_policies(self) -> None:
        assert known_models(AIProvider.OPENAI) == tuple(sorted(MODEL_SIZE_POLICIES))


class TestPolicies:
    @pytest.mark.parametrize("provider", list(AIProvider))
    def test_every_provider_has_https_policies_and_a_blurb(self, provider: AIProvider) -> None:
        info = PROVIDERS[provider]
        assert len(info.policy_urls) >= 1
        assert all(url.startswith("https://") for url in info.policy_urls)
        assert info.consent_blurb.strip()
        assert info.consent_blurb.endswith("\n")

    def test_openai_policy_and_blurb(self) -> None:
        info = PROVIDERS[AIProvider.OPENAI]
        assert info.policy_urls == ("https://openai.com/policies/usage-policies",)
        assert info.consent_blurb == (
            "  * You have read the OpenAI usage policy: "
            "https://openai.com/policies/usage-policies\n"
        )

    @pytest.mark.parametrize("model", sorted(MODEL_SIZE_POLICIES))
    def test_openai_policy_urls_are_the_registry_entry(self, model: str) -> None:
        assert policy_urls_for(AIProvider.OPENAI, model) == PROVIDERS[AIProvider.OPENAI].policy_urls


class TestResolveModel:
    def test_none_is_the_provider_default(self) -> None:
        assert resolve_model(AIProvider.OPENAI, None) == "gpt-image-2"

    def test_known_model_is_returned(self) -> None:
        assert resolve_model(AIProvider.OPENAI, "gpt-image-1") == "gpt-image-1"

    def test_unknown_model_lists_every_known_id_sorted(self) -> None:
        with pytest.raises(UnknownModelError) as info:
            resolve_model(AIProvider.OPENAI, "dall-e-9")
        known = ", ".join(sorted(MODEL_SIZE_POLICIES))
        assert str(info.value) == f"unknown openai image model 'dall-e-9'; known: {known}"

    def test_unknown_model_error_is_a_value_error(self) -> None:
        assert issubclass(UnknownModelError, ValueError)


@pytest.mark.parametrize("model", sorted(MODEL_SIZE_POLICIES))
def test_no_openai_model_supports_a_seed(model: str) -> None:
    assert supports_seed(AIProvider.OPENAI, model) is False


class TestMakeImageClient:
    @pytest.mark.parametrize("value", [None, "", "   "], ids=["unset", "empty", "blank"])
    def test_missing_key_names_the_variable(
        self, monkeypatch: pytest.MonkeyPatch, value: str | None
    ) -> None:
        if value is not None:  # unset: the conftest guard already scrubs the key (#143)
            monkeypatch.setenv("OPENAI_API_KEY", value)
        with pytest.raises(AIDependencyError, match="OPENAI_API_KEY"):
            make_image_client(AIProvider.OPENAI)

    def test_unknown_model_is_checked_before_the_key(self) -> None:
        with pytest.raises(UnknownModelError, match="dall-e-9"):
            make_image_client(AIProvider.OPENAI, "dall-e-9")

    def test_builds_an_openai_client_for_the_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))
        client = make_image_client(AIProvider.OPENAI, "gpt-image-1")
        assert isinstance(client, OpenAIImageClient)
        assert client.provider is AIProvider.OPENAI
        assert client.model == "gpt-image-1"

    def test_default_model_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))
        assert make_image_client(AIProvider.OPENAI).model == "gpt-image-2"

    def test_missing_extra_is_a_dependency_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setitem(sys.modules, "openai", None)  # `import openai` -> ImportError
        with pytest.raises(AIDependencyError, match=r"holiday-card\[ai\]"):
            make_image_client(AIProvider.OPENAI)


def test_dependency_error_lives_here_and_is_not_re_exported() -> None:
    assert AIDependencyError.__module__ == "holiday_card.core.ai_providers"
    assert "AIDependencyError" not in ai_openai.__all__
    assert not hasattr(ai_openai, "make_image_client")


def test_import_loads_neither_openai_nor_pil() -> None:
    code = (
        "import sys, holiday_card.core.ai_providers\n"
        "loaded = [m for m in ('openai', 'PIL') if m in sys.modules]\n"
        "assert not loaded, loaded\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


# --------------------------------------------------------------------------- OpenRouter (#150)

OR_KEY = "sk-or-v1-" + "ab" * 32
OR_PRIVACY_URL = "https://openrouter.ai/workspaces/default/settings"


class TestOpenRouterRegistry:
    def test_key_variable_and_default_model_is_curated(self) -> None:
        from holiday_card.core.ai_openrouter_models import OPENROUTER_IMAGE_MODELS

        info = PROVIDERS[AIProvider.OPENROUTER]
        assert info.api_key_env == "OPENROUTER_API_KEY"
        assert info.default_model == "google/gemini-3-pro-image"
        assert info.default_model in OPENROUTER_IMAGE_MODELS

    def test_policy_urls_are_the_terms_and_the_account_privacy_settings(self) -> None:
        assert PROVIDERS[AIProvider.OPENROUTER].policy_urls == (
            "https://openrouter.ai/terms",
            OR_PRIVACY_URL,
        )

    def test_known_models_are_the_curated_allowlist(self) -> None:
        from holiday_card.core.ai_openrouter_models import OPENROUTER_IMAGE_MODELS

        assert known_models(AIProvider.OPENROUTER) == tuple(sorted(OPENROUTER_IMAGE_MODELS))

    def test_unknown_model_lists_the_curated_ids(self) -> None:
        with pytest.raises(UnknownModelError) as info:
            resolve_model(AIProvider.OPENROUTER, "foo/bar")
        assert "unknown openrouter image model 'foo/bar'" in str(info.value)
        assert "google/gemini-3-pro-image" in str(info.value)

    def test_the_provider_is_never_inferred_from_a_slash(self) -> None:
        # O5 / §6.8: an OpenRouter id is not an OpenAI model.
        with pytest.raises(UnknownModelError):
            resolve_model(AIProvider.OPENAI, "google/gemini-3-pro-image")

    @pytest.mark.parametrize(
        ("model", "seed"),
        [("google/gemini-3-pro-image", False), ("black-forest-labs/flux.2-pro", True)],
    )
    def test_seed_support_is_the_allowlist_flag(self, model: str, seed: bool) -> None:
        assert supports_seed(AIProvider.OPENROUTER, model) is seed

    def test_policy_urls_add_the_upstream_vendor_terms(self) -> None:
        assert policy_urls_for(AIProvider.OPENROUTER, "black-forest-labs/flux.2-pro") == (
            "https://openrouter.ai/terms",
            OR_PRIVACY_URL,
            "https://bfl.ai/legal/developer-terms-of-service",
        )

    def test_reference_limits(self) -> None:
        assert reference_limits(AIProvider.OPENROUTER, "google/gemini-3-pro-image") == (0, 14)
        assert reference_limits(AIProvider.OPENAI, "gpt-image-2") == (0, 1)

    def test_upstream_vendor(self) -> None:
        assert upstream_vendor(AIProvider.OPENROUTER, "google/gemini-3-pro-image") == (
            "Google (AI Studio)",
            "https://ai.google.dev/gemini-api/terms",
            "google-ai-studio/global",
        )
        assert upstream_vendor(AIProvider.OPENAI, "gpt-image-2") is None


class TestOpenRouterFactory:
    @pytest.mark.parametrize("value", [None, "", "   "], ids=["unset", "empty", "blank"])
    def test_missing_key_names_the_variable_and_no_extra(
        self, monkeypatch: pytest.MonkeyPatch, value: str | None
    ) -> None:
        if value is not None:
            monkeypatch.setenv("OPENROUTER_API_KEY", value)
        with pytest.raises(AIDependencyError) as info:
            make_image_client(AIProvider.OPENROUTER)
        assert "OPENROUTER_API_KEY" in str(info.value)
        assert "[ai]" not in str(info.value)
        assert "pip install" not in str(info.value)

    def test_an_openai_key_does_not_cross_providers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with pytest.raises(AIDependencyError, match="OPENROUTER_API_KEY"):
            make_image_client(AIProvider.OPENROUTER)

    def test_builds_an_openrouter_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from holiday_card.core.ai_openrouter import OpenRouterImageClient

        monkeypatch.setenv("OPENROUTER_API_KEY", OR_KEY)
        client = make_image_client(AIProvider.OPENROUTER)
        assert isinstance(client, OpenRouterImageClient)
        assert client.provider is AIProvider.OPENROUTER
        assert client.model == "google/gemini-3-pro-image"
        assert OR_KEY not in repr(client)

    def test_reads_the_module_transport_at_call_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from holiday_card.core import ai_openrouter
        from holiday_card.core.ai_assets import AspectSize
        from openrouter_fixtures import FakeTransport

        fake = FakeTransport()
        monkeypatch.setattr(ai_openrouter, "urllib_transport", fake)
        monkeypatch.setenv("OPENROUTER_API_KEY", OR_KEY)
        client = make_image_client(AIProvider.OPENROUTER)
        client.generate(
            prompt="pine", reference_path=None, shape=AspectSize("3:4", "2K"), seed=None
        )
        assert len(fake.calls) == 1


# --- transparent background (#169) -------------------------------------------------


@pytest.mark.parametrize("model", sorted(MODEL_SIZE_POLICIES))
def test_no_direct_openai_model_offers_a_transparent_background(model: str) -> None:
    # Enabling direct OpenAI is an owner call (#169).
    assert supports_transparent(AIProvider.OPENAI, model) is False


def test_transparent_support_is_the_allowlist_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace
    from types import MappingProxyType

    from holiday_card.core import ai_openrouter_models

    models = ai_openrouter_models.OPENROUTER_IMAGE_MODELS
    flux = "black-forest-labs/flux.2-pro"
    assert supports_transparent(AIProvider.OPENROUTER, flux) is False
    assert transparent_models(AIProvider.OPENROUTER) == []
    monkeypatch.setattr(
        ai_openrouter_models,
        "OPENROUTER_IMAGE_MODELS",
        MappingProxyType({**models, flux: replace(models[flux], background_transparent=True)}),
    )
    assert supports_transparent(AIProvider.OPENROUTER, flux) is True
    assert transparent_models(AIProvider.OPENROUTER) == [flux]
    assert transparent_models(AIProvider.OPENAI) == []
