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
from typing import TYPE_CHECKING, Any, assert_never

from holiday_card.core import ai_openrouter_models
from holiday_card.core.ai_openrouter_models import OpenRouterPrice

if TYPE_CHECKING:
    from holiday_card.core.ai_assets import ImageClient, ModelSizePolicy

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
    "MODELS_SCHEMA_VERSION",
    "PixelSizeRule",
    "ModelListing",
    "list_models",
    "model_listing_payload",
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


# --- the curated model listing (`ai-asset models`, #152) -----------------------------

MODELS_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PixelSizeRule:
    """The pixel sizes a direct OpenAI model accepts: ``fixed`` sizes, or flexible bounds."""

    fixed: tuple[tuple[int, int], ...] | None
    multiple: int | None
    max_edge: int | None
    max_aspect: float | None
    min_pixels: int | None
    max_pixels: int | None


@dataclass(frozen=True)
class ModelListing:
    """One curated image model, as ``ai-asset models`` lists it. No network."""

    provider: AIProvider
    id: str
    default: bool  # == PROVIDERS[provider].default_model
    route: str  # "openai" (direct) | the pinned OpenRouter provider_tag
    upstream: str  # the vendor the request reaches
    input_references: tuple[int, int]  # (min, max)
    aspect_ratios: tuple[str, ...] | None  # None for pixel-sized models
    resolutions: tuple[str, ...] | None  # None when the endpoint has no tiers / pixel-sized
    pixel_sizes: PixelSizeRule | None  # OpenAI direct only
    seed: bool
    output_formats: tuple[str, ...]  # () when the endpoint advertises no output_format
    pricing: tuple[OpenRouterPrice, ...]  # () when no price is recorded
    terms_urls: tuple[str, ...]  # provider policy URLs, then the upstream terms URL
    snapshot_date: str  # ISO date the capability data was verified


def _pixel_size_rule(policy: ModelSizePolicy) -> PixelSizeRule:
    if policy.fixed_sizes is not None:
        return PixelSizeRule(policy.fixed_sizes, None, None, None, None, None)
    return PixelSizeRule(
        fixed=None,
        multiple=policy.multiple,
        max_edge=policy.max_edge,
        max_aspect=policy.max_aspect,
        min_pixels=policy.min_pixels,
        max_pixels=policy.max_pixels,
    )


def _listings(provider: AIProvider) -> list[ModelListing]:
    default = PROVIDERS[provider].default_model
    match provider:
        case AIProvider.OPENAI:
            from holiday_card.core import ai_assets

            return [
                ModelListing(
                    provider=provider,
                    id=model,
                    default=model == default,
                    route="openai",
                    upstream="OpenAI",
                    input_references=reference_limits(provider, model),
                    aspect_ratios=None,
                    resolutions=None,
                    pixel_sizes=_pixel_size_rule(policy),
                    seed=supports_seed(provider, model),
                    output_formats=("png",),
                    pricing=(
                        ()
                        if policy.max_price_usd is None
                        else (OpenRouterPrice("output_image", "image", policy.max_price_usd),)
                    ),
                    terms_urls=policy_urls_for(provider, model),
                    snapshot_date=ai_assets.MODEL_SIZE_POLICIES_VERIFIED,
                )
                for model, policy in ai_assets.MODEL_SIZE_POLICIES.items()
            ]
        case AIProvider.OPENROUTER:
            return [
                ModelListing(
                    provider=provider,
                    id=entry.id,
                    default=entry.id == default,
                    route=entry.provider_tag,
                    upstream=ai_openrouter_models.upstream_vendor_name(entry),
                    input_references=(entry.input_refs_min, entry.input_refs_max),
                    aspect_ratios=entry.aspect_ratios,
                    resolutions=entry.resolutions or None,
                    pixel_sizes=None,
                    seed=entry.seed,
                    output_formats=entry.output_formats,
                    pricing=entry.pricing,
                    terms_urls=policy_urls_for(provider, entry.id),
                    snapshot_date=entry.snapshot_date,
                )
                for entry in ai_openrouter_models.OPENROUTER_IMAGE_MODELS.values()
            ]
        case _:
            assert_never(provider)


def list_models(provider: AIProvider | None = None) -> list[ModelListing]:
    """The curated image models of ``provider`` (or of every provider), from checked-in tables.

    Sorted by ``(provider, id)``. Makes no network call and imports no adapter.
    """
    providers = list(AIProvider) if provider is None else [provider]
    rows = [row for p in providers for row in _listings(p)]
    return sorted(rows, key=lambda r: (r.provider.value, r.id))


def _listing_record(row: ModelListing) -> dict[str, object]:
    rule = row.pixel_sizes
    return {
        "provider": row.provider.value,
        "id": row.id,
        "default": row.default,
        "route": row.route,
        "upstream": row.upstream,
        "input_references": {"min": row.input_references[0], "max": row.input_references[1]},
        "aspect_ratios": None if row.aspect_ratios is None else list(row.aspect_ratios),
        "resolutions": None if row.resolutions is None else list(row.resolutions),
        "pixel_sizes": None if rule is None else {
            "fixed": None if rule.fixed is None else [list(size) for size in rule.fixed],
            "multiple": rule.multiple,
            "max_edge": rule.max_edge,
            "max_aspect": rule.max_aspect,
            "min_pixels": rule.min_pixels,
            "max_pixels": rule.max_pixels,
        },
        "seed": row.seed,
        "output_formats": list(row.output_formats),
        "pricing": [
            {"billable": p.billable, "unit": p.unit, "usd": p.cost_usd} for p in row.pricing
        ],
        "terms_urls": list(row.terms_urls),
        "snapshot_date": row.snapshot_date,
    }


def model_listing_payload(rows: list[ModelListing]) -> dict[str, Any]:
    """The versioned JSON / YAML document of ``rows``: plain lists, dicts and scalars only."""
    return {"schema_version": MODELS_SCHEMA_VERSION, "models": [_listing_record(r) for r in rows]}
