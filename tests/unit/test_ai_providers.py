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
    resolve_model,
    supports_seed,
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
