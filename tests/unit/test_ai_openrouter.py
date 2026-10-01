"""OpenRouter ``/images`` client: request contract, local refusals, response mapping (#149).

No network: every test drives :class:`OpenRouterImageClient` through a
``FakeTransport`` or calls :func:`parse_images_response` on a committed
fixture (``tests/fixtures/openrouter/``). Row numbers refer to the mapping
table in issue #149 §5.
"""

from __future__ import annotations

import ast
import base64
import copy
import email.utils
import io
import json
import time
import traceback
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from PIL import Image
from pydantic import SecretStr

from holiday_card.core import ai_openrouter, ai_openrouter_models
from holiday_card.core.ai_assets import AspectSize, GeneratedImage, PixelSize
from holiday_card.core.ai_errors import ProviderError
from holiday_card.core.ai_openrouter import (
    ATTRIBUTION_HEADERS,
    CONNECT_TIMEOUT_S,
    IMAGES_URL,
    MAX_B64_CHARS,
    MAX_IMAGE_BYTES,
    MAX_RESPONSE_BYTES,
    OPENROUTER_BASE_URL,
    READ_TIMEOUT_S,
    HttpResponse,
    OpenRouterImageClient,
    parse_images_response,
)
from holiday_card.core.ai_openrouter_models import OPENROUTER_IMAGE_MODELS, OpenRouterModel
from openrouter_fixtures import (
    FIXTURES_DIR,
    GOLDEN_REQUEST,
    REFERENCE_PNG,
    FakeTransport,
    fixture_raw,
    load_response,
    to_response,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "src" / "holiday_card" / "core" / "ai_openrouter.py"

GEMINI = "google/gemini-3-pro-image"
GOLDEN_PROMPT = "watercolor pine bough border, sage green and burgundy"
KEY = "sk-or-v1-" + "ab" * 32
OTHER_KEY = "sk-or-v1-" + "cd" * 32
ENTRY = OPENROUTER_IMAGE_MODELS[GEMINI]


def _identity(text: str) -> str:
    return text


def _client(
    model: str = GEMINI, transport: FakeTransport | None = None, key: str = KEY
) -> tuple[OpenRouterImageClient, FakeTransport]:
    fake = transport or FakeTransport()
    return OpenRouterImageClient(api_key=SecretStr(key), model=model, transport=fake), fake


def _valid_shape(entry: OpenRouterModel) -> AspectSize:
    return AspectSize("3:4", entry.resolutions[-1] if entry.resolutions else None)


def _parse(name_or_response: str | HttpResponse, entry: OpenRouterModel = ENTRY) -> GeneratedImage:
    response = (
        load_response(name_or_response) if isinstance(name_or_response, str) else name_or_response
    )
    return parse_images_response(response, entry=entry, redact=_identity)


def _refused(name_or_response: str | HttpResponse) -> ProviderError:
    with pytest.raises(ProviderError) as info:
        _parse(name_or_response)
    return info.value


def _ok_body(**datum: Any) -> HttpResponse:
    return HttpResponse(
        200, {"content-type": "application/json"}, json.dumps({"data": [datum]}).encode()
    )


def _png_b64() -> str:
    return base64.b64encode(REFERENCE_PNG.read_bytes()).decode()


# --------------------------------------------------------------------------- constants


class TestConstants:
    def test_endpoint_and_limits(self) -> None:
        assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"
        assert IMAGES_URL == "https://openrouter.ai/api/v1/images"
        assert MAX_RESPONSE_BYTES == 48 * 1024 * 1024
        assert MAX_IMAGE_BYTES == 32 * 1024 * 1024
        assert MAX_B64_CHARS == 4 * -(-MAX_IMAGE_BYTES // 3)
        assert (CONNECT_TIMEOUT_S, READ_TIMEOUT_S) == (10.0, 300.0)

    def test_attribution_headers(self) -> None:
        assert dict(ATTRIBUTION_HEADERS) == {
            "HTTP-Referer": "https://github.com/clostaunau/holiday-card",
            "X-OpenRouter-Title": "holiday-card",
            "X-OpenRouter-App-Visibility": "hidden",
        }


# --------------------------------------------------------------------------- request contract


class TestRequestContract:
    def test_one_call_to_the_images_url_with_the_limits(self) -> None:
        client, fake = _client()
        client.generate(prompt="x", reference_path=None, shape=AspectSize("3:4", "2K"), seed=None)
        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["url"] == "https://openrouter.ai/api/v1/images"
        assert call["timeout_s"] == 300.0
        assert call["max_bytes"] == 48 * 1024 * 1024

    def test_headers_are_exactly_the_documented_set(self) -> None:
        from holiday_card import __version__

        client, fake = _client()
        client.generate(prompt="x", reference_path=None, shape=AspectSize("3:4", "2K"), seed=None)
        assert fake.calls[0]["headers"] == {
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"holiday-card/{__version__}",
            "HTTP-Referer": "https://github.com/clostaunau/holiday-card",
            "X-OpenRouter-Title": "holiday-card",
            "X-OpenRouter-App-Visibility": "hidden",
        }

    def test_the_key_is_in_neither_url_nor_body(self) -> None:
        client, fake = _client()
        client.generate(
            prompt="x", reference_path=str(REFERENCE_PNG), shape=AspectSize("3:4", "2K"), seed=None
        )
        assert KEY not in fake.calls[0]["url"]
        assert KEY.encode() not in fake.calls[0]["body"]

    def test_body_equals_the_golden_moo_a6_request(self) -> None:
        client, fake = _client()
        client.generate(
            prompt=GOLDEN_PROMPT,
            reference_path=str(REFERENCE_PNG),
            shape=AspectSize("3:4", "2K"),
            seed=None,
        )
        golden = json.loads((FIXTURES_DIR / GOLDEN_REQUEST).read_text(encoding="utf-8"))
        assert fake.body == golden
        # Key order is part of the contract (spec §6.2).
        assert list(fake.body) == list(golden)

    def test_body_is_compact_ascii_json(self) -> None:
        client, fake = _client()
        client.generate(prompt="Frohe Weihnachten ✨", reference_path=None,
                        shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        raw = fake.calls[0]["body"]
        assert b", " not in raw and b": " not in raw
        assert raw.isascii()  # non-ASCII is JSON-escaped (surrogate-safe)
        assert fake.body["prompt"] == "Frohe Weihnachten ✨"

    def test_a_changed_pin_changes_the_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The golden is tied to the allowlist: moving the pin must turn it red.
        moved = replace(ENTRY, provider_tag="google-vertex")
        monkeypatch.setattr(
            ai_openrouter_models,
            "OPENROUTER_IMAGE_MODELS",
            MappingProxyType({**OPENROUTER_IMAGE_MODELS, GEMINI: moved}),
        )
        client, fake = _client()
        client.generate(prompt=GOLDEN_PROMPT, reference_path=str(REFERENCE_PNG),
                        shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        golden = json.loads((FIXTURES_DIR / GOLDEN_REQUEST).read_text(encoding="utf-8"))
        assert fake.body != golden

    @pytest.mark.parametrize("with_reference", [True, False])
    @pytest.mark.parametrize("model", sorted(OPENROUTER_IMAGE_MODELS))
    def test_never_sends_forbidden_keys(self, model: str, with_reference: bool) -> None:
        entry = OPENROUTER_IMAGE_MODELS[model]
        client, fake = _client(model)
        client.generate(
            prompt="x",
            reference_path=str(REFERENCE_PNG) if with_reference else None,
            shape=_valid_shape(entry),
            seed=7 if entry.seed else None,
        )
        forbidden = {"size", "models", "stream", "quality", "background", "user", "session_id"}
        assert not forbidden & set(fake.body)
        assert fake.body["model"] == model
        assert fake.body["n"] == 1
        assert fake.body["provider"]["only"] == [entry.provider_tag]
        assert fake.body["provider"]["allow_fallbacks"] is False
        assert ("input_references" in fake.body) is with_reference


@pytest.mark.parametrize("model", sorted(OPENROUTER_IMAGE_MODELS))
class TestConditionalFields:
    def test_seed_only_when_supported(self, model: str) -> None:
        entry = OPENROUTER_IMAGE_MODELS[model]
        client, fake = _client(model)
        client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry),
                        seed=7 if entry.seed else None)  # fmt: skip
        assert fake.body.get("seed") == (7 if entry.seed else None)
        client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry), seed=None)
        assert "seed" not in fake.body

    def test_output_format_only_when_advertised(self, model: str) -> None:
        entry = OPENROUTER_IMAGE_MODELS[model]
        client, fake = _client(model)
        client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry), seed=None)
        if "png" in entry.output_formats:
            assert fake.body["output_format"] == "png"
        else:
            assert "output_format" not in fake.body

    def test_resolution_only_when_the_shape_has_one(self, model: str) -> None:
        entry = OPENROUTER_IMAGE_MODELS[model]
        client, fake = _client(model)
        client.generate(prompt="x", reference_path=None, shape=AspectSize("3:4", None), seed=None)
        assert "resolution" not in fake.body
        if entry.resolutions:
            tier = entry.resolutions[0]
            client.generate(prompt="x", reference_path=None,
                            shape=AspectSize("3:4", tier), seed=None)  # fmt: skip
            assert fake.body["resolution"] == tier

    def test_moderation_passthrough_only_when_advertised(self, model: str) -> None:
        entry = OPENROUTER_IMAGE_MODELS[model]
        client, fake = _client(model)
        client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry), seed=None)
        slug = entry.provider_tag.split("/")[0]
        if "moderation" in entry.passthrough:
            assert fake.body["provider"]["options"] == {slug: {"moderation": "auto"}}
        else:
            assert "options" not in fake.body["provider"]


