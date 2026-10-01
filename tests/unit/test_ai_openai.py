"""The OpenAI adapter sends only sizes its model accepts (issue #87).

No network: a fake object stands in for the ``openai.OpenAI`` client and
records the kwargs of ``images.generate`` / ``images.edit``.
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from pydantic import SecretStr

import openai_sdk_stub as sdk
from holiday_card.core.ai_assets import (
    MODEL_SIZE_POLICIES,
    AspectSize,
    ImagePayloadError,
    PixelSize,
    build_ai_request,
    size_is_allowed,
)
from holiday_card.core.ai_errors import ProviderError
from holiday_card.core.ai_openai import OpenAIImageClient, make_openai_client
from holiday_card.core.ai_providers import AIProvider


def _png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (1, 2, 3)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class _FakeImages:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _respond(self) -> SimpleNamespace:
        return SimpleNamespace(data=[SimpleNamespace(b64_json=_png_b64())])

    def generate(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(("generate", kwargs))
        return self._respond()

    def edit(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(("edit", kwargs))
        return self._respond()


def _fake_openai() -> SimpleNamespace:
    return SimpleNamespace(images=_FakeImages())


def _size_kwarg(fake: SimpleNamespace) -> tuple[int, int]:
    w, h = fake.images.calls[0][1]["size"].split("x")
    return int(w), int(h)


@pytest.fixture
def reference(tmp_path: Path) -> Path:
    path = tmp_path / "ref.png"
    Image.new("RGB", (32, 32)).save(path)
    return path


def test_model_is_required() -> None:
    with pytest.raises(TypeError):
        OpenAIImageClient(_fake_openai())  # type: ignore[call-arg]


def test_provider_is_openai() -> None:
    assert OpenAIImageClient(_fake_openai(), model="gpt-image-2").provider is AIProvider.OPENAI


@pytest.mark.parametrize("model", sorted(MODEL_SIZE_POLICIES))
@pytest.mark.parametrize("use_reference", [False, True], ids=["generate", "edit"])
def test_moo_a6_size_sent_is_allowed_for_the_model(
    model: str, use_reference: bool, reference: Path
) -> None:
    fake = _fake_openai()
    client = OpenAIImageClient(fake, model=model)
    req = build_ai_request(
        prompt="pine bough",
        trim_width_in=4.13,
        trim_height_in=5.83,
        bleed_in=0.125,
        reference_path=str(reference) if use_reference else None,
        provider=client.provider,
        model=client.model,
    )
    client.generate(
        prompt=req.prompt, reference_path=req.reference_path, shape=req.shape, seed=None
    )
    method, kwargs = fake.images.calls[0]
    assert method == ("edit" if use_reference else "generate")
    assert kwargs["model"] == model
    assert kwargs["moderation"] == "auto"
    assert size_is_allowed(model, *_size_kwarg(fake))


def test_refuses_an_unsupported_size_before_calling_the_api() -> None:
    fake = _fake_openai()
    client = OpenAIImageClient(fake, model="gpt-image-1")
    with pytest.raises(ValueError, match="1312x1824"):
        client.generate(prompt="x", reference_path=None, shape=PixelSize(1312, 1824), seed=None)
    assert fake.images.calls == []


def test_refuses_an_aspect_shape_before_calling_the_api() -> None:
    fake = _fake_openai()
    client = OpenAIImageClient(fake, model="gpt-image-2")
    with pytest.raises(ValueError, match="openai takes a pixel size, got AspectSize"):
        client.generate(prompt="x", reference_path=None, shape=AspectSize("3:4", "2K"), seed=None)
    assert fake.images.calls == []


def test_refuses_a_seed_before_calling_the_api() -> None:
    fake = _fake_openai()
    client = OpenAIImageClient(fake, model="gpt-image-2")
    with pytest.raises(ValueError, match="gpt-image-2"):
        client.generate(prompt="x", reference_path=None, shape=PixelSize(1024, 1024), seed=7)
    assert fake.images.calls == []


def test_refuses_a_transparent_background_before_calling_the_api() -> None:
    # Whether direct OpenAI gets --transparent is an owner call (#169); until
    # then the client refuses it rather than silently baking opaque.
    fake = _fake_openai()
    client = OpenAIImageClient(fake, model="gpt-image-2")
    with pytest.raises(ValueError, match="transparent"):
        client.generate(prompt="x", reference_path=None, shape=PixelSize(1024, 1024),
                        seed=None, transparent=True)  # fmt: skip
    assert fake.images.calls == []


def test_unknown_model_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="dall-e-9"):
        OpenAIImageClient(_fake_openai(), model="dall-e-9")


# ---------------------------------------------------------------------------
# Provider errors are mapped to ProviderError, redacted (issue #142)
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_openai(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Install the stub SDK as ``openai`` (CI has no ``[ai]`` extra)."""
    mod = sdk.make_module()
    monkeypatch.setitem(sys.modules, "openai", mod)
    return mod


