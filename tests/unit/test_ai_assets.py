"""POD-aware sizing + generate-orchestration tests for AI imagery.

Covers ``build_ai_request`` (resolve print geometry to the exact baked
size at 300 PPI plus a model-supported request size, issue #87) and ``generate_ai_asset`` (the authoring-time
orchestration: consent → rails → client call → sRGB-tagged PNG +
provenance sidecar). The model call is injected as a fake client, so no
network and no ``OPENAI_API_KEY`` are needed — the panel's
"authoring-time bake to disk, never render-time" shape (Agreement A2).
"""

from __future__ import annotations

import base64
import io
import struct
import zlib
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import EpsImagePlugin, Image, ImageFile

from holiday_card.core.ai_assets import (
    MAX_IMAGE_BYTES,
    MODEL_SIZE_POLICIES,
    RESOLUTION_LONG_EDGE_PX,
    AIRequest,
    AspectSize,
    ConsentRequiredError,
    GeneratedImage,
    ImageMediaType,
    ImagePayloadError,
    ModelSizePolicy,
    PixelSize,
    RailRefusedError,
    RequestShape,
    aspect_ratio_value,
    build_ai_request,
    choose_aspect_shape,
    choose_request_shape,
    choose_request_size,
    decode_b64_image,
    generate_ai_asset,
    open_generated_image,
    size_is_allowed,
)
from holiday_card.core.ai_openrouter_models import (
    OPENROUTER_IMAGE_MODELS,
    openrouter_model,
)
from holiday_card.core.ai_provenance import read_sidecar, record_consent
from holiday_card.core.ai_providers import AIProvider
from holiday_card.core.export_targets import REGISTRY
from holiday_card.core.images import MAX_IMAGE_PIXELS
from holiday_card.core.models import OccasionType

# --- Fake injectable client -------------------------------------------------


@dataclass
class FakeImageClient:
    """Records the size it was sent; returns a solid image of ``returns`` or that size.

    ``fmt`` / ``media_type`` pick the encoding, ``raw`` replaces the bytes
    outright, and ``cost_usd=None`` is a provider that reports no cost.
    """

    calls: list[dict] | None = None
    model: str = "gpt-image-2"
    provider: AIProvider = AIProvider.OPENAI
    returns: tuple[int, int] | None = None
    image: Image.Image | None = None
    fmt: str = "PNG"
    media_type: ImageMediaType = "image/png"
    raw: bytes | None = None
    cost_usd: float | None = 0.13

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        shape: RequestShape,
        seed: int | None,
    ) -> GeneratedImage:
        if self.calls is None:
            self.calls = []
        self.calls.append(
            {"prompt": prompt, "reference_path": reference_path, "shape": shape, "seed": seed}
        )
        assert isinstance(shape, PixelSize)
        buf = io.BytesIO()
        size = self.returns or (shape.width_px, shape.height_px)
        img = self.image or Image.new("RGB", size, (10, 120, 60))
        img.save(buf, format=self.fmt)
        return GeneratedImage(
            image_bytes=self.raw if self.raw is not None else buf.getvalue(),
            media_type=self.media_type,
            cost_usd=self.cost_usd,
            cost_source="reported" if self.cost_usd is not None else "unknown",
            model_version="2027-01",
        )


def _consented(tmp_path: Path) -> Path:
    path = tmp_path / "ai-consent.json"
    record_consent(path)
    return path


def _small_request() -> AIRequest:
    return AIRequest(
        prompt="watercolor pine bough border",
        width_px=64,
        height_px=96,
        shape=PixelSize(64, 96),
        provider=AIProvider.OPENAI,
        model="gpt-image-2",
        dpi=300,
        reference_path="ref.png",
    )


# --- Sizing -----------------------------------------------------------------