def test_gpt_image_2_sends_moderation_auto_under_the_openai_slug() -> None:
    client, fake = _client("openai/gpt-image-2")
    client.generate(prompt="x", reference_path=None, shape=AspectSize("3:4", None), seed=None)
    assert fake.body["provider"] == {
        "only": ["openai"],
        "allow_fallbacks": False,
        "options": {"openai": {"moderation": "auto"}},
    }


def test_jpeg_reference_is_sent_as_image_jpeg(tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"  # the extension lies; the probe decides
    Image.new("RGB", (8, 8), (1, 2, 3)).save(ref, format="JPEG")
    client, fake = _client()
    client.generate(prompt="x", reference_path=str(ref), shape=AspectSize("3:4", "2K"), seed=None)
    url = fake.body["input_references"][0]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == ref.read_bytes()


# --------------------------------------------------------------------------- local refusals


def _test_entry(**changes: Any) -> OpenRouterModel:
    return replace(
        OPENROUTER_IMAGE_MODELS["bytedance-seed/seedream-4.5"], id="test/model", **changes
    )


def _install(monkeypatch: pytest.MonkeyPatch, entry: OpenRouterModel) -> None:
    monkeypatch.setattr(
        ai_openrouter_models,
        "OPENROUTER_IMAGE_MODELS",
        MappingProxyType({**OPENROUTER_IMAGE_MODELS, entry.id: entry}),
    )


class TestLocalRefusals:
    def test_unknown_model_lists_the_curated_ids(self) -> None:
        with pytest.raises(ValueError, match="unknown OpenRouter image model 'nope/x'") as info:
            OpenRouterImageClient(api_key=SecretStr(KEY), model="nope/x", transport=FakeTransport())
        for model in OPENROUTER_IMAGE_MODELS:
            assert model in str(info.value)

    @pytest.mark.parametrize("key", ["", "   ", "\t\n"])
    def test_blank_key_is_an_environment_error(self, key: str) -> None:
        fake = FakeTransport()
        with pytest.raises(ProviderError) as info:
            OpenRouterImageClient(api_key=SecretStr(key), model=GEMINI, transport=fake)
        assert info.value.kind == "environment"
        assert "OPENROUTER_API_KEY" in str(info.value)
        assert fake.calls == []

    @pytest.mark.parametrize(
        ("model", "shape", "seed", "match"),
        [
            (GEMINI, PixelSize(1024, 1536), None, "aspect ratio and resolution"),
            (GEMINI, AspectSize("7:5", "2K"), None, "aspect ratio '7:5'"),
            (GEMINI, AspectSize("3:4", "512"), None, "resolution '512'"),
            ("black-forest-labs/flux.2-pro", AspectSize("3:4", "1K"), None, "resolution '1K'"),
            (GEMINI, AspectSize("3:4", "2K"), 7, "seed"),
        ],
    )
    def test_usage_refusals_before_any_call(
        self, model: str, shape: Any, seed: int | None, match: str
    ) -> None:
        client, fake = _client(model)
        with pytest.raises(ProviderError, match=match) as info:
            client.generate(prompt="x", reference_path=None, shape=shape, seed=seed)
        assert (info.value.kind, info.value.status) == ("usage", None)
        assert fake.calls == []

    def test_reference_on_a_no_reference_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch, _test_entry(input_refs_min=0, input_refs_max=0))
        client, fake = _client("test/model")
        with pytest.raises(ProviderError, match="takes no reference") as info:
            client.generate(prompt="x", reference_path=str(REFERENCE_PNG),
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        assert info.value.kind == "usage"
        assert fake.calls == []

    def test_no_reference_on_a_reference_required_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _test_entry(input_refs_min=1, input_refs_max=4))
        client, fake = _client("test/model")
        with pytest.raises(ProviderError, match="needs a reference") as info:
            client.generate(
                prompt="x", reference_path=None, shape=AspectSize("3:4", "2K"), seed=None
            )
        assert info.value.kind == "usage"
        assert fake.calls == []

    @pytest.mark.parametrize("kind", ["text", "gif", "missing"])
    def test_unreadable_reference_is_a_usage_error(self, tmp_path: Path, kind: str) -> None:
        ref = tmp_path / "ref.png"
        if kind == "text":
            ref.write_text("OPENROUTER_API_KEY=nope\n")
        elif kind == "gif":
            Image.new("RGB", (8, 8)).save(ref, format="GIF")
        client, fake = _client()
        with pytest.raises(ProviderError, match="--reference") as info:
            client.generate(prompt="x", reference_path=str(ref),
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        assert info.value.kind == "usage"
        assert fake.calls == []


# --------------------------------------------------------------------------- responses


class TestSuccessfulResponses:
    def test_ok_png(self) -> None:
        img = _parse("ok_png")
        assert img.media_type == "image/png"
        assert (img.cost_usd, img.cost_source) == (0.1344, "reported")
        assert img.generation_id == "gen-TEST123"
        assert img.provider_route == "google-ai-studio/global"
        assert img.model_version is None
        assert Image.open(io.BytesIO(img.image_bytes)).size == (8, 8)

    def test_ok_jpeg_without_cost_is_unknown(self) -> None:
        img = _parse("ok_jpeg")
        assert img.media_type == "image/jpeg"
        assert (img.cost_usd, img.cost_source) == (None, "unknown")
        assert img.generation_id is None
        assert Image.open(io.BytesIO(img.image_bytes)).size == (8, 8)

    def test_ok_webp_media_type_is_sniffed(self) -> None:
        img = _parse("ok_webp")
        assert img.media_type == "image/webp"
        assert (img.cost_usd, img.cost_source) == (0.04, "reported")
        assert Image.open(io.BytesIO(img.image_bytes)).size == (8, 8)

    def test_client_returns_the_parsed_image(self) -> None:
        client, _fake = _client(transport=FakeTransport([load_response("ok_webp")]))
        img = client.generate(prompt="x", reference_path=None,
                              shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        assert img.media_type == "image/webp"

    def test_content_type_parameters_are_ignored(self) -> None:
        raw = fixture_raw("ok_png")
        raw["headers"]["content-type"] = "Application/JSON; charset=utf-8"
        assert _parse(to_response(raw)).media_type == "image/png"


def _expect(name: str, kind: str, status: int | None, retry: float | None = None) -> None:
    e = _refused(name)
    assert (e.kind, e.status, e.retry_after_s) == (kind, status, retry)


class TestErrorMapping:
    """One test per table row (issue #149 §5)."""

    @pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
    def test_row_2_redirect(self, status: int) -> None:
        e = _refused(HttpResponse(status, {"location": "https://evil.invalid/"}, b""))
        assert (e.kind, e.status) == ("transient", status)

    def test_row_3_400(self) -> None:
        _expect("err_400", "usage", 400)
        assert "OpenRouter 400 invalid_request: Invalid aspect_ratio" in str(_refused("err_400"))

    def test_row_3_400_gemini_moderation_block_is_refused(self) -> None:
        # Live call E (#140): Gemini's safety block is a 400 with no error_type (#172).
        _expect("err_400_gemini_block", "refused", 400)
        text = str(_refused("err_400_gemini_block"))
        assert "content moderation" in text and "PROHIBITED_CONTENT" in text

    @pytest.mark.parametrize("reason", ["PROHIBITED_CONTENT", "SAFETY", "BLOCKLIST", "IMAGE_SAFETY"])
    @pytest.mark.parametrize("field", ["block_reason", "finish_reason"])
    def test_row_3_400_safety_reason_is_refused(self, field: str, reason: str) -> None:
        body = {"error": {"code": 400, "message": "m", "metadata": {field: reason}}}
        e = _refused(HttpResponse(400, {}, json.dumps(body).encode()))
        assert (e.kind, e.status) == ("refused", 400)

    @pytest.mark.parametrize("field", ["block_reason", "finish_reason"])
    def test_row_3_400_other_reason_stays_usage(self, field: str) -> None:
        body = {"error": {"code": 400, "message": "m", "metadata": {field: "MAX_TOKENS"}}}
        e = _refused(HttpResponse(400, {}, json.dumps(body).encode()))
        assert (e.kind, e.status) == ("usage", 400)

    @pytest.mark.parametrize("status", [404, 413, 422])
    def test_row_3_safety_reason_on_other_usage_status_stays_usage(self, status: int) -> None:
        body = {"error": {"code": status, "message": "m", "metadata": {"block_reason": "SAFETY"}}}
        e = _refused(HttpResponse(status, {}, json.dumps(body).encode()))
        assert (e.kind, e.status) == ("usage", status)

    @pytest.mark.parametrize(
        "error_type",
        ["invalid_request", "invalid_image", "image_too_large", "image_too_small",
         "unsupported_image_format", "image_not_found", "image_download_failed"],
    )  # fmt: skip
    @pytest.mark.parametrize("status", [400, 404, 413, 422])
    def test_row_3_usage_statuses(self, status: int, error_type: str) -> None:
        body = {"error": {"code": status, "message": "m", "metadata": {"error_type": error_type}}}
        e = _refused(HttpResponse(status, {}, json.dumps(body).encode()))
        assert (e.kind, e.status) == ("usage", status)

    def test_row_4_401(self) -> None:
        _expect("err_401", "environment", 401)
        assert str(_refused("err_401")) == "OpenRouter 401 error: User not found."

    def test_row_5_402_in_flight_budget_is_transient(self) -> None:
        _expect("err_402_in_flight", "transient", 402, 5.0)
        assert str(_refused("err_402_in_flight")).endswith("(retry after 5 s)")

    def test_row_6_402_credits(self) -> None:
        _expect("err_402", "environment", 402)
        assert "Add credits" in str(_refused("err_402"))  # remedy_hint is shown

    def test_row_6_402_without_metadata(self) -> None:
        e = _refused(HttpResponse(402, {}, b'{"error":{"code":402,"message":"pay"}}'))
        assert (e.kind, e.status) == ("environment", 402)

    def test_row_7_403_content_policy(self) -> None:
        _expect("err_403_policy", "refused", 403)
        text = str(_refused("err_403_policy"))
        assert "content_policy_violation" in text
        assert "SAFETY" in text and "real person" in text

    def test_row_7_403_refusal(self) -> None:
        _expect("err_403_refusal", "refused", 403)

    def test_row_8_403_permission(self) -> None:
        _expect("err_403_permission", "environment", 403)

    def test_row_8_403_guardrail_without_error_type(self) -> None:
        body = b'{"error":{"code":403,"message":"Request blocked by guardrail"}}'
        e = _refused(HttpResponse(403, {}, body))
        assert (e.kind, e.status) == ("environment", 403)

    def test_row_9_429(self) -> None:
        _expect("err_429", "transient", 429, 30.0)

    def test_row_9_502(self) -> None:
        _expect("err_502", "transient", 502)

    def test_row_9_524(self) -> None:
        _expect("err_524", "transient", 524)

    @pytest.mark.parametrize("status", [408, 500, 503, 504, 529, 599])
    def test_row_9_other_transient_statuses(self, status: int) -> None:
        e = _refused(HttpResponse(status, {"retry-after": "2"}, b""))
        assert (e.kind, e.status, e.retry_after_s) == ("transient", status, 2.0)

    @pytest.mark.parametrize("status", [100, 201, 204, 409, 418])
    def test_row_10_any_other_status(self, status: int) -> None:
        e = _refused(HttpResponse(status, {}, b"nope"))
        assert (e.kind, e.status) == ("transient", status)

    def test_non_json_error_body_maps_on_status_alone(self) -> None:
        e = _refused(HttpResponse(401, {"content-type": "text/html"}, b"<html>no</html>"))
        assert (e.kind, e.status) == ("environment", 401)
        assert str(e) == "OpenRouter 401 error"

    def test_row_11_non_json_content_type(self) -> None:
        _expect("not_json", "transient", 200)

    def test_row_11_missing_content_type(self) -> None:
        raw = fixture_raw("ok_png")
        del raw["headers"]["content-type"]
        e = _refused(to_response(raw))
        assert (e.kind, e.status) == ("transient", 200)

    @pytest.mark.parametrize(
        "body", [b"{not json", b"[]", b'{"data": "x"}', b'"hello"', b"\xff\xfe", b'{"created": 1}']
    )
    def test_row_12_invalid_json_or_shape(self, body: bytes) -> None:
        e = _refused(HttpResponse(200, {"content-type": "application/json"}, body))
        assert (e.kind, e.status) == ("transient", 200)

    def test_row_12_error_key_that_is_not_an_envelope(self) -> None:
        body = b'{"error": "boom"}'
        e = _refused(HttpResponse(200, {"content-type": "application/json"}, body))
        assert (e.kind, e.status) == ("transient", 200)
        assert "malformed" in str(e)

    def test_row_13_status_200_error_envelope(self) -> None:
        _expect("err_200_envelope", "transient", 502)

    @pytest.mark.parametrize(("code", "kind"), [(401, "environment"), (403, "environment"),
                                                (400, "usage"), (None, "transient")])  # fmt: skip
    def test_row_13_envelope_code_goes_through_the_table(self, code: int | None, kind: str) -> None:
        body = json.dumps({"error": {"code": code, "message": "m"}}).encode()
        e = _refused(HttpResponse(200, {"content-type": "application/json"}, body))
        assert (e.kind, e.status) == (kind, code if code is not None else 200)

    def test_row_14_empty_data(self) -> None:
        _expect("empty_data", "refused", 200)

    def test_row_15_two_images(self) -> None:
        _expect("two_images", "refused", 200)

    def test_row_16_remote_url(self) -> None:
        _expect("remote_url", "refused", 200)

    @pytest.mark.parametrize("prefix", ["http://x/", "https://x/", "data:image/png;base64,"])
    def test_row_16_url_shaped_b64(self, prefix: str) -> None:
        e = _refused(_ok_body(b64_json=prefix + _png_b64(), media_type="image/png"))
        assert (e.kind, e.status) == ("refused", 200)

    @pytest.mark.parametrize("datum", [{}, {"b64_json": ""}, {"media_type": "image/png"}])
    def test_row_17_missing_b64(self, datum: dict[str, str]) -> None:
        e = _refused(_ok_body(**datum))
        assert (e.kind, e.status) == ("transient", 200)

    def test_row_18_svg(self) -> None:
        _expect("svg", "transient", 200)

    def test_row_19_oversize_b64_is_refused_before_decoding(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def spy(*_a: object, **_k: object) -> bytes:
            raise AssertionError("b64decode was called")

        monkeypatch.setattr(base64, "b64decode", spy)
        e = _refused(_ok_body(b64_json="A" * (MAX_B64_CHARS + 4), media_type="image/png"))
        assert (e.kind, e.status) == ("transient", 200)

    def test_row_20_bad_base64(self) -> None:
        _expect("bad_base64", "transient", 200)

    def test_row_21_mime_mismatch(self) -> None:
        _expect("mime_mismatch", "transient", 200)

    def test_row_21_unknown_magic_without_media_type(self) -> None:
        gif = io.BytesIO()
        Image.new("RGB", (8, 8)).save(gif, format="GIF")
        e = _refused(_ok_body(b64_json=base64.b64encode(gif.getvalue()).decode()))
        assert (e.kind, e.status) == ("transient", 200)

    def test_row_22_bomb(self) -> None:
        _expect("bomb_png", "transient", 200)

    def test_row_22_truncated_header(self) -> None:
        png = REFERENCE_PNG.read_bytes()[:20]
        e = _refused(_ok_body(b64_json=base64.b64encode(png).decode(), media_type="image/png"))
        assert (e.kind, e.status) == ("transient", 200)

    def test_row_22_animation(self) -> None:
        buf = io.BytesIO()
        frames = [Image.new("RGB", (8, 8), c) for c in ((255, 0, 0), (0, 0, 255))]
        frames[0].save(buf, format="PNG", save_all=True, append_images=frames[1:])
        e = _refused(_ok_body(b64_json=base64.b64encode(buf.getvalue()).decode(),
                              media_type="image/png"))  # fmt: skip
        assert (e.kind, e.status) == ("transient", 200)

    def test_unexpected_exception_becomes_transient(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: object, **_k: object) -> object:
            raise ZeroDivisionError("bug")

        monkeypatch.setattr(ai_openrouter, "probe_generated_image", boom)
        e = _refused("ok_png")
        assert (e.kind, e.status) == ("transient", 200)
        assert "ZeroDivisionError" in str(e)


# --------------------------------------------------------------------------- headers + cost


class TestHeaderHygiene:
    @pytest.mark.parametrize("value", ["<script>", "", "a" * 129, "gen 1", "gen-1\n", "gén-1"])
    def test_untrusted_generation_id_is_dropped(self, value: str) -> None:
        raw = fixture_raw("ok_png")
        raw["headers"]["x-generation-id"] = value
        assert _parse(to_response(raw)).generation_id is None

    def test_generation_id_at_the_length_limit_is_kept(self) -> None:
        raw = fixture_raw("ok_png")
        raw["headers"]["x-generation-id"] = "a_-" * 42 + "zz"
        assert _parse(to_response(raw)).generation_id == "a_-" * 42 + "zz"

    def _retry(self, value: str) -> float | None:
        e = _refused(HttpResponse(429, {"retry-after": value}, b""))
        return e.retry_after_s

    def test_http_date_retry_after(self) -> None:
        future = email.utils.formatdate(time.time() + 120, usegmt=True)
        retry = self._retry(future)
        assert retry is not None and 100 <= retry <= 121

    def test_past_http_date_clamps_to_zero(self) -> None:
        assert self._retry("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0

    def test_naive_http_date_is_utc(self) -> None:
        naive = email.utils.formatdate(time.time() + 120)[:-6]  # drop the zone
        retry = self._retry(naive)
        assert retry is not None and retry <= 121

    @pytest.mark.parametrize("value", ["soon", "-5", "", "1e3", "Wed, 99 Foo"])
    def test_unparsable_retry_after_is_none(self, value: str) -> None:
        assert self._retry(value) is None

    def test_fractional_delta_seconds(self) -> None:
        assert self._retry("1.5") == 1.5


class TestCost:
    @pytest.mark.parametrize("cost", ["-1", "NaN", "Infinity", "null"])
    def test_invalid_cost_is_unknown(self, cost: str) -> None:
        text = json.dumps(fixture_raw("ok_png")["body"]).replace("0.1344", cost)
        img = _parse(HttpResponse(200, {"content-type": "application/json"}, text.encode()))
        assert (img.cost_usd, img.cost_source) == (None, "unknown")

    def test_string_cost_fails_validation(self) -> None:
        # Pinned: a non-numeric cost is a malformed response (row 12), not "unknown".
        text = json.dumps(fixture_raw("ok_png")["body"]).replace("0.1344", '"abc"')
        e = _refused(HttpResponse(200, {"content-type": "application/json"}, text.encode()))
        assert (e.kind, e.status) == ("transient", 200)

    def test_zero_cost_is_reported(self) -> None:
        text = json.dumps(fixture_raw("ok_png")["body"]).replace("0.1344", "0")
        img = _parse(HttpResponse(200, {"content-type": "application/json"}, text.encode()))
        assert (img.cost_usd, img.cost_source) == (0.0, "reported")


# --------------------------------------------------------------------------- transport errors + retries


class TestNoRetry:
    @pytest.mark.parametrize("name", ["err_429", "err_502"])
    def test_error_status_is_not_retried(self, name: str) -> None:
        client, fake = _client(transport=FakeTransport([load_response(name)] * 3))
        with pytest.raises(ProviderError):
            client.generate(prompt="x", reference_path=None,
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        assert len(fake.calls) == 1

    def test_transport_timeout_is_not_retried_and_passes_through(self) -> None:
        timeout = ProviderError("OpenRouter read timed out", kind="transient")
        client, fake = _client(transport=FakeTransport([timeout, load_response("ok_png")]))
        with pytest.raises(ProviderError) as info:
            client.generate(prompt="x", reference_path=None,
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        assert info.value is timeout
        assert len(fake.calls) == 1


# --------------------------------------------------------------------------- secrets


def _err_fixture_names() -> list[str]:
    return sorted(p.stem for p in FIXTURES_DIR.glob("err_*.json"))


def _with_sentinel(name: str, sentinel: str) -> HttpResponse:
    raw = copy.deepcopy(fixture_raw(name))
    error = raw["body"]["error"]
    error["message"] = f"bad key {sentinel} rejected"
    metadata = error.setdefault("metadata", {})
    metadata["reasons"] = [*metadata.get("reasons", []), sentinel]
    metadata["remedy_hint"] = f"rotate {sentinel}"
    metadata["error_type"] = metadata.get("error_type", "x") + sentinel
    return to_response(raw)


def _assert_absent(e: BaseException, secret: str) -> None:
    rendered = "".join(traceback.format_exception(e))
    assert secret not in str(e)
    assert secret not in repr(e)
    assert secret not in rendered
    assert all(secret not in str(a) for a in e.args)


class TestSecretSentinel:
    @pytest.mark.parametrize("name", _err_fixture_names())
    @pytest.mark.parametrize("sentinel", [KEY, OTHER_KEY], ids=["the-key", "key-shaped"])
    def test_sentinel_never_reaches_the_exception(self, name: str, sentinel: str) -> None:
        client, _fake = _client(transport=FakeTransport([_with_sentinel(name, sentinel)]))
        with pytest.raises(ProviderError) as info:
            client.generate(prompt="x", reference_path=None,
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        _assert_absent(info.value, sentinel)
        assert "[REDACTED]" in str(info.value)

    def test_literal_key_that_is_not_key_shaped_is_redacted(self) -> None:
        odd = "zz" + "Q" * 30
        body = json.dumps({"error": {"code": 401, "message": f"bad {odd}"}}).encode()
        client, _fake = _client(transport=FakeTransport([HttpResponse(401, {}, body)]), key=odd)
        with pytest.raises(ProviderError) as info:
            client.generate(prompt="x", reference_path=None,
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        _assert_absent(info.value, odd)

    def test_malformed_body_echoing_the_key_does_not_leak(self) -> None:
        # A pydantic ValidationError would echo input_value; it must not be chained.
        body = json.dumps({"data": KEY, "usage": {"cost": KEY}}).encode()
        client, _fake = _client(transport=FakeTransport(
            [HttpResponse(200, {"content-type": "application/json"}, body)]))  # fmt: skip
        with pytest.raises(ProviderError) as info:
            client.generate(prompt="x", reference_path=None,
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        _assert_absent(info.value, KEY)
        assert info.value.__cause__ is None

    def test_client_repr_and_state_hold_no_key(self) -> None:
        client, _fake = _client()
        assert repr(client) == "OpenRouterImageClient(model='google/gemini-3-pro-image')"
        assert KEY not in repr(client)
        for name, value in vars(client).items():
            if isinstance(value, SecretStr):
                continue
            assert KEY not in repr(value), name
            assert not isinstance(value, dict) or "Authorization" not in value, name

    def test_model_property(self) -> None:
        client, _fake = _client("openai/gpt-image-2")
        assert client.model == "openai/gpt-image-2"


def test_get_secret_value_is_called_only_in_the_two_helpers() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    allowed = {"_request_headers", "_key_redactor"}
    found: list[str] = []

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.ClassDef)) else scope
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "get_secret_value"
            ):
                found.append(scope)
            visit(child, inner)

    visit(tree, "<module>")
    assert found, "the scan must see the unwrap"
    assert set(found) <= allowed, found


# --------------------------------------------------------------------------- review findings


class TestReviewFindings:
    @pytest.mark.parametrize(
        "key", [KEY + "\r", KEY + "\n", "sk-or-v1-dead beefdeadbeef", KEY + "\x00"]
    )
    def test_key_with_whitespace_or_controls_is_refused_without_echoing_it(self, key: str) -> None:
        fake = FakeTransport()
        with pytest.raises(ProviderError) as info:
            OpenRouterImageClient(api_key=SecretStr(key), model=GEMINI, transport=fake)
        assert info.value.kind == "environment"
        _assert_absent(info.value, key.strip())
        assert "beef" not in str(info.value)

    def test_key_split_by_an_escape_sequence_is_still_redacted(self) -> None:
        odd = "MyCustomKey123456"
        body = json.dumps({"error": {"code": 401, "message": "bad key MyCustom\x1b[0mKey123456"}})
        client, _fake = _client(
            transport=FakeTransport([HttpResponse(401, {}, body.encode())]), key=odd
        )
        with pytest.raises(ProviderError) as info:
            client.generate(prompt="x", reference_path=None,
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        _assert_absent(info.value, odd)

    def test_lone_surrogate_prompt_is_sent_escaped(self) -> None:
        client, fake = _client()
        client.generate(prompt="\udcff pine", reference_path=None,
                        shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        assert fake.body["prompt"] == "\udcff pine"

    def test_unreadable_reference_after_the_probe_is_a_usage_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def gone(_self: Path) -> bytes:
            raise PermissionError("denied")

        monkeypatch.setattr(Path, "read_bytes", gone)
        client, fake = _client()
        with pytest.raises(ProviderError, match="--reference") as info:
            client.generate(prompt="x", reference_path=str(REFERENCE_PNG),
                            shape=AspectSize("3:4", "2K"), seed=None)  # fmt: skip
        assert info.value.kind == "usage"
        assert fake.calls == []


# --------------------------------------------------------------------------- transparent motifs (#169)


class TestTransparentBackground:
    def test_a_model_without_the_capability_is_refused_before_any_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entry = _test_entry(background_transparent=False)
        _install(monkeypatch, entry)
        client, fake = _client(entry.id)
        with pytest.raises(ProviderError, match="transparent background") as info:
            client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry),
                            seed=None, transparent=True)  # fmt: skip
        assert info.value.kind == "usage"
        assert fake.calls == []

    def test_only_the_live_proven_model_is_capable(self) -> None:
        # Flip one only with a live call showing real alpha (#169); #179 proved sunburst.
        capable = [m for m, e in OPENROUTER_IMAGE_MODELS.items() if e.background_transparent]
        assert capable == ["openai/gpt-image-2.5-sunburst"]

    def test_sunburst_is_sent_background_transparent_and_no_output_format(self) -> None:
        # It advertises no output_format; #179's live call proved this exact body.
        client, fake = _client("openai/gpt-image-2.5-sunburst")
        client.generate(prompt="x", reference_path=None, shape=AspectSize("3:4", None),
                        seed=None, transparent=True)  # fmt: skip
        assert fake.body["background"] == "transparent"
        assert "output_format" not in fake.body
        assert fake.body["provider"]["only"] == ["openai"]

    def test_a_capable_model_is_sent_background_transparent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entry = _test_entry(background_transparent=True, output_formats=("png", "jpeg"))
        _install(monkeypatch, entry)
        client, fake = _client(entry.id)
        client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry),
                        seed=None, transparent=True)  # fmt: skip
        assert fake.body["background"] == "transparent"
        assert fake.body["output_format"] == "png"

    def test_an_opaque_request_to_a_capable_model_sends_no_background(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entry = _test_entry(background_transparent=True)
        _install(monkeypatch, entry)
        client, fake = _client(entry.id)
        client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry), seed=None)
        assert "background" not in fake.body

    def test_a_capable_model_with_only_alpha_less_formats_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Riverflow v2.5 Fast advertises transparent but only outputs JPEG.
        entry = _test_entry(background_transparent=True, output_formats=("jpeg",))
        _install(monkeypatch, entry)
        client, fake = _client(entry.id)
        with pytest.raises(ProviderError, match="jpeg") as info:
            client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry),
                            seed=None, transparent=True)  # fmt: skip
        assert info.value.kind == "usage"
        assert fake.calls == []

    def test_webp_carries_alpha(self, monkeypatch: pytest.MonkeyPatch) -> None:
        entry = _test_entry(background_transparent=True, output_formats=("webp", "jpeg"))
        _install(monkeypatch, entry)
        client, fake = _client(entry.id)
        client.generate(prompt="x", reference_path=None, shape=_valid_shape(entry),
                        seed=None, transparent=True)  # fmt: skip
        assert fake.body["background"] == "transparent"
        assert fake.body["output_format"] == "webp"
