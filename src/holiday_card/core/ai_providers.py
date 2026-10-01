"""AI image-provider registry and client factory (issue #146).

The one place a provider's API-key variable and default model live, and
the one factory that turns ``(provider, model)`` into an
:class:`~holiday_card.core.ai_assets.ImageClient`. It is import-light:
stdlib only at module level, with the adapter and ``ai_assets`` imported
inside the functions that need them, so importing the CLI never loads
``openai`` (or Pillow) and there is no import cycle with ``ai_assets``.

The provider is chosen explicitly and never inferred from a model id.
OpenRouter's per-model facts come from the curated allowlist
(:mod:`~holiday_card.core.ai_openrouter_models`, stdlib only), read
through the module at call time.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, assert_never

from holiday_card.core import ai_openrouter_models

if TYPE_CHECKING:
    from holiday_card.core.ai_assets import ImageClient

__all__ = [
    "AIProvider",
    "ProviderInfo",
    "PROVIDERS",
    "AIDependencyError",
    "UnknownModelError",
    "known_models",
    "policy_urls_for",
    "reference_limits",
    "resolve_model",
    "supports_seed",
    "upstream_vendor",
    "make_image_client",
]


class AIProvider(StrEnum):
    """An image provider ``ai-asset generate`` can call."""

    OPENAI = "openai"
    OPENROUTER = "openrouter"


@dataclass(frozen=True)
class ProviderInfo:
    """Static facts about one provider."""

    name: AIProvider
    api_key_env: str
    default_model: str
    policy_urls: tuple[str, ...]  # recorded in the consent file and every sidecar
    consent_blurb: str  # this provider's bullet(s) in the consent notice


# Verified 2026-09-30: the page openrouter.ai/docs/guides/privacy/data-collection
# links for the account's data-retention / training settings.
_OPENROUTER_PRIVACY_URL = "https://openrouter.ai/workspaces/default/settings"

OPENROUTER_CONSENT_BLURB = f"""\
  * Your prompt and reference image are sent to OpenRouter AND to the
    upstream vendor of the model you chose (for example Google or Black
    Forest Labs). holiday-card pins that one vendor and never falls back.
  * You have read the OpenRouter Terms of Service:
    https://openrouter.ai/terms
    Ownership of the output, and what you may do with it, is set by the
    upstream vendor's model terms; OpenRouter grants no licence of its own.
    That vendor's terms URL is recorded in each asset's .license.yaml sidecar.
  * OpenRouter's data-retention and training settings are ACCOUNT-LEVEL
    settings of your OpenRouter account; this tool cannot opt out per
    request. Review them before you send a private image:
    {_OPENROUTER_PRIVACY_URL}
  * Reference images are NOT screened for trademarks or real people's
    likenesses; only the text prompt is checked. You are responsible for
    what you upload: do not send a reference you do not have the rights to.
