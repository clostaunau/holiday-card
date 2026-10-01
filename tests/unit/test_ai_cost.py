"""The offline ``--max-cost`` upper-bound estimate (issue #151, spec §6.7).

The worked moo-a6 examples use the committed allowlist entries, so a change
to any recorded price or bound fails a test here. Formula rows use
synthetic entries built from one valid base with ``dataclasses.replace``.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_parsers_properties import _SETTINGS

from holiday_card.core import ai_assets, ai_cost
from holiday_card.core.ai_assets import (
    MODEL_SIZE_POLICIES,
    AspectSize,
    PixelSize,
    build_ai_request,
)
from holiday_card.core.ai_cost import (
    TIER_LONG_EDGE_PX,
    CostCapExceededError,
    CostEstimate,
    NoPriceOnRecordError,
    check_cost_cap,
    estimate_max_cost,
    estimate_openrouter_cost,
)
from holiday_card.core.ai_openrouter_models import (
    OPENROUTER_IMAGE_MODELS,
    OpenRouterModel,
    OpenRouterPrice,
)
from holiday_card.core.ai_providers import AIProvider
from holiday_card.core.export_targets import REGISTRY
from holiday_card.core.images import ProbedImage

PROMPT = "watercolor pine bough border, sage green and burgundy"
REF_8 = ProbedImage(path=Path("ref.png"), format="png", width_px=8, height_px=8)
MOO_SHAPE_TIERED = AspectSize("3:4", "2K")
MOO_SHAPE_UNTIERED = AspectSize("3:4", None)
SOURCE = "2026-09-30 https://example.com/vendor-pricing"
OBSERVED = "2026-09-30 docs/industry-review/openrouter-image-api-snapshot.md (call A)"


def _entry(*prices: OpenRouterPrice, **changes: object) -> OpenRouterModel:
    base = OPENROUTER_IMAGE_MODELS["bytedance-seed/seedream-4.5"]
    unbounded: dict[str, object] = {
        "max_output_megapixels": None,
        "output_image_tokens": None,
        "input_image_tokens": None,
        "output_text_tokens": None,
        "output_text_usd_per_token": None,
        "bound_source": None,
    }
    return replace(
        base, id="test/synthetic", pricing=prices, **{**unbounded, **changes}  # type: ignore[arg-type]
    )


def _or(model: str, shape: AspectSize, *, reference: ProbedImage | None = REF_8) -> CostEstimate:
    return estimate_max_cost(AIProvider.OPENROUTER, model, shape, prompt=PROMPT, reference=reference)


# --------------------------------------------------------------------------- worked moo-a6 examples


class TestWorkedExamples:
    def test_moo_a6_request_is_3_4_at_2k(self) -> None:
        request = build_ai_request(
            prompt=PROMPT, trim_width_in=4.13, trim_height_in=5.83, bleed_in=0.125,
            provider=AIProvider.OPENROUTER, model="google/gemini-3-pro-image",
        )  # fmt: skip
        assert (request.width_px, request.height_px) == (1314, 1824)
        assert request.shape == MOO_SHAPE_TIERED

    def test_per_image_seedream(self) -> None:
        est = _or("bytedance-seed/seedream-4.5", MOO_SHAPE_TIERED)
        assert est.usd == pytest.approx(0.04, abs=1e-9)
        assert est.lines == (
            "output_image: 1 image x $0.04 = $0.04",
            "input_image: 1 image x $0 = $0",
        )
        check_cost_cap(est, 0.04)  # equal is allowed
        with pytest.raises(CostCapExceededError):
            check_cost_cap(est, 0.039)

    def test_per_megapixel_flux_uses_the_recorded_ceiling(self) -> None:
        # BFL: "up to 4MP (e.g., 2048x2048)"; the example itself is 4.194304 MP,
        # so the upper bound is 2048 x 2048, not a round 4.0.
        entry = OPENROUTER_IMAGE_MODELS["black-forest-labs/flux.2-pro"]
        assert entry.max_output_megapixels == pytest.approx(2048 * 2048 / 1e6, abs=1e-12)
        est = _or("black-forest-labs/flux.2-pro", MOO_SHAPE_UNTIERED)
        assert est.usd == pytest.approx(0.03 * 4.194304, abs=1e-9)
        assert f"${est.usd:.4f}" == "$0.1258"
        assert est.lines == ("output_image: 4.194304 MP x $0.03 = $0.12582912",)

    def test_per_megapixel_without_a_ceiling_or_tier_has_no_price(self) -> None:
        entry = replace(
            OPENROUTER_IMAGE_MODELS["black-forest-labs/flux.2-pro"],
            max_output_megapixels=None,
            bound_source=None,
        )
        with pytest.raises(NoPriceOnRecordError, match="max_output_megapixels"):
            estimate_openrouter_cost(entry, MOO_SHAPE_UNTIERED, prompt=PROMPT, reference=REF_8)

    def test_per_megapixel_with_tiers_synthetic(self) -> None:
        entry = _entry(OpenRouterPrice("output_image", "megapixel", 0.03))
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert est.usd == pytest.approx(0.03 * 3.145728, abs=1e-9)
        assert f"${est.usd:.4f}" == "$0.0944"
        # The ratio's short / long sides, not its orientation.
        flipped = estimate_openrouter_cost(
            entry, AspectSize("4:3", "2K"), prompt=PROMPT, reference=None
        )
        assert flipped.usd == pytest.approx(est.usd, abs=1e-12)

    def test_per_megapixel_tier_uses_the_observed_long_edge(self) -> None:
        # #174: an observed 2400 px long edge at 3:4 is 2400 x 1800, not 2048 x 1536.
        entry = _entry(
            OpenRouterPrice("output_image", "megapixel", 0.03),
            observed_long_edge_px=MappingProxyType({"2K": 2400}),
            observed_source=OBSERVED,
        )
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert est.usd == pytest.approx(0.03 * 4.32, abs=1e-9)

    def test_per_token_gemini_3_pro(self) -> None:
        est = _or("google/gemini-3-pro-image", MOO_SHAPE_TIERED)
        assert est.usd == pytest.approx(
            0.00012 * 1120 + 0.000002 * 560 + 0.000012 * 256, abs=1e-9
        )
        assert f"${est.usd:.4f}" == "$0.1386"
        assert est.lines == (
            "input_image: 560 tok x $2e-06 = $0.00112",
            "output_image: 1120 tok x $0.00012 = $0.1344",
            "output_text: 256 tok x $1.2e-05 = $0.003072",
        )
        check_cost_cap(est, 0.14)
        with pytest.raises(CostCapExceededError):
            check_cost_cap(est, 0.138)

    def test_per_token_with_text_synthetic(self) -> None:
        assert len(PROMPT.encode("utf-8")) == 53
        entry = _entry(OpenRouterPrice("input_text", "token", 0.000005))
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert est.usd == pytest.approx(0.000005 * (53 + 16), abs=1e-12)
        assert est.lines == ("input_text: 69 tok x $5e-06 = $0.000345",)

    def test_openai_direct_has_no_price_on_record(self) -> None:
        assert MODEL_SIZE_POLICIES["gpt-image-2"].max_price_usd is None
        with pytest.raises(NoPriceOnRecordError, match=r"gpt-image-2 \(openai\)"):
            estimate_max_cost(
                AIProvider.OPENAI, "gpt-image-2", PixelSize(1312, 1824), prompt=PROMPT, reference=None
            )


class TestRecordedBounds:
    """Every committed bound, so a silent edit fails here."""

    def test_bounds_match_the_cited_vendor_figures(self) -> None:
        bounds = {
            e.id: (e.max_output_megapixels, e.output_image_tokens and dict(e.output_image_tokens),
                   e.input_image_tokens)
            for e in OPENROUTER_IMAGE_MODELS.values()
        }  # fmt: skip
        assert bounds == {
            "google/gemini-3-pro-image": (None, {"1K": 1120, "2K": 1120, "4K": 2000}, 560),
            "google/gemini-3.1-flash-image": (
                None, {"512": 747, "1K": 1120, "2K": 1680, "4K": 2520}, None,
            ),  # fmt: skip
            "black-forest-labs/flux.2-pro": (2048 * 2048 / 1e6, None, None),
            "bytedance-seed/seedream-4.5": (None, None, None),
            "openai/gpt-image-2": (None, None, None),
            "openai/gpt-image-2.5-sunburst": (None, None, None),
        }

    def test_non_image_output_allowance_at_the_text_rate(self) -> None:
        # "$12.00 (text and thinking)" / "$1.50 (text and thinking)" per 1M
        # tokens; 256 is a margin over #140's observed 87 / 101 (#173).
        allowance = {
            e.id: (e.output_text_tokens, e.output_text_usd_per_token)
            for e in OPENROUTER_IMAGE_MODELS.values()
        }
        assert allowance == {
            "google/gemini-3-pro-image": (256, 0.000012),
            "google/gemini-3.1-flash-image": (256, 0.0000015),
            "black-forest-labs/flux.2-pro": (None, None),
            "bytedance-seed/seedream-4.5": (None, None),
            "openai/gpt-image-2": (None, None),
            "openai/gpt-image-2.5-sunburst": (None, None),
        }

    def test_flash_image_at_2k(self) -> None:
        est = _or("google/gemini-3.1-flash-image", MOO_SHAPE_TIERED)
        assert est.usd == pytest.approx(0.00006 * 1680 + 0.0000015 * 256, abs=1e-9)

    def test_gpt_image_2_via_openrouter_has_no_token_bound(self) -> None:
        with pytest.raises(NoPriceOnRecordError, match="openai/gpt-image-2"):
            _or("openai/gpt-image-2", MOO_SHAPE_UNTIERED)


class TestObservedGeminiCost:
    """#140's billed calls A / B (#173): the bound must cover the real cost."""

    @pytest.mark.parametrize(
        ("tier", "image_tokens", "completion_tokens", "observed_usd"),
        [("2K", 1120, 1207, 0.136002), ("4K", 2000, 2101, 0.241770)],
    )
    def test_estimate_covers_the_observed_cost(
        self, tier: str, image_tokens: int, completion_tokens: int, observed_usd: float
    ) -> None:
        entry = OPENROUTER_IMAGE_MODELS["google/gemini-3-pro-image"]
        assert entry.output_image_tokens is not None
        assert entry.output_image_tokens[tier] == image_tokens
        assert entry.output_text_tokens is not None
        assert completion_tokens - image_tokens <= entry.output_text_tokens
        est = _or("google/gemini-3-pro-image", AspectSize("3:4", tier))
        assert est.usd >= observed_usd
        check_cost_cap(est, est.usd)  # a cap at the estimate is not exceeded by the bill
        with pytest.raises(CostCapExceededError):
            check_cost_cap(est, observed_usd)