class _RaisingImages:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def generate(self, **_kwargs: Any) -> Any:
        raise self.exc

    def edit(self, **_kwargs: Any) -> Any:
        raise self.exc


def _generate(client: OpenAIImageClient) -> Any:
    return client.generate(
        prompt="pine bough", reference_path=None, shape=PixelSize(1024, 1024), seed=None
    )


def _raising_client(exc: BaseException, **kwargs: Any) -> OpenAIImageClient:
    return OpenAIImageClient(
        SimpleNamespace(images=_RaisingImages(exc)), **{"model": "gpt-image-2", **kwargs}
    )


_MAPPING_ROWS = [
    # (id, exception factory, kind, status, retry_after_s)
    ("timeout", lambda: sdk.APITimeoutError(request=None), "transient", None, None),
    ("connection", lambda: sdk.APIConnectionError(request=None), "transient", None, None),
    ("400-moderation", lambda: sdk.status_error(400, code="moderation_blocked"), "refused", 400, None),
    ("400-content-policy", lambda: sdk.status_error(400, code="content_policy_violation"), "refused", 400, None),
    ("400-other", lambda: sdk.status_error(400, code="invalid_value"), "usage", 400, None),
    ("400-no-code", lambda: sdk.status_error(400), "usage", 400, None),
    ("404", lambda: sdk.status_error(404, code="model_not_found"), "usage", 404, None),
    ("422", lambda: sdk.status_error(422), "usage", 422, None),
    ("401", lambda: sdk.status_error(401, code="invalid_api_key"), "environment", 401, None),
    ("403", lambda: sdk.status_error(403, code="unsupported_country_region_territory"), "environment", 403, None),
    ("429-quota", lambda: sdk.status_error(429, code="insufficient_quota"), "environment", 429, None),
    # The billing / spend-limit 429s in OpenAI's error-code guide (2026-09-30) are not retryable.
    *[
        (f"429-{c}", (lambda c=c: sdk.status_error(429, code=c)), "environment", 429, None)
        for c in (
            "credit_balance_exhausted",
            "organization_spend_limit_exceeded",
            "project_spend_limit_exceeded",
            "organization_usage_limit_exceeded",
        )
    ],
    (
        "429-rate",
        lambda: sdk.status_error(429, code="rate_limit_exceeded", headers={"retry-after": "20"}),
        "transient",
        429,
        20.0,
    ),
    ("429-date", lambda: sdk.status_error(429, headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}), "transient", 429, None),
    ("408", lambda: sdk.status_error(408), "transient", 408, None),
    ("409", lambda: sdk.status_error(409), "transient", 409, None),
    ("500", lambda: sdk.status_error(500), "transient", 500, None),
    ("503-retry", lambda: sdk.status_error(503, headers={"retry-after": "7"}), "transient", 503, 7.0),
    ("413-other-4xx", lambda: sdk.status_error(413), "usage", 413, None),
    ("bare-api-error", lambda: sdk.APIError("invalid response", None, body=None), "transient", None, None),
]


@pytest.mark.usefixtures("stub_openai")
@pytest.mark.parametrize(
    ("make_exc", "kind", "status", "retry_after"),
    [row[1:] for row in _MAPPING_ROWS],
    ids=[row[0] for row in _MAPPING_ROWS],
)
def test_sdk_errors_map_to_provider_error(
    make_exc: Any, kind: str, status: int | None, retry_after: float | None
) -> None:
    with pytest.raises(ProviderError) as info:
        _generate(_raising_client(make_exc()))
    err = info.value
    assert (err.kind, err.status, err.retry_after_s) == (kind, status, retry_after)


@pytest.mark.usefixtures("stub_openai")
def test_mapped_error_carries_no_sdk_exception() -> None:
    with pytest.raises(ProviderError) as info:
        _generate(_raising_client(sdk.status_error(401, "Incorrect API key")))
    err = info.value
    assert err.__cause__ is None
    assert err.__suppress_context__ is True
    # Raised after the handler, so the raw SDK error is not even __context__.
    assert err.__context__ is None


@pytest.mark.usefixtures("stub_openai")
def test_non_sdk_exception_propagates_unchanged() -> None:
    boom = KeyError("bug")
    with pytest.raises(KeyError) as info:
        _generate(_raising_client(boom))
    assert info.value is boom


