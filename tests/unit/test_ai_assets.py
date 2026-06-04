"""POD-aware sizing + generate-orchestration tests for AI imagery.

Covers ``build_ai_request`` (resolve print geometry to pixel dims at
300 DPI rounded to /16) and ``generate_ai_asset`` (the authoring-time
orchestration: consent → rails → client call → sRGB-tagged PNG +
provenance sidecar). The model call is injected as a fake client, so no
network and no ``OPENAI_API_KEY`` are needed — the panel's
"authoring-time bake to disk, never render-time" shape (Agreement A2).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image

from holiday_card.core.ai_assets import (
    AIRequest,
    ConsentRequiredError,
    GeneratedImage,
    RailRefusedError,
    build_ai_request,
    generate_ai_asset,
    round_to_multiple,
)
from holiday_card.core.ai_provenance import read_sidecar, record_consent
from holiday_card.core.models import OccasionType

# --- Fake injectable client -------------------------------------------------


@dataclass
class FakeImageClient:
    """Records the request and returns a solid PNG of the requested size."""

    calls: list[dict] | None = None

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        width_px: int,
        height_px: int,
        moderation: str,
        seed: int | None,
    ) -> GeneratedImage:
        if self.calls is None:
            self.calls = []
        self.calls.append(
            {
                "prompt": prompt,
                "reference_path": reference_path,
                "width_px": width_px,
                "height_px": height_px,
                "moderation": moderation,
                "seed": seed,
            }
        )
        buf = io.BytesIO()
        Image.new("RGB", (width_px, height_px), (10, 120, 60)).save(buf, format="PNG")
        return GeneratedImage(png_bytes=buf.getvalue(), cost_usd=0.04, model_version="2027-01")


def _consented(tmp_path: Path) -> Path:
    path = tmp_path / "ai-consent.json"
    record_consent(path)
    return path


def _small_request() -> AIRequest:
    return AIRequest(
        prompt="watercolor pine bough border",
        width_px=64,
        height_px=96,
        dpi=300,
        reference_path="ref.png",
        moderation="auto",
    )


# --- Sizing -----------------------------------------------------------------


class TestRounding:
    def test_rounds_to_nearest_multiple_of_16(self) -> None:
        assert round_to_multiple(1000) == 1008  # 62.5 -> 63 * 16
        assert round_to_multiple(1024) == 1024
        assert round_to_multiple(8) == 16  # never round to zero


class TestBuildAIRequest:
    def test_resolves_trim_plus_bleed_at_300_dpi_rounded_to_16(self) -> None:
        # MOO A6: trim 4.13x5.83 + 0.125 bleed each side, generate at
        # trim + 2*bleed so the model paints into the bleed band.
        req = build_ai_request(
            prompt="x",
            trim_width_in=4.13,
            trim_height_in=5.83,
            bleed_in=0.125,
            dpi=300,
        )
        # 4.38in * 300 = 1314 -> /16 nearest = 1312
        assert req.width_px == 1312
        # 6.08in * 300 = 1824 -> already /16
        assert req.height_px == 1824
        assert req.dpi == 300
        assert req.moderation == "auto"

    def test_is_deterministic(self) -> None:
        kwargs = {"prompt": "x", "trim_width_in": 4.13, "trim_height_in": 5.83, "bleed_in": 0.125}
        assert build_ai_request(**kwargs) == build_ai_request(**kwargs)


# --- Orchestration ----------------------------------------------------------


class TestGenerateHappyPath:
    def test_writes_srgb_png_and_sidecar(self, tmp_path: Path) -> None:
        out = tmp_path / "border.png"
        client = FakeImageClient()
        result = generate_ai_asset(
            prompt="watercolor pine bough border",
            occasion=OccasionType.CHRISTMAS,
            out_path=out,
            request=_small_request(),
            client=client,
            style="watercolor",
            seed=42,
            timestamp="2027-01-15T10:00:00Z",
            consent_path=_consented(tmp_path),
        )

        # PNG written at the requested size and tagged sRGB.
        assert out.exists()
        with Image.open(out) as img:
            assert img.size == (64, 96)
            assert img.info.get("icc_profile")  # sRGB tag embedded

        # Sidecar written with provenance.
        record = read_sidecar(out)
        assert record.prompt == "watercolor pine bough border"
        assert record.seed == 42
        assert record.cost_usd == 0.04
        assert record.model_version == "2027-01"
        assert record.color_profile == "sRGB IEC61966-2.1"

        assert result.cost_usd == 0.04
        assert result.asset_path == out
        assert result.overridden == []

    def test_passes_moderation_auto_to_client(self, tmp_path: Path) -> None:
        client = FakeImageClient()
        generate_ai_asset(
            prompt="balloons",
            occasion=OccasionType.BIRTHDAY,
            out_path=tmp_path / "b.png",
            request=_small_request(),
            client=client,
            timestamp="2027-01-15T10:00:00Z",
            consent_path=_consented(tmp_path),
        )
        assert client.calls is not None
        assert client.calls[0]["moderation"] == "auto"


class TestConsentEnforced:
    def test_refuses_without_consent(self, tmp_path: Path) -> None:
        with pytest.raises(ConsentRequiredError):
            generate_ai_asset(
                prompt="balloons",
                occasion=OccasionType.BIRTHDAY,
                out_path=tmp_path / "b.png",
                request=_small_request(),
                client=FakeImageClient(),
                timestamp="2027-01-15T10:00:00Z",
                consent_path=tmp_path / "absent.json",
            )


class TestRailsEnforced:
    def test_refuses_sympathy_occasion_by_default(self, tmp_path: Path) -> None:
        client = FakeImageClient()
        with pytest.raises(RailRefusedError) as exc:
            generate_ai_asset(
                prompt="a calm field",
                occasion=OccasionType.SYMPATHY,
                out_path=tmp_path / "s.png",
                request=_small_request(),
                client=client,
                timestamp="2027-01-15T10:00:00Z",
                consent_path=_consented(tmp_path),
            )
        assert any(v.category == "occasion" for v in exc.value.violations)
        # The model was never called — fail before spending money.
        assert not client.calls
        assert not (tmp_path / "s.png").exists()

    def test_refuses_trademark_prompt_by_default(self, tmp_path: Path) -> None:
        with pytest.raises(RailRefusedError):
            generate_ai_asset(
                prompt="mickey mouse in a santa hat",
                occasion=OccasionType.CHRISTMAS,
                out_path=tmp_path / "m.png",
                request=_small_request(),
                client=FakeImageClient(),
                timestamp="2027-01-15T10:00:00Z",
                consent_path=_consented(tmp_path),
            )

    def test_override_proceeds_and_records_reasons(self, tmp_path: Path) -> None:
        out = tmp_path / "s.png"
        result = generate_ai_asset(
            prompt="a calm field",
            occasion=OccasionType.SYMPATHY,
            out_path=out,
            request=_small_request(),
            client=FakeImageClient(),
            timestamp="2027-01-15T10:00:00Z",
            consent_path=_consented(tmp_path),
            override=True,
        )
        assert out.exists()
        assert any(v.category == "occasion" for v in result.overridden)
        # Override reasons are persisted into the sidecar for audit.
        record = read_sidecar(out)
        assert record.override_reasons