# --------------------------------------------------------------------------- one test per table row


class TestFormulaRows:
    def test_image_output_counts_one_image(self) -> None:
        entry = _entry(OpenRouterPrice("output_image", "image", 0.05))
        assert estimate_openrouter_cost(
            entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=REF_8
        ).usd == pytest.approx(0.05, abs=1e-12)

    @pytest.mark.parametrize("billable", ["input_image", "input_reference"])
    def test_image_input_counts_references(self, billable: str) -> None:
        entry = _entry(
            OpenRouterPrice("output_image", "image", 0.05),
            OpenRouterPrice(billable, "image", 0.01),  # type: ignore[arg-type]
        )
        with_ref = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=REF_8)
        without = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert with_ref.usd == pytest.approx(0.06, abs=1e-12)
        assert without.usd == pytest.approx(0.05, abs=1e-12)
        assert without.lines[1] == f"{billable}: 0 image x $0.01 = $0"

    def test_output_text_allowance_is_added_after_the_rows(self) -> None:
        entry = _entry(
            OpenRouterPrice("output_image", "image", 0.05),
            output_text_tokens=100,
            output_text_usd_per_token=0.00001,
            bound_source=SOURCE,
        )
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert est.usd == pytest.approx(0.051, abs=1e-12)
        assert est.lines[-1] == "output_text: 100 tok x $1e-05 = $0.001"

    def test_megapixel_output_prefers_the_recorded_ceiling_over_the_tier(self) -> None:
        entry = _entry(
            OpenRouterPrice("output_image", "megapixel", 0.03),
            max_output_megapixels=1.5,
            bound_source=SOURCE,
        )
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert est.usd == pytest.approx(0.045, abs=1e-12)

    @pytest.mark.parametrize("billable", ["input_image", "input_reference"])
    def test_megapixel_input_is_exact_from_the_probe(self, billable: str) -> None:
        entry = _entry(OpenRouterPrice(billable, "megapixel", 0.02))  # type: ignore[arg-type]
        ref = ProbedImage(path=Path("r.jpg"), format="jpeg", width_px=1200, height_px=1600)
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=ref)
        assert est.usd == pytest.approx(0.02 * 1.92, abs=1e-12)
        none = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert none.usd == 0

    def test_token_output_uses_the_tier_key(self) -> None:
        entry = _entry(
            OpenRouterPrice("output_image", "token", 0.0001),
            output_image_tokens=MappingProxyType({"1K": 100, "2K": 200, "4K": 400}),
            bound_source=SOURCE,
        )
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert est.usd == pytest.approx(0.02, abs=1e-12)

    def test_token_output_uses_default_without_a_tier(self) -> None:
        entry = _entry(
            OpenRouterPrice("output_image", "token", 0.0001),
            resolutions=(),
            output_image_tokens=MappingProxyType({"default": 300}),
            bound_source=SOURCE,
        )
        est = estimate_openrouter_cost(entry, MOO_SHAPE_UNTIERED, prompt=PROMPT, reference=None)
        assert est.usd == pytest.approx(0.03, abs=1e-12)

    def test_token_output_without_tokens_has_no_price(self) -> None:
        entry = _entry(OpenRouterPrice("output_image", "token", 0.0001))
        with pytest.raises(NoPriceOnRecordError, match="output_image_tokens"):
            estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)

    def test_token_output_missing_tier_key_has_no_price(self) -> None:
        entry = _entry(
            OpenRouterPrice("output_image", "token", 0.0001),
            output_image_tokens=MappingProxyType({"1K": 100}),
            bound_source=SOURCE,
        )
        with pytest.raises(NoPriceOnRecordError, match="2K"):
            estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)

    @pytest.mark.parametrize("billable", ["input_image", "input_reference"])
    def test_token_input_counts_reference_tokens(self, billable: str) -> None:
        entry = _entry(
            OpenRouterPrice(billable, "token", 0.00001),  # type: ignore[arg-type]
            input_image_tokens=500,
            bound_source=SOURCE,
        )
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=REF_8)
        assert est.usd == pytest.approx(0.005, abs=1e-12)

    def test_token_input_without_tokens_refuses_only_with_a_reference(self) -> None:
        entry = _entry(OpenRouterPrice("input_image", "token", 0.00001))
        with pytest.raises(NoPriceOnRecordError, match="input_image_tokens"):
            estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=REF_8)
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)
        assert est.usd == 0
        assert est.lines == ("input_image: 0 tok x $1e-05 = $0",)

    def test_prompt_is_counted_in_utf8_bytes(self) -> None:
        entry = _entry(OpenRouterPrice("input_text", "token", 1.0))
        est = estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt="é", reference=None)
        assert est.usd == 2 + 16

    @pytest.mark.parametrize(
        ("billable", "unit"),
        [
            ("input_text", "image"),
            ("input_text", "megapixel"),
            ("output_text", "token"),
            ("output_image", "second"),
        ],
    )
    def test_an_unknown_unit_or_billable_has_no_price(self, billable: str, unit: str) -> None:
        entry = _entry(OpenRouterPrice(billable, unit, 0.01))  # type: ignore[arg-type]
        with pytest.raises(NoPriceOnRecordError, match=f"{billable}.*{unit}|{unit}.*{billable}"):
            estimate_openrouter_cost(entry, MOO_SHAPE_TIERED, prompt=PROMPT, reference=None)

    def test_an_aspect_shape_is_required_for_openrouter(self) -> None:
        with pytest.raises(TypeError):
            estimate_max_cost(
                AIProvider.OPENROUTER, "google/gemini-3-pro-image", PixelSize(1024, 1024),
                prompt=PROMPT, reference=None,
            )  # fmt: skip


