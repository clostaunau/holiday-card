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
from collections.abc import Callable, Mapping
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
    # Human-maintained upper bounds for ``--max-cost`` (#151); the refresh
    # script carries them over. Each is filled only from a cited, dated
    # vendor source, recorded in ``bound_source`` ("YYYY-MM-DD https://…").
    max_output_megapixels: float | None = None  # megapixel-priced output, no tier
    output_image_tokens: Mapping[str, int] | None = None  # per tier, or "default"
    input_image_tokens: int | None = None  # per token-priced reference image
    bound_source: str | None = None

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
        self._check_bounds(bad)
        url = urlsplit(self.upstream_terms_url)
        host = (url.hostname or "").lower()
        if url.scheme != "https" or not host:
            raise bad("upstream_terms_url", f"{self.upstream_terms_url!r} is not an https URL")
        if host == "openrouter.ai" or host.endswith(".openrouter.ai"):
            raise bad("upstream_terms_url", "must be the model vendor's terms, not OpenRouter's")

    def _check_bounds(self, bad: Callable[[str, str], ValueError]) -> None:
        mp, tokens, ref_tokens = (
            self.max_output_megapixels, self.output_image_tokens, self.input_image_tokens
        )
        if mp is not None and not (math.isfinite(mp) and mp > 0):
            raise bad("max_output_megapixels", f"{mp!r} is not a finite number > 0")
        if tokens is not None:
            allowed = set(self.resolutions) or {"default"}
            if not tokens or not set(tokens) <= allowed:
                raise bad(
                    "output_image_tokens",
                    f"keys {sorted(tokens)} must be among {sorted(allowed)}",
                )
            if any(n <= 0 for n in tokens.values()):
                raise bad("output_image_tokens", "every count must be > 0")
        if ref_tokens is not None and ref_tokens <= 0:
            raise bad("input_image_tokens", f"{ref_tokens!r} is not > 0")
        has_bound = (mp, tokens, ref_tokens) != (None, None, None)
        if has_bound != (self.bound_source is not None):
            raise bad("bound_source", "needed exactly when an upper bound is recorded")
        if self.bound_source is not None:
            stamp, _, rest = self.bound_source.partition(" ")
            try:
                date.fromisoformat(stamp)
            except ValueError as e:
                raise bad("bound_source", "must start with an ISO date") from e
            if "https://" not in rest:
                raise bad("bound_source", "must cite an https:// source after the date")


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
        # "1K … and up to 2048x2048px (2K) consume 1120 tokens", "4K … 2000
        # tokens"; "Image input is set at 560 tokens".
        output_image_tokens=MappingProxyType({"1K": 1120, "2K": 1120, "4K": 2000}),
        input_image_tokens=560,
        bound_source="2026-09-30 https://ai.google.dev/gemini-api/docs/pricing (Gemini 3 Pro Image)",
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
        # "0.5K (512px) consume 747 tokens", 1K 1120, 2K 1680, 4K 2520. No
        # input_image price row, so a reference needs no token bound.
        output_image_tokens=MappingProxyType({"512": 747, "1K": 1120, "2K": 1680, "4K": 2520}),
        bound_source="2026-09-30 https://ai.google.dev/gemini-api/docs/pricing (Gemini 3.1 Flash Image)",
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
        # "FLUX.2 generates images up to 4MP (e.g., 2048x2048)": the example
        # is 4.194304 MP, so the bound is 2048 x 2048, not a round 4.0.
        max_output_megapixels=2048 * 2048 / 1e6,
        bound_source=(
            "2026-09-30 https://help.bfl.ai/articles/8531149640-what-are-the-resolution-limits"
        ),
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
    """The human name of the vendor ``entry``'s pinned endpoint sends the request to."""
    return _VENDOR_NAMES[entry.provider_tag.split("/")[0]]


# A curated entry whose vendor has no name fails at import, not at first use (D4).
_unnamed = sorted(
    e.id for e in _ENTRIES if e.provider_tag.split("/")[0] not in _VENDOR_NAMES
)
if _unnamed:  # pragma: no cover - a test covers every shipped entry
    raise ValueError(f"OpenRouter model(s) {', '.join(_unnamed)}: add the vendor to _VENDOR_NAMES")
