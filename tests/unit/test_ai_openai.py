"""The OpenAI adapter sends only sizes its model accepts (issue #87).

No network: a fake object stands in for the ``openai.OpenAI`` client and
records the kwargs of ``images.generate`` / ``images.edit``.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from holiday_card.core.ai_assets import (
    DEFAULT_AI_MODEL,
    MODEL_SIZE_POLICIES,
    build_ai_request,
    size_is_allowed,
)
from holiday_card.core.ai_openai import AIDependencyError, OpenAIImageClient, make_image_client


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


def test_default_model_is_the_single_source_of_truth() -> None:
    assert OpenAIImageClient(_fake_openai()).model == DEFAULT_AI_MODEL


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
        model=client.model,
    )
    client.generate(
        prompt=req.prompt,
        reference_path=req.reference_path,
        width_px=req.request_width_px,
        height_px=req.request_height_px,
        moderation=req.moderation,
        seed=None,
    )
    method, kwargs = fake.images.calls[0]
    assert method == ("edit" if use_reference else "generate")
    assert kwargs["model"] == model
    assert size_is_allowed(model, *_size_kwarg(fake))


def test_refuses_an_unsupported_size_before_calling_the_api() -> None:
    fake = _fake_openai()
    client = OpenAIImageClient(fake, model="gpt-image-1")
    with pytest.raises(ValueError, match="1312x1824"):
        client.generate(
            prompt="x",
            reference_path=None,
            width_px=1312,
            height_px=1824,
            moderation="auto",
            seed=None,
        )
    assert fake.images.calls == []


def test_unknown_model_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="dall-e-9"):
        OpenAIImageClient(_fake_openai(), model="dall-e-9")


def test_make_image_client_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AIDependencyError):
        make_image_client()