class TestOpenAI:
    def test_a_recorded_price_is_the_estimate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        policy = replace(MODEL_SIZE_POLICIES["gpt-image-2"], max_price_usd=0.42)
        monkeypatch.setitem(ai_assets.MODEL_SIZE_POLICIES, "gpt-image-2", policy)
        est = estimate_max_cost(
            AIProvider.OPENAI, "gpt-image-2", PixelSize(1312, 1824), prompt=PROMPT, reference=REF_8
        )
        assert est.usd == 0.42
        assert len(est.lines) == 1

    def test_every_openai_model_is_unpriced(self) -> None:
        # No verified per-request upper bound is recorded (issue #151 scope 3).
        assert all(p.max_price_usd is None for p in MODEL_SIZE_POLICIES.values())


class TestCap:
    def test_cap_error_carries_the_estimate_and_cap(self) -> None:
        est = CostEstimate(usd=0.2, lines=("x",))
        with pytest.raises(CostCapExceededError) as err:
            check_cost_cap(est, 0.1)
        assert err.value.estimate is est
        assert err.value.cap_usd == 0.1
        assert "$0.2000" in str(err.value) and "$0.10" in str(err.value)


# --------------------------------------------------------------------------- properties


_price = st.floats(min_value=0, max_value=1, allow_nan=False)
_bump = st.floats(min_value=0, max_value=1, allow_nan=False)
_tokens = st.integers(min_value=1, max_value=100_000)
_mp = st.floats(min_value=0.01, max_value=50, allow_nan=False)