class TestBuildAIRequest:
    def test_target_is_exact_trim_plus_bleed_at_300_dpi(self) -> None:
        # MOO A6: trim 4.13x5.83 + 0.125 bleed each side, generate at
        # trim + 2*bleed so the model paints into the bleed band.
        req = build_ai_request(
            prompt="x",
            trim_width_in=4.13,
            trim_height_in=5.83,
            bleed_in=0.125,
            dpi=300,
            provider=AIProvider.OPENAI,
            model="gpt-image-2",
        )
        # 4.38in * 300 = 1314 and 6.08in * 300 = 1824: the baked file is
        # exactly this, not /16-rounded (1312 would be 299.5 PPI).
        assert (req.width_px, req.height_px) == (1314, 1824)
        assert req.dpi == 300

    def test_flexible_model_shape_is_rounded_up_to_16(self) -> None:
        req = build_ai_request(
            prompt="x",
            trim_width_in=4.13,
            trim_height_in=5.83,
            bleed_in=0.125,
            provider=AIProvider.OPENAI,
            model="gpt-image-2",
        )
        assert (req.provider, req.model) == (AIProvider.OPENAI, "gpt-image-2")
        # Rounded up to /16 so the request never under-resolves the target.
        assert req.shape == PixelSize(1328, 1824)
        assert size_is_allowed("gpt-image-2", req.shape.width_px, req.shape.height_px)

    def test_fixed_size_model_gets_its_closest_aspect(self) -> None:
        req = build_ai_request(
            prompt="x",
            trim_width_in=4.13,
            trim_height_in=5.83,
            bleed_in=0.125,
            provider=AIProvider.OPENAI,
            model="gpt-image-1",
        )
        assert req.shape == PixelSize(1024, 1536)
        assert (req.width_px, req.height_px) == (1314, 1824)

    def test_provider_and_model_are_required(self) -> None:
        with pytest.raises(TypeError):
            build_ai_request(prompt="x", trim_width_in=4.13, trim_height_in=5.83)  # type: ignore[call-arg]

    def test_is_deterministic(self) -> None:
        kwargs = {
            "prompt": "x",
            "trim_width_in": 4.13,
            "trim_height_in": 5.83,
            "bleed_in": 0.125,
            "provider": AIProvider.OPENAI,
            "model": "gpt-image-2",
        }
        assert build_ai_request(**kwargs) == build_ai_request(**kwargs)


class TestChooseRequestShape:
    @pytest.mark.parametrize("model", sorted(MODEL_SIZE_POLICIES))
    @pytest.mark.parametrize("target", [(1314, 1824), (2550, 3300)], ids=["moo-a6", "letter"])
    def test_openai_shape_is_the_pixel_size(self, model: str, target: tuple[int, int]) -> None:
        shape = choose_request_shape(AIProvider.OPENAI, model, *target)
        assert shape == PixelSize(*choose_request_size(model, *target))

    def test_unknown_model_raises(self) -> None:
        with pytest.raises(ValueError, match="dall-e-9"):
            choose_request_shape(AIProvider.OPENAI, "dall-e-9", 1314, 1824)

    def test_aspect_size_is_a_request_shape(self) -> None:
        shape: RequestShape = AspectSize("3:4", "2K")
        assert (shape.aspect_ratio, shape.resolution) == ("3:4", "2K")


def _target_px(name: str) -> tuple[int, int]:
    geom = REGISTRY[name].geometry
    assert geom is not None
    req = build_ai_request(
        prompt="x",
        trim_width_in=geom.trim_width_in,
        trim_height_in=geom.trim_height_in,
        bleed_in=geom.bleed_in,
        provider=AIProvider.OPENAI,
        model="gpt-image-2",
    )
    return req.width_px, req.height_px


_GEOMETRY_TARGETS = sorted(name for name, t in REGISTRY.items() if t.geometry is not None)
_GEMINI_PRO = "google/gemini-3-pro-image"


