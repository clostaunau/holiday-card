"""The curated OpenRouter image-model allowlist (L3, spec §3 / O2 / O6).

OpenRouter sizes an image by an aspect-ratio enum plus a resolution tier,
and each endpoint (hosting provider) of a model can advertise different
values. So every entry here pins **one** endpoint (``provider_tag``, sent
as ``provider.only``; no fallbacks) and records exactly what that endpoint
advertises. An id that is not here is refused: only reviewed models, whose
output terms someone has read, are allowed.

The values are checked in, never fetched at run time. Refresh them with
``scripts/refresh_openrouter_models.py`` (dev-only) and review the diff;
see ``docs/industry-review/openrouter-image-api-snapshot.md``.

Stdlib only: importing this loads neither Pillow nor pydantic nor any HTTP
client.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Literal
from urllib.parse import urlsplit

__all__ = [
    "Billable",
    "PriceUnit",
    "OpenRouterPrice",
    "OpenRouterModel",
    "OPENROUTER_IMAGE_MODELS",
    "RESOLUTION_LONG_EDGE_PX",
    "aspect_ratio_value",
    "openrouter_model",
    "upstream_vendor_name",
]

Billable = Literal["output_image", "input_image", "input_reference", "input_text"]
PriceUnit = Literal["image", "megapixel", "token"]

MAX_INPUT_REFERENCES = 16

# Nominal long edge of each resolution tier. OpenRouter does not publish
# per-model pixel sizes (spec §3); #140 measures the real W×H, and if a tier
# turns out to mean something else this table changes with it.
RESOLUTION_LONG_EDGE_PX: Mapping[str, int] = MappingProxyType(
    {"512": 512, "768": 768, "1K": 1024, "2K": 2048, "4K": 4096}
)


def aspect_ratio_value(ratio: str) -> float:
    """The width / height of a ``"W:H"`` aspect ratio such as ``"9:19.5"``.

    Raises ``ValueError`` for ``"auto"``, a missing or extra ``:``, and any
    part that is not a finite number greater than zero.
    """
    parts = ratio.split(":")
    try:
        if len(parts) != 2:
            raise ValueError
        w, h = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError(f"invalid aspect ratio {ratio!r}; expected 'W:H'") from None
    if not (math.isfinite(w) and math.isfinite(h) and w > 0 and h > 0):
        raise ValueError(f"invalid aspect ratio {ratio!r}; W and H must be finite and > 0")
    return w / h


@dataclass(frozen=True)
class OpenRouterPrice:
    """One row of an endpoint's ``pricing[]``."""

    billable: Billable
    unit: PriceUnit
    cost_usd: float


@dataclass(frozen=True)
class OpenRouterModel:
    """One curated model, as its pinned endpoint advertises it.

    ``resolutions == ()`` and ``output_formats == ()`` mean the endpoint does
    not advertise the parameter, so it is never sent. ``__post_init__``
    refuses a malformed entry, so a bad paste fails at import (D4).
    """

    id: str
    provider_tag: str
    aspect_ratios: tuple[str, ...]
    resolutions: tuple[str, ...]
    input_refs_min: int
    input_refs_max: int
    seed: bool
    output_formats: tuple[str, ...]
    background_transparent: bool
    passthrough: tuple[str, ...]
    pricing: tuple[OpenRouterPrice, ...]
    upstream_terms_url: str
    snapshot_date: str

    def __post_init__(self) -> None:
        def bad(field: str, why: str) -> ValueError:
            return ValueError(f"OpenRouter model {self.id!r}: {field}: {why}")

        if not self.provider_tag:
            raise bad("provider_tag", "empty; pin exactly one endpoint")
        if not self.aspect_ratios:
            raise bad("aspect_ratios", "empty")
        for ratio in self.aspect_ratios:
            if ratio == "auto":
                raise bad("aspect_ratios", "'auto' is never requested; remove it")
            try:
                aspect_ratio_value(ratio)
            except ValueError as e:
                raise bad("aspect_ratios", str(e)) from e
        unknown = [r for r in self.resolutions if r not in RESOLUTION_LONG_EDGE_PX]
        if unknown:
            known = ", ".join(RESOLUTION_LONG_EDGE_PX)
            raise bad("resolutions", f"unknown tier(s) {', '.join(unknown)}; known: {known}")
        if not 0 <= self.input_refs_min <= self.input_refs_max <= MAX_INPUT_REFERENCES:
            raise bad(
                "input_refs_min/input_refs_max",
                f"need 0 <= min <= max <= {MAX_INPUT_REFERENCES}, "
                f"got {self.input_refs_min}..{self.input_refs_max}",
            )
        if not self.pricing:
            raise bad("pricing", "empty")
        if any(p.cost_usd < 0 for p in self.pricing):
            raise bad("pricing", "a cost_usd is negative")
        try:
            date.fromisoformat(self.snapshot_date)
        except ValueError as e:
            raise bad("snapshot_date", f"{self.snapshot_date!r} is not an ISO date") from e
        url = urlsplit(self.upstream_terms_url)
        host = (url.hostname or "").lower()
        if url.scheme != "https" or not host:
            raise bad("upstream_terms_url", f"{self.upstream_terms_url!r} is not an https URL")
        if host == "openrouter.ai" or host.endswith(".openrouter.ai"):
            raise bad("upstream_terms_url", "must be the model vendor's terms, not OpenRouter's")