def test_without_the_sdk_nothing_is_relabelled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "openai", None)  # `import openai` -> ImportError
    boom = RuntimeError("bug")
    with pytest.raises(RuntimeError) as info:
        _generate(_raising_client(boom))
    assert info.value is boom


@pytest.mark.usefixtures("stub_openai")
def test_api_key_is_redacted_from_the_mapped_message() -> None:
    key = "literal-key-that-is-not-sk-shaped-0123"
    exc = sdk.status_error(401, f"Incorrect API key provided: {key}; also sk-proj-****…abcd")
    with pytest.raises(ProviderError) as info:
        _generate(_raising_client(exc, api_key=SecretStr(key)))
    text = str(info.value)
    assert key not in text
    assert "sk-proj-****" not in text
    assert "[REDACTED]" in text


@pytest.mark.parametrize(
    "data",
    [[], [SimpleNamespace(b64_json=None)], [SimpleNamespace()]],
    ids=["empty", "b64-none", "no-b64"],
)
def test_no_image_in_the_response_is_a_refusal(data: list[Any]) -> None:
    images = SimpleNamespace(generate=lambda **_kw: SimpleNamespace(data=data))
    client = OpenAIImageClient(SimpleNamespace(images=images), model="gpt-image-2")
    with pytest.raises(ProviderError, match="no image") as info:
        _generate(client)
    assert info.value.kind == "refused"


class _RecordingOpenAI:
    instances: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        type(self).instances.append(kwargs)
        self.images = _FakeImages()


def test_make_openai_client_pins_host_retries_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    from holiday_card.core import ai_openai

    _RecordingOpenAI.instances = []
    monkeypatch.setitem(sys.modules, "openai", sdk.make_module(OpenAI=_RecordingOpenAI))
    monkeypatch.setenv("OPENAI_BASE_URL", "https://evil.example")
    client = make_openai_client(api_key="sk-proj-" + "k" * 40, model="gpt-image-1")
    assert client.model == "gpt-image-1"
    (kwargs,) = _RecordingOpenAI.instances
    assert kwargs["base_url"] == "https://api.openai.com/v1"
    assert kwargs["max_retries"] == 0
    assert kwargs["timeout"] == ai_openai.OPENAI_TIMEOUT_S == 300.0
    assert kwargs["api_key"] == "sk-proj-" + "k" * 40


def test_make_openai_client_redacts_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key = "not-sk-shaped-env-key-0123456789"

    class _FailingOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            self.images = _RaisingImages(sdk.status_error(401, f"bad key {key}"))

    monkeypatch.setitem(sys.modules, "openai", sdk.make_module(OpenAI=_FailingOpenAI))
    with pytest.raises(ProviderError) as info:
        _generate(make_openai_client(api_key=key, model="gpt-image-2"))
    assert key not in str(info.value)


# --- #141: decode safely, never invent a cost --------------------------------


def _client_returning(**response: Any) -> OpenAIImageClient:
    images = SimpleNamespace(generate=lambda **_kw: SimpleNamespace(**response))
    return OpenAIImageClient(SimpleNamespace(images=images), model="gpt-image-2")


def test_invalid_base64_is_an_image_payload_error() -> None:
    client = _client_returning(data=[SimpleNamespace(b64_json="iVBOR*not~base64")])
    with pytest.raises(ImagePayloadError, match="base64"):
        _generate(client)


def test_cost_is_unknown_because_the_sdk_reports_none() -> None:
    # openai 3.19.2's ImagesResponse carries token `usage`, never a USD cost.
    usage = SimpleNamespace(input_tokens=10, output_tokens=100, total_tokens=110)
    image = _generate(_client_returning(data=[SimpleNamespace(b64_json=_png_b64())], usage=usage))
    assert image.cost_usd is None
    assert image.cost_source == "unknown"


@pytest.mark.parametrize(
    ("output_format", "media_type"),
    [("png", "image/png"), ("jpeg", "image/jpeg"), ("webp", "image/webp"), (None, "image/png")],
)
def test_media_type_follows_output_format(output_format: str | None, media_type: str) -> None:
    image = _generate(
        _client_returning(data=[SimpleNamespace(b64_json=_png_b64())], output_format=output_format)
    )
    assert image.media_type == media_type


def test_media_type_defaults_to_png_without_output_format() -> None:
    image = _generate(_client_returning(data=[SimpleNamespace(b64_json=_png_b64())]))
    assert image.media_type == "image/png"
    assert base64.b64encode(image.image_bytes).decode() == _png_b64()