class TestChooseAspectShape:
    """OpenRouter sizing: nearest aspect in log space, then a resolution tier (#148)."""

    @pytest.mark.parametrize(
        ("ratio", "value"),
        [("3:4", 0.75), ("9:19.5", 9 / 19.5), ("19.5:9", 19.5 / 9), ("2.35:1", 2.35), ("1:1", 1.0)],
    )
    def test_aspect_ratio_value(self, ratio: str, value: float) -> None:
        assert aspect_ratio_value(ratio) == pytest.approx(value)

    @pytest.mark.parametrize(
        "ratio", ["auto", "", "3", "0:4", "3:0", "a:b", "-3:4", "inf:1", "nan:1", "1:2:3", ":4"]
    )
    def test_aspect_ratio_value_refuses(self, ratio: str) -> None:
        with pytest.raises(ValueError, match="aspect ratio"):
            aspect_ratio_value(ratio)

    def test_resolution_tiers(self) -> None:
        assert dict(RESOLUTION_LONG_EDGE_PX) == {
            "512": 512,
            "768": 768,
            "1K": 1024,
            "2K": 2048,
            "4K": 4096,
        }

    def test_target_sizes(self) -> None:
        assert _target_px("letter") == (2550, 3300)
        assert _target_px("moo-a6") == (1314, 1824)

    @pytest.mark.parametrize("target", _GEOMETRY_TARGETS)
    @pytest.mark.parametrize("model", sorted(OPENROUTER_IMAGE_MODELS))
    def test_chosen_shape_is_advertised_by_the_pinned_endpoint(
        self, model: str, target: str
    ) -> None:
        entry = OPENROUTER_IMAGE_MODELS[model]
        shape = choose_aspect_shape(entry, *_target_px(target))
        assert shape.aspect_ratio in entry.aspect_ratios
        if entry.resolutions:
            assert shape.resolution in entry.resolutions
        else:
            assert shape.resolution is None

    @pytest.mark.parametrize("model", sorted(OPENROUTER_IMAGE_MODELS))
    @pytest.mark.parametrize("target", ["letter", "moo-a6"])
    def test_every_curated_model_picks_3_4_for_portrait_targets(
        self, model: str, target: str
    ) -> None:
        shape = choose_aspect_shape(OPENROUTER_IMAGE_MODELS[model], *_target_px(target))
        assert shape.aspect_ratio == "3:4"

    def test_gemini_pro_moo_a6(self) -> None:
        assert choose_aspect_shape(openrouter_model(_GEMINI_PRO), 1314, 1824) == AspectSize("3:4", "2K")

    def test_gemini_pro_letter(self) -> None:
        assert choose_aspect_shape(openrouter_model(_GEMINI_PRO), 2550, 3300) == AspectSize("3:4", "4K")

    def test_flux_has_no_resolution(self) -> None:
        entry = openrouter_model("black-forest-labs/flux.2-pro")
        assert choose_aspect_shape(entry, 1314, 1824) == AspectSize("3:4", None)

    def test_landscape(self) -> None:
        assert choose_aspect_shape(openrouter_model(_GEMINI_PRO), 1824, 1314).aspect_ratio == "4:3"

    def test_decimal_ratio_is_reachable(self) -> None:
        entry = openrouter_model("bytedance-seed/seedream-4.5")
        assert choose_aspect_shape(entry, 900, 1950).aspect_ratio == "9:19.5"

    @pytest.mark.parametrize(
        ("ratios", "expected"),
        [
            (("4:3", "3:4"), "3:4"),
            (("3:4", "4:3"), "3:4"),
            (("2:1", "1:2"), "1:2"),
            (("1:2", "2:1"), "1:2"),
        ],
    )
    def test_tie_goes_to_the_narrower_ratio_in_any_order(
        self, ratios: tuple[str, ...], expected: str
    ) -> None:
        entry = replace(openrouter_model(_GEMINI_PRO), aspect_ratios=ratios)
        assert choose_aspect_shape(entry, 1000, 1000).aspect_ratio == expected

    def test_equal_values_tie_on_the_string(self) -> None:
        entry = replace(openrouter_model(_GEMINI_PRO), aspect_ratios=("6:8", "3:4"))
        assert choose_aspect_shape(entry, 1314, 1824).aspect_ratio == "3:4"

    def test_reversed_catalogue_order_gives_the_same_shape(self) -> None:
        for entry in OPENROUTER_IMAGE_MODELS.values():
            flipped = replace(
                entry,
                aspect_ratios=entry.aspect_ratios[::-1],
                resolutions=entry.resolutions[::-1],
            )
            for size in [(1314, 1824), (2550, 3300), (1824, 1314), (1000, 1000)]:
                assert choose_aspect_shape(flipped, *size) == choose_aspect_shape(entry, *size)

    def test_resolution_falls_back_to_the_largest_tier(self) -> None:
        entry = replace(openrouter_model(_GEMINI_PRO), resolutions=("1K", "2K"))
        assert choose_aspect_shape(entry, 2550, 3300).resolution == "2K"

    def test_resolution_is_the_smallest_tier_that_covers_the_long_edge(self) -> None:
        entry = replace(openrouter_model(_GEMINI_PRO), resolutions=("512", "1K", "2K"))
        assert choose_aspect_shape(entry, 1000, 1000).resolution == "1K"
        assert choose_aspect_shape(entry, 1024, 500).resolution == "1K"
        assert choose_aspect_shape(entry, 1025, 500).resolution == "2K"