@_SETTINGS
@given(
    prices=st.lists(_price, min_size=6, max_size=6),
    out_tokens=_tokens,
    in_tokens=_tokens,
    mp=_mp,
    which=st.integers(min_value=0, max_value=8),
    bump=_bump,
    with_ref=st.booleans(),
)
def test_estimate_is_non_negative_and_monotone(
    prices: list[float],
    out_tokens: int,
    in_tokens: int,
    mp: float,
    which: int,
    bump: float,
    with_ref: bool,
) -> None:
    def build(ps: list[float], ot: int, it: int, m: float) -> OpenRouterModel:
        return _entry(
            OpenRouterPrice("output_image", "image", ps[0]),
            OpenRouterPrice("output_image", "megapixel", ps[1]),
            OpenRouterPrice("output_image", "token", ps[2]),
            OpenRouterPrice("input_image", "megapixel", ps[3]),
            OpenRouterPrice("input_reference", "token", ps[4]),
            OpenRouterPrice("input_text", "token", ps[5]),
            max_output_megapixels=m,
            output_image_tokens=MappingProxyType({"1K": ot, "2K": ot, "4K": ot}),
            input_image_tokens=it,
            bound_source=SOURCE,
        )

    ref = REF_8 if with_ref else None
    before = estimate_openrouter_cost(
        build(prices, out_tokens, in_tokens, mp), MOO_SHAPE_TIERED, prompt=PROMPT, reference=ref
    ).usd
    bumped = list(prices)
    ot, it, m = out_tokens, in_tokens, mp
    if which < 6:
        bumped[which] += bump
    elif which == 6:
        ot += round(bump * 1000)
    elif which == 7:
        it += round(bump * 1000)
    else:
        m += bump
    after = estimate_openrouter_cost(
        build(bumped, ot, it, m), MOO_SHAPE_TIERED, prompt=PROMPT, reference=ref
    ).usd
    assert before >= 0
    assert after >= before


