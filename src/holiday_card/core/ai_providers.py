"""AI image-provider registry and client factory (issue #146).

The one place a provider's API-key variable and default model live, and
the one factory that turns ``(provider, model)`` into an
:class:`~holiday_card.core.ai_assets.ImageClient`. It is import-light:
stdlib only at module level, with the adapter and ``ai_assets`` imported
inside the functions that need them, so importing the CLI never loads
``openai`` (or Pillow) and there is no import cycle with ``ai_assets``.

The provider is chosen explicitly and never inferred from a model id.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, assert_never

if TYPE_CHECKING:
    from holiday_card.core.ai_assets import ImageClient

__all__ = [
    "AIProvider",
    "ProviderInfo",
    "PROVIDERS",
    "AIDependencyError",
    "UnknownModelError",
    "known_models",
    "resolve_model",
    "supports_seed",
    "make_image_client",
]


class AIProvider(StrEnum):
    """An image provider ``ai-asset generate`` can call."""

    OPENAI = "openai"
    # OPENROUTER is added by #150, together with its adapter wiring (D17: no dead members).


@dataclass(frozen=True)
class ProviderInfo:
    """Static facts about one provider."""

    name: AIProvider
    api_key_env: str
    default_model: str


PROVIDERS: Mapping[AIProvider, ProviderInfo] = MappingProxyType(
    {
        AIProvider.OPENAI: ProviderInfo(
            name=AIProvider.OPENAI,
            api_key_env="OPENAI_API_KEY",
            default_model="gpt-image-2",
        ),
    }
)


class AIDependencyError(RuntimeError):
    """The provider's API key or the ``[ai]`` extra is missing (CLI exit 4)."""


class UnknownModelError(ValueError):
    """``--model`` is not a known model of ``--provider`` (CLI exit 2)."""


def known_models(provider: AIProvider) -> tuple[str, ...]:
    """The model ids ``provider`` accepts, sorted."""
    match provider:
        case AIProvider.OPENAI:
            from holiday_card.core.ai_assets import MODEL_SIZE_POLICIES

            return tuple(sorted(MODEL_SIZE_POLICIES))
        case _:
            assert_never(provider)


def resolve_model(provider: AIProvider, model: str | None) -> str:
    """``model``, or the provider's default when ``None``.

    Raises:
        UnknownModelError: If ``model`` is not one of :func:`known_models`.
    """
    if model is None:
        return PROVIDERS[provider].default_model
    known = known_models(provider)
    if model not in known:
        raise UnknownModelError(
            f"unknown {provider.value} image model {model!r}; known: {', '.join(known)}"
        )
    return model


def supports_seed(provider: AIProvider, model: str) -> bool:  # noqa: ARG001 - per-model once a provider has seeds
    """Whether ``model`` takes a seed that makes its output reproducible."""
    match provider:
        case AIProvider.OPENAI:
            # The OpenAI Images API has no seed parameter (spec §3 "Seed").
            return False
        case _:
            assert_never(provider)


def make_image_client(provider: AIProvider, model: str | None = None) -> ImageClient:
    """Construct a live client for ``provider`` / ``model``.

    The model is resolved first, so an unknown model is reported even when
    no key is set; then the key is read from the provider's variable.

    Raises:
        UnknownModelError: For an unknown ``model``.
        AIDependencyError: If the key is unset or blank, or the ``[ai]``
            extra is not installed.
    """
    resolved = resolve_model(provider, model)
    info = PROVIDERS[provider]
    api_key = os.environ.get(info.api_key_env, "").strip()
    if not api_key:
        raise AIDependencyError(
            f"{info.api_key_env} is not set. AI imagery with {provider.value} "
            f"requires an API key (and `pip install holiday-card[ai]`)."
        )
    match provider:
        case AIProvider.OPENAI:
            from holiday_card.core.ai_openai import make_openai_client

            return make_openai_client(api_key=api_key, model=resolved)
        case _:
            assert_never(provider)