class TestModelSizePolicy:
    @pytest.mark.parametrize("model", ["gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5"])
    def test_legacy_models_are_fixed_size(self, model: str) -> None:
        assert MODEL_SIZE_POLICIES[model].fixed_sizes == (
            (1024, 1024),
            (1536, 1024),
            (1024, 1536),
        )

    def test_fixed_model_picks_closest_aspect(self) -> None:
        assert choose_request_size("gpt-image-1", 1314, 1824) == (1024, 1536)
        assert choose_request_size("gpt-image-1", 1824, 1314) == (1536, 1024)
        assert choose_request_size("gpt-image-1", 900, 1000) == (1024, 1024)

    def test_fixed_model_tie_goes_to_larger_area(self) -> None:
        policy = ModelSizePolicy(model="m", fixed_sizes=((100, 100), (200, 200)))
        MODEL_SIZE_POLICIES["test-tie"] = policy
        try:
            assert choose_request_size("test-tie", 50, 50) == (200, 200)
        finally:
            del MODEL_SIZE_POLICIES["test-tie"]

    def test_flexible_valid_size_passes_through(self) -> None:
        assert choose_request_size("gpt-image-2", 1312, 1824) == (1312, 1824)

    def test_flexible_off_grid_size_rounds_up_to_multiple(self) -> None:
        assert choose_request_size("gpt-image-2", 1314, 1824) == (1328, 1824)

    def test_flexible_oversize_is_scaled_into_limits(self) -> None:
        policy = MODEL_SIZE_POLICIES["gpt-image-2"]
        w, h = choose_request_size("gpt-image-2", 4000, 1000)
        assert policy.max_edge is not None and max(w, h) <= policy.max_edge
        assert policy.max_aspect is not None and max(w, h) / min(w, h) <= policy.max_aspect
        assert w % 16 == 0 and h % 16 == 0
        assert size_is_allowed("gpt-image-2", w, h)

    def test_flexible_too_many_pixels_is_scaled_down(self) -> None:
        w, h = choose_request_size("gpt-image-2", 3600, 3600)
        assert size_is_allowed("gpt-image-2", w, h)
        assert abs(w - h) <= 16

    def test_flexible_too_few_pixels_is_scaled_up(self) -> None:
        w, h = choose_request_size("gpt-image-2", 64, 96)
        assert size_is_allowed("gpt-image-2", w, h)
        assert w * h >= 655_360

    def test_unknown_model_raises(self) -> None:
        with pytest.raises(ValueError, match="no-such-model"):
            choose_request_size("no-such-model", 1314, 1824)
        with pytest.raises(ValueError, match="no-such-model"):
            size_is_allowed("no-such-model", 1024, 1024)

    def test_size_is_allowed(self) -> None:
        assert size_is_allowed("gpt-image-1", 1024, 1536)
        assert not size_is_allowed("gpt-image-1", 1312, 1824)
        assert size_is_allowed("gpt-image-2", 1312, 1824)
        assert not size_is_allowed("gpt-image-2", 1314, 1824)  # not /16
        assert not size_is_allowed("gpt-image-2", 3840, 1024)  # aspect > 3
        assert not size_is_allowed("gpt-image-2", 4096, 2048)  # edge > 3840
        assert not size_is_allowed("gpt-image-2", 512, 512)  # < min pixels


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
        assert record.cost_usd == 0.13
        assert record.cost_source == "reported"
        assert record.model_version == "2027-01"
        assert record.color_profile == "sRGB IEC61966-2.1"

        assert result.cost_usd == 0.13
        assert result.cost_source == "reported"
        assert result.asset_path == out
        assert result.overridden == []

    def test_passes_the_request_shape_to_the_client(self, tmp_path: Path) -> None:
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
        assert client.calls[0]["shape"] == PixelSize(64, 96)

    def test_request_for_another_model_is_refused_before_the_call(self, tmp_path: Path) -> None:
        client = FakeImageClient(model="gpt-image-2")
        request = replace(_small_request(), model="gpt-image-1")
        out = tmp_path / "b.png"
        with pytest.raises(ValueError, match="gpt-image-1"):
            generate_ai_asset(
                prompt="balloons",
                occasion=OccasionType.BIRTHDAY,
                out_path=out,
                request=request,
                client=client,
                timestamp="2027-01-15T10:00:00Z",
                consent_path=_consented(tmp_path),
            )
        assert client.calls is None
        assert not out.exists()