# --------------------------------------------------------------------------- drift guard + wiring


def test_every_entry_estimates_or_has_no_price_for_every_target() -> None:
    lacking: set[str] = set()
    targets = [t for t in REGISTRY.values() if t.geometry is not None]
    assert targets
    for entry in OPENROUTER_IMAGE_MODELS.values():
        for target in targets:
            geom = target.geometry
            assert geom is not None
            request = build_ai_request(
                prompt=PROMPT, trim_width_in=geom.trim_width_in,
                trim_height_in=geom.trim_height_in, bleed_in=geom.bleed_in,
                provider=AIProvider.OPENROUTER, model=entry.id,
            )  # fmt: skip
            for ref in (REF_8, None):
                try:
                    est = estimate_max_cost(
                        AIProvider.OPENROUTER, entry.id, request.shape, prompt=PROMPT, reference=ref
                    )
                except NoPriceOnRecordError:
                    lacking.add(entry.id)
                else:
                    assert est.usd >= 0 and est.lines
    print(f"entries without a complete --max-cost bound: {sorted(lacking) or 'none'}")
    # sunburst (#179) is priced like gpt-image-2: no cited bound for either.
    assert lacking == {"openai/gpt-image-2", "openai/gpt-image-2.5-sunburst"}


def test_tier_table_is_the_choosers_table() -> None:
    assert TIER_LONG_EDGE_PX is ai_assets.RESOLUTION_LONG_EDGE_PX


def test_import_loads_only_the_standard_library() -> None:
    code = (
        "import sys\n"
        "import holiday_card\n"
        "before = set(sys.modules)\n"
        "import holiday_card.core.ai_cost\n"
        "added = set(sys.modules) - before\n"
        "third = sorted(m for m in added if m.split('.')[0] not in sys.stdlib_module_names\n"
        "               and not m.startswith('holiday_card'))\n"
        "assert not third, third\n"
        "bad = [m for m in ('PIL', 'openai', 'urllib.request') if m in added]\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_module_exports() -> None:
    assert set(ai_cost.__all__) >= {
        "CostEstimate", "NoPriceOnRecordError", "CostCapExceededError",
        "TIER_LONG_EDGE_PX", "estimate_max_cost",
    }  # fmt: skip