def _prices(*rows: tuple[Billable, PriceUnit, float]) -> tuple[OpenRouterPrice, ...]:
    return tuple(OpenRouterPrice(*row) for row in rows)


_SNAPSHOT = "2026-09-30"

# Fetched 2026-09-30 from the public catalogue (recorded in
# tests/fixtures/openrouter/catalogue/). upstream_terms_url is the reviewed
# page that governs output ownership for API use, not always the one
# /providers lists (see the snapshot doc).
_ENTRIES = (
    OpenRouterModel(
        id="google/gemini-3-pro-image",
        provider_tag="google-ai-studio/global",
        aspect_ratios=("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"),
        resolutions=("1K", "2K", "4K"),
        input_refs_min=0,
        input_refs_max=14,
        seed=False,
        output_formats=(),
        background_transparent=False,
        passthrough=("cachedContent",),
        pricing=_prices(("input_image", "token", 0.000002), ("output_image", "token", 0.00012)),
        upstream_terms_url="https://ai.google.dev/gemini-api/terms",
        snapshot_date=_SNAPSHOT,
    ),
    OpenRouterModel(
        id="google/gemini-3.1-flash-image",
        provider_tag="google-ai-studio",
        aspect_ratios=(
            "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1",
            "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
        ),  # fmt: skip
        resolutions=("512", "1K", "2K", "4K"),
        input_refs_min=0,
        input_refs_max=14,
        seed=False,
        output_formats=(),
        background_transparent=False,
        passthrough=("cachedContent",),
        pricing=_prices(("output_image", "token", 0.00006)),
        upstream_terms_url="https://ai.google.dev/gemini-api/terms",
        snapshot_date=_SNAPSHOT,
    ),
    OpenRouterModel(
        id="black-forest-labs/flux.2-pro",
        provider_tag="black-forest-labs",
        aspect_ratios=("1:1", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16", "21:9"),
        resolutions=(),
        input_refs_min=0,
        input_refs_max=8,
        seed=True,
        output_formats=("png", "jpeg"),
        background_transparent=False,
        passthrough=("steps", "guidance", "safety_tolerance"),
        pricing=_prices(("output_image", "megapixel", 0.03)),
        upstream_terms_url="https://bfl.ai/legal/developer-terms-of-service",
        snapshot_date=_SNAPSHOT,
    ),
    OpenRouterModel(
        id="bytedance-seed/seedream-4.5",
        provider_tag="seed",
        aspect_ratios=(
            "1:1", "1:2", "2:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
            "9:16", "16:9", "9:19.5", "19.5:9", "9:20", "20:9", "9:21", "21:9",
        ),  # fmt: skip
        resolutions=("1K", "2K", "4K"),
        input_refs_min=0,
        input_refs_max=14,
        seed=True,
        output_formats=(),
        background_transparent=False,
        passthrough=(),
        pricing=_prices(("output_image", "image", 0.04), ("input_image", "image", 0.0)),
        upstream_terms_url="https://docs.byteplus.com/en/docs/legal/AI-Services-terms",
        snapshot_date=_SNAPSHOT,
    ),
    OpenRouterModel(
        id="openai/gpt-image-2",
        provider_tag="openai",
        aspect_ratios=("1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9"),
        resolutions=(),
        input_refs_min=0,
        input_refs_max=16,
        seed=False,
        output_formats=(),
        background_transparent=False,
        passthrough=("moderation",),
        pricing=_prices(
            ("input_image", "token", 0.000008),
            ("input_text", "token", 0.000005),
            ("output_image", "token", 0.00003),
        ),
        upstream_terms_url="https://openai.com/policies/services-agreement/",
        snapshot_date=_SNAPSHOT,
    ),
)

OPENROUTER_IMAGE_MODELS: Mapping[str, OpenRouterModel] = MappingProxyType(
    {entry.id: entry for entry in _ENTRIES}
)


def openrouter_model(model_id: str) -> OpenRouterModel:
    """The curated entry for ``model_id``.

    Raises:
        ValueError: If ``model_id`` is not curated (O2: no run-time catalogue).
    """
    try:
        return OPENROUTER_IMAGE_MODELS[model_id]
    except KeyError:
        curated = ", ".join(sorted(OPENROUTER_IMAGE_MODELS))
        raise ValueError(
            f"unknown OpenRouter image model {model_id!r}; curated: {curated} "
            "(only reviewed models are allowed; see "
            "docs/industry-review/openrouter-image-api-snapshot.md)"
        ) from None


# The display name of each pinned endpoint's vendor, keyed by the slug of
# ``provider_tag`` (before any ``/region``). The consent notice names it.
_VENDOR_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "google-ai-studio": "Google (AI Studio)",
        "black-forest-labs": "Black Forest Labs",
        "seed": "ByteDance (Seed)",
        "openai": "OpenAI",
    }
)


def upstream_vendor_name(entry: OpenRouterModel) -> str:
    """The human name of the vendor ``entry``'s pinned endpoint sends the request to.

    Raises:
        KeyError: If the endpoint's slug has no name (a test covers every entry).
    """
    return _VENDOR_NAMES[entry.provider_tag.split("/")[0]]