class TestResampleToTarget:
    def _moo_a6_run(self, tmp_path: Path, client: FakeImageClient) -> Path:
        out = tmp_path / "moo.png"
        generate_ai_asset(
            prompt="watercolor pine bough border",
            occasion=OccasionType.CHRISTMAS,
            out_path=out,
            request=build_ai_request(
                prompt="watercolor pine bough border",
                trim_width_in=4.13,
                trim_height_in=5.83,
                bleed_in=0.125,
                provider=client.provider,
                model=client.model,
            ),
            client=client,
            timestamp="2027-01-15T10:00:00Z",
            consent_path=_consented(tmp_path),
        )
        return out

    def test_fixed_size_output_is_resampled_to_the_exact_target(self, tmp_path: Path) -> None:
        client = FakeImageClient(model="gpt-image-1", returns=(1024, 1536))
        out = self._moo_a6_run(tmp_path, client)

        assert client.calls is not None
        assert client.calls[0]["shape"] == PixelSize(1024, 1536)
        with Image.open(out) as img:
            assert img.size == (1314, 1824)
            assert img.info["dpi"] == pytest.approx((300, 300), abs=0.01)
            assert img.info.get("icc_profile")

        record = read_sidecar(out)
        assert (record.width_px, record.height_px) == (1314, 1824)
        assert (record.generated_width_px, record.generated_height_px) == (1024, 1536)
        assert record.native_ppi == pytest.approx(233.8, abs=0.05)
        assert record.model == "gpt-image-1"

    def test_flexible_output_is_cropped_not_scaled(self, tmp_path: Path) -> None:
        client = FakeImageClient(model="gpt-image-2")
        out = self._moo_a6_run(tmp_path, client)

        assert client.calls is not None
        assert client.calls[0]["shape"] == PixelSize(1328, 1824)
        with Image.open(out) as img:
            assert img.size == (1314, 1824)
        record = read_sidecar(out)
        assert record.native_ppi == pytest.approx(300.0)
        assert record.model == "gpt-image-2"

    def test_cover_crop_keeps_the_centre(self, tmp_path: Path) -> None:
        # A 2:1 source with a red left half, green centre, blue right half:
        # cropping to the portrait target keeps only the green centre.
        img = Image.new("RGB", (1536, 1024), (0, 200, 0))
        img.paste((200, 0, 0), (0, 0, 384, 1024))
        img.paste((0, 0, 200), (1152, 0, 1536, 1024))

        out = self._moo_a6_run(tmp_path, FakeImageClient(model="gpt-image-1", image=img))
        with Image.open(out) as img:
            rgb = img.convert("RGB")
            assert rgb.getpixel((2, 900)) == (0, 200, 0)
            assert rgb.getpixel((1311, 900)) == (0, 200, 0)


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


# --- Model output is untrusted (#141) ---------------------------------------


