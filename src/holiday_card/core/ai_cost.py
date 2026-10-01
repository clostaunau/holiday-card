"""The offline upper-bound price of one generation, for ``--max-cost`` (#151, spec §6.7).

OpenRouter's ``/images`` takes no ``max_price``, so the cap is enforced
here, before any call: the estimate comes only from the checked-in
allowlist (its ``pricing`` rows and the human-maintained upper bounds), with
no live preflight. A missing price or bound is refused, never guessed (D4).

Per pricing row (``n_refs`` is 1 with a reference, else 0):

* ``image``: ``cost × 1`` for the output (``n: 1``), ``cost × n_refs`` for inputs;
* ``megapixel``: output ``cost × max_output_megapixels``, else the tier's
  ``L × round(L × short / long)`` pixels; input ``cost × n_refs ×`` the
  probed reference's exact megapixels;
* ``token``: output ``cost × output_image_tokens[tier or "default"]``;
  input image ``cost × n_refs × input_image_tokens``; input text
  ``cost × (UTF-8 bytes + 16)``, a bound on byte-level BPE tokens plus
  special tokens, not an exact count.

Then, for an entry with an ``output_text_tokens`` allowance (#173),
``output_text_usd_per_token × output_text_tokens``: text / thinking tokens
the model bills beside the image, which no catalogue price row covers.

Stdlib only at import time; the OpenAI branch reads its size policy lazily.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never

from holiday_card.core.ai_openrouter_models import (
    RESOLUTION_LONG_EDGE_PX,
    OpenRouterModel,
    OpenRouterPrice,
    openrouter_model,
)
from holiday_card.core.ai_providers import AIProvider

if TYPE_CHECKING:
    from holiday_card.core.ai_assets import RequestShape
    from holiday_card.core.images import ProbedImage

__all__ = [
    "TIER_LONG_EDGE_PX",
    "CostEstimate",
    "NoPriceOnRecordError",
    "CostCapExceededError",
    "estimate_max_cost",
    "estimate_openrouter_cost",
    "check_cost_cap",
    "format_usd_cap",
]

# The resolution chooser's own table (one copy, not two).
TIER_LONG_EDGE_PX: Mapping[str, int] = RESOLUTION_LONG_EDGE_PX

_TEXT_TOKEN_OVERHEAD = 16


@dataclass(frozen=True)
class CostEstimate:
    """An upper-bound price: ``usd`` is compared with the cap, ``lines`` explain it."""

    usd: float
    lines: tuple[str, ...]


class NoPriceOnRecordError(ValueError):
    """The allowlist lacks a price or bound needed to bound this request (D4)."""

    def __init__(self, model: str, provider: AIProvider, reason: str) -> None:
        self.model = model
        self.provider = provider
        self.reason = reason
        super().__init__(f"no price on record for {model} ({provider.value}): {reason}")


def format_usd_cap(cap_usd: float) -> str:
    """``cap_usd`` as typed: cents when that is exact (``$0.10``), else in full."""
    return f"${cap_usd:.2f}" if round(cap_usd, 2) == cap_usd else f"${cap_usd:g}"


class CostCapExceededError(ValueError):
    """The upper-bound estimate is above ``--max-cost``; nothing was spent."""

    def __init__(self, estimate: CostEstimate, cap_usd: float) -> None:
        self.estimate = estimate
        self.cap_usd = cap_usd
        super().__init__(
            f"estimated cost ${estimate.usd:.4f} exceeds --max-cost {format_usd_cap(cap_usd)}"
        )


def check_cost_cap(estimate: CostEstimate, cap_usd: float) -> None:
    """Raise :class:`CostCapExceededError` when ``estimate.usd > cap_usd`` (equal passes)."""
    if estimate.usd > cap_usd:
        raise CostCapExceededError(estimate, cap_usd)


def _line(row: OpenRouterPrice, quantity: str, unit: str, usd: float) -> str:
    return f"{row.billable}: {quantity} {unit} x ${row.cost_usd:g} = ${usd:.10g}"


def _tier_megapixels(aspect_ratio: str, resolution: str) -> float:
    a, b = (float(part) for part in aspect_ratio.split(":"))
    long_edge = TIER_LONG_EDGE_PX[resolution]
    return long_edge * round(long_edge * min(a, b) / max(a, b)) / 1e6


def estimate_openrouter_cost(
    entry: OpenRouterModel,
    shape: RequestShape,
    *,
    prompt: str,
    reference: ProbedImage | None,
) -> CostEstimate:
    """The upper-bound price of one ``entry`` request of ``shape`` (formulas above).

    Raises:
        NoPriceOnRecordError: For a missing bound or an unknown unit / billable.
        TypeError: If ``shape`` is not an aspect-ratio shape.
    """
    from holiday_card.core.ai_assets import AspectSize

    if not isinstance(shape, AspectSize):
        raise TypeError(f"an OpenRouter request is sized by aspect ratio, not {shape!r}")

    def missing(reason: str) -> NoPriceOnRecordError:
        return NoPriceOnRecordError(entry.id, AIProvider.OPENROUTER, reason)

    n_refs = 0 if reference is None else 1
    total = 0.0
    lines: list[str] = []
    for row in entry.pricing:
        kind = (row.unit, "output" if row.billable == "output_image" else row.billable)
        match kind:
            case ("image", "output"):
                qty, unit, n = "1", "image", 1.0
            case ("image", "input_image" | "input_reference"):
                qty, unit, n = str(n_refs), "image", float(n_refs)
            case ("megapixel", "output"):
                if entry.max_output_megapixels is not None:
                    mp = entry.max_output_megapixels
                elif shape.resolution is not None:
                    mp = _tier_megapixels(shape.aspect_ratio, shape.resolution)
                else:
                    raise missing("megapixel-priced output with no max_output_megapixels or tier")
                qty, unit, n = f"{mp:.10g}", "MP", mp
            case ("megapixel", "input_image" | "input_reference"):
                mp = 0.0 if reference is None else reference.width_px * reference.height_px / 1e6
                qty, unit, n = f"{mp:.10g}", "MP", mp
            case ("token", "output"):
                key = shape.resolution or "default"
                tokens = entry.output_image_tokens
                if tokens is None or key not in tokens:
                    raise missing(f"no output_image_tokens bound for tier {key!r}")
                qty, unit, n = str(tokens[key]), "tok", float(tokens[key])
            case ("token", "input_image" | "input_reference"):
                if n_refs and entry.input_image_tokens is None:
                    raise missing("token-priced reference with no input_image_tokens bound")
                count = n_refs * (entry.input_image_tokens or 0)
                qty, unit, n = str(count), "tok", float(count)
            case ("token", "input_text"):
                count = len(prompt.encode("utf-8")) + _TEXT_TOKEN_OVERHEAD
                qty, unit, n = str(count), "tok", float(count)
            case _:
                raise missing(f"unsupported price row {row.billable}/{row.unit}")
        usd = row.cost_usd * n
        total += usd
        lines.append(_line(row, qty, unit, usd))
    text_tokens, text_rate = entry.output_text_tokens, entry.output_text_usd_per_token
    if text_tokens is not None and text_rate is not None:
        usd = text_rate * text_tokens
        total += usd
        lines.append(f"output_text: {text_tokens} tok x ${text_rate:g} = ${usd:.10g}")
    return CostEstimate(usd=total, lines=tuple(lines))


def estimate_max_cost(
    provider: AIProvider,
    model: str,
    shape: RequestShape,
    *,
    prompt: str,
    reference: ProbedImage | None,
) -> CostEstimate:
    """The upper-bound USD price of one ``provider`` / ``model`` request, offline.

    Raises:
        NoPriceOnRecordError: When a needed price or bound is not recorded.
    """
    match provider:
        case AIProvider.OPENROUTER:
            return estimate_openrouter_cost(
                openrouter_model(model), shape, prompt=prompt, reference=reference
            )
        case AIProvider.OPENAI:
            from holiday_card.core.ai_assets import MODEL_SIZE_POLICIES

            policy = MODEL_SIZE_POLICIES.get(model)
            if policy is None or policy.max_price_usd is None:
                raise NoPriceOnRecordError(
                    model, provider, "no verified max_price_usd in its size policy"
                )
            price = policy.max_price_usd
            return CostEstimate(
                usd=price, lines=(f"one request at the largest size: ${price:g}",)
            )
        case _:
            assert_never(provider)