"""

PROVIDERS: Mapping[AIProvider, ProviderInfo] = MappingProxyType(
    {
        AIProvider.OPENAI: ProviderInfo(
            name=AIProvider.OPENAI,
            api_key_env="OPENAI_API_KEY",
            default_model="gpt-image-2",
            policy_urls=("https://openai.com/policies/usage-policies",),
            consent_blurb=(
                "  * You have read the OpenAI usage policy: "
                "https://openai.com/policies/usage-policies\n"
            ),
        ),
        AIProvider.OPENROUTER: ProviderInfo(
            name=AIProvider.OPENROUTER,
            api_key_env="OPENROUTER_API_KEY",
            # Provisional until #140's live verification recommends one.
            default_model="google/gemini-3-pro-image",
            policy_urls=("https://openrouter.ai/terms", _OPENROUTER_PRIVACY_URL),
            consent_blurb=OPENROUTER_CONSENT_BLURB,
        ),
    }
)


class AIDependencyError(RuntimeError):
    """The provider's API key, or OpenAI's ``[ai]`` extra, is missing (CLI exit 4)."""


class UnknownModelError(ValueError):
    """``--model`` is not a known model of ``--provider`` (CLI exit 2)."""


def known_models(provider: AIProvider) -> tuple[str, ...]:
    """The model ids ``provider`` accepts, sorted."""
    match provider:
        case AIProvider.OPENAI:
            from holiday_card.core.ai_assets import MODEL_SIZE_POLICIES

            return tuple(sorted(MODEL_SIZE_POLICIES))
        case AIProvider.OPENROUTER:
            return tuple(sorted(ai_openrouter_models.OPENROUTER_IMAGE_MODELS))
        case _:
            assert_never(provider)


def policy_urls_for(provider: AIProvider, model: str) -> tuple[str, ...]:
    """The policy URLs a bake with ``provider`` / ``model`` is made under.

    For OpenRouter: its own, then the pinned upstream vendor's terms, which
    govern ownership of the output.
    """
    match provider:
        case AIProvider.OPENAI:
            return PROVIDERS[provider].policy_urls
        case AIProvider.OPENROUTER:
            entry = ai_openrouter_models.openrouter_model(model)
            return (*PROVIDERS[provider].policy_urls, entry.upstream_terms_url)
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


def supports_seed(provider: AIProvider, model: str) -> bool:
    """Whether ``model`` takes a seed that makes its output reproducible."""
    match provider:
        case AIProvider.OPENAI:
            # The OpenAI Images API has no seed parameter (spec §3 "Seed").
            return False
        case AIProvider.OPENROUTER:
            return ai_openrouter_models.openrouter_model(model).seed
        case _:
            assert_never(provider)


def reference_limits(provider: AIProvider, model: str) -> tuple[int, int]:
    """The ``(min, max)`` number of reference images ``model`` accepts.

    The CLI's style-anchor rule (S2) is checked against it before consent.
    """
    match provider:
        case AIProvider.OPENAI:
            return (0, 1)  # images.edit with one reference, or images.generate with none
        case AIProvider.OPENROUTER:
            entry = ai_openrouter_models.openrouter_model(model)
            return (entry.input_refs_min, entry.input_refs_max)
        case _:
            assert_never(provider)


def upstream_vendor(provider: AIProvider, model: str) -> tuple[str, str, str] | None:
    """``(vendor name, terms URL, route)`` of the vendor a routed ``model`` reaches.

    ``None`` for a direct provider.
    """
    match provider:
        case AIProvider.OPENAI:
            return None
        case AIProvider.OPENROUTER:
            entry = ai_openrouter_models.openrouter_model(model)
            name = ai_openrouter_models.upstream_vendor_name(entry)
            return (name, entry.upstream_terms_url, entry.provider_tag)
        case _:
            assert_never(provider)


def make_image_client(provider: AIProvider, model: str | None = None) -> ImageClient:
    """Construct a live client for ``provider`` / ``model``.

    The model is resolved first, so an unknown model is reported even when
    no key is set; then the key is read from the provider's variable.

    Raises:
        UnknownModelError: For an unknown ``model``.
        AIDependencyError: If the key is unset or blank, or (OpenAI only)
            the ``[ai]`` extra is not installed.
    """
    resolved = resolve_model(provider, model)
    info = PROVIDERS[provider]
    api_key = os.environ.get(info.api_key_env, "").strip()
    if not api_key:
        match provider:
            case AIProvider.OPENAI:
                needs = "an API key (and `pip install holiday-card[ai]`)"
            case AIProvider.OPENROUTER:
                needs = "an API key; no install extra is needed"  # O4
            case _:
                assert_never(provider)
        raise AIDependencyError(
            f"{info.api_key_env} is not set. AI imagery with {provider.value} requires {needs}."
        )
    match provider:
        case AIProvider.OPENAI:
            from holiday_card.core.ai_openai import make_openai_client

            return make_openai_client(api_key=api_key, model=resolved)
        case AIProvider.OPENROUTER:
            from pydantic import SecretStr

            # Function-local: importing the CLI must not load urllib.request (#149).
            from holiday_card.core import ai_openrouter

            return ai_openrouter.OpenRouterImageClient(
                api_key=SecretStr(api_key),
                model=resolved,
                # Read at call time so tests can monkeypatch the module attribute.
                transport=ai_openrouter.urllib_transport,
            )
        case _:
            assert_never(provider)