def _encoded(fmt: str, size: tuple[int, int] = (16, 16), **save: object) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 120, 60)).save(buf, format=fmt, **save)
    return buf.getvalue()


def _animated(fmt: str) -> bytes:
    buf = io.BytesIO()
    frames = [Image.new("RGB", (16, 16), c) for c in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(buf, format=fmt, save_all=True, append_images=frames[1:])
    return buf.getvalue()


def _png_with_ihdr(width: int, height: int) -> bytes:
    """A tiny PNG whose header claims ``width``×``height`` (one short IDAT)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00" * 64))
        + chunk(b"IEND", b"")
    )


_EPS = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n"


@pytest.fixture
def no_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if any raster is decoded."""

    def refuse(_self: object) -> None:
        raise AssertionError("the raster was decoded")

    monkeypatch.setattr(ImageFile.ImageFile, "load", refuse)


class TestGeneratedImage:
    def test_reported_cost_requires_a_value(self) -> None:
        with pytest.raises(ValueError, match="cost_source"):
            GeneratedImage(image_bytes=b"", media_type="image/png", cost_usd=None, cost_source="reported")

    def test_unknown_cost_must_have_no_value(self) -> None:
        with pytest.raises(ValueError, match="cost_source"):
            GeneratedImage(image_bytes=b"", media_type="image/png", cost_usd=0.1, cost_source="unknown")


class TestDecodeB64Image:
    def test_round_trip(self) -> None:
        raw = _encoded("PNG")
        assert decode_b64_image(base64.b64encode(raw).decode()) == raw

    def test_non_alphabet_characters_are_refused(self) -> None:
        good = base64.b64encode(_encoded("PNG")).decode()
        with pytest.raises(ImagePayloadError, match="base64"):
            decode_b64_image(good[:8] + "!*" + good[8:])

    def test_oversize_is_refused_before_decoding(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_args: object, **_kwargs: object) -> bytes:
            raise AssertionError("b64decode was called")

        monkeypatch.setattr(base64, "b64decode", boom)
        with pytest.raises(ImagePayloadError, match="1024"):
            decode_b64_image("A" * (4 * -(-1024 // 3) + 4), max_bytes=1024)

    def test_default_cap_is_32_mib(self) -> None:
        assert MAX_IMAGE_BYTES == 32 * 1024 * 1024


class TestOpenGeneratedImage:
    @pytest.mark.parametrize(
        ("fmt", "media_type"),
        [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")],
    )
    def test_valid_image_opens_as_rgb(self, fmt: str, media_type: ImageMediaType) -> None:
        img = open_generated_image(_encoded(fmt), media_type)
        assert img.mode == "RGB"
        assert img.size == (16, 16)

    def test_eps_is_refused_without_ghostscript(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def ghostscript(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("Ghostscript was invoked")

        monkeypatch.setattr(EpsImagePlugin, "Ghostscript", ghostscript)
        with pytest.raises(ImagePayloadError):
            open_generated_image(_EPS, "image/png")

    def test_gif_is_refused(self) -> None:
        with pytest.raises(ImagePayloadError):
            open_generated_image(_encoded("GIF"), "image/png")

    def test_declared_type_must_match_the_bytes(self) -> None:
        with pytest.raises(ImagePayloadError, match="image/jpeg"):
            open_generated_image(_encoded("PNG"), "image/jpeg")

    @pytest.mark.parametrize(("fmt", "media_type"), [("PNG", "image/png"), ("WEBP", "image/webp")])
    def test_animated_image_is_refused(self, fmt: str, media_type: ImageMediaType) -> None:
        with pytest.raises(ImagePayloadError, match="frames"):
            open_generated_image(_animated(fmt), media_type)

    @pytest.mark.usefixtures("no_load")
    def test_decompression_bomb_is_refused_before_decoding(self) -> None:
        with pytest.raises(ImagePayloadError):
            open_generated_image(_png_with_ihdr(20000, 20000), "image/png")

    @pytest.mark.usefixtures("no_load")
    def test_our_pixel_cap_applies_below_pillows_threshold(self) -> None:
        assert MAX_IMAGE_PIXELS < 8000 * 7000
        assert Image.MAX_IMAGE_PIXELS > 8000 * 7000
        with pytest.raises(ImagePayloadError, match="megapixels"):
            open_generated_image(_png_with_ihdr(8000, 7000), "image/png")

    def test_truncated_image_is_refused(self) -> None:
        raw = _encoded("PNG", (64, 64))
        with pytest.raises(ImagePayloadError):
            open_generated_image(raw[: len(raw) // 2], "image/png")

    def test_message_never_echoes_the_payload(self) -> None:
        with pytest.raises(ImagePayloadError) as info:
            open_generated_image(b"SECRET-PAYLOAD-BYTES" * 4, "image/png")
        assert "SECRET" not in str(info.value)


_MAGIC = st.sampled_from([b"", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF\x00\x00\x00\x00WEBPVP8 "])


@settings(max_examples=200, deadline=None)
@given(
    prefix=_MAGIC,
    body=st.binary(max_size=512),
    media_type=st.sampled_from(["image/png", "image/jpeg", "image/webp"]),
)
def test_open_generated_image_returns_or_refuses(
    prefix: bytes, body: bytes, media_type: ImageMediaType
) -> None:
    try:
        img = open_generated_image(prefix + body, media_type)
    except ImagePayloadError:
        return
    assert img.mode == "RGB"


_SEEDS: dict[ImageMediaType, bytes] = {
    "image/png": _encoded("PNG", (24, 24)),
    "image/jpeg": _encoded("JPEG", (24, 24)),
    "image/webp": _encoded("WEBP", (24, 24)),
}


@settings(max_examples=200, deadline=None)
@given(
    media_type=st.sampled_from(sorted(_SEEDS)),
    edits=st.lists(st.tuples(st.integers(min_value=0), st.integers(0, 255)), max_size=8),
    keep=st.floats(min_value=0.0, max_value=1.0),
)
def test_mutated_real_image_returns_or_refuses(
    media_type: ImageMediaType, edits: list[tuple[int, int]], keep: float
) -> None:
    # Byte flips and truncation of a valid image reach the decoders' inner paths.
    data = bytearray(_SEEDS[media_type])
    for index, value in edits:
        data[index % len(data)] = value
    data = data[: max(1, round(len(data) * keep))]
    try:
        img = open_generated_image(bytes(data), media_type)
    except ImagePayloadError:
        return
    assert img.mode == "RGB"


class TestBakePayload:
    def _run(self, tmp_path: Path, client: FakeImageClient, out: Path | None = None) -> Path:
        out = out or tmp_path / "bake.png"
        generate_ai_asset(
            prompt="watercolor pine bough border",
            occasion=OccasionType.CHRISTMAS,
            out_path=out,
            request=_small_request(),
            client=client,
            timestamp="2027-01-15T10:00:00Z",
            consent_path=_consented(tmp_path),
        )
        return out

    def test_unreported_cost_is_recorded_as_unknown(self, tmp_path: Path) -> None:
        out = self._run(tmp_path, FakeImageClient(cost_usd=None))
        record = read_sidecar(out)
        assert record.cost_usd is None
        assert record.cost_source == "unknown"
        text = out.with_suffix(".license.yaml").read_text()
        assert "cost_usd: null" in text
        assert "cost_source: unknown" in text

    @pytest.mark.parametrize(
        ("fmt", "media_type"), [("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
    )
    def test_jpeg_and_webp_bake_to_the_exact_target(
        self, tmp_path: Path, fmt: str, media_type: ImageMediaType
    ) -> None:
        out = self._run(tmp_path, FakeImageClient(fmt=fmt, media_type=media_type))
        with Image.open(out) as img:
            assert img.format == "PNG"
            assert img.size == (64, 96)

    def test_refused_payload_writes_nothing(self, tmp_path: Path) -> None:
        out = tmp_path / "out" / "bake.png"
        with pytest.raises(ImagePayloadError):
            self._run(tmp_path, FakeImageClient(raw=_EPS), out=out)
        assert not out.parent.exists()
