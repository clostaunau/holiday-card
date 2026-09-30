"""The ``openai`` stub mirrors the real SDK's exception hierarchy (issue #142).

Skipped where the ``[ai]`` extra is absent (CI); run it locally with
``uv run --extra dev --extra ai pytest tests/unit/test_ai_openai_sdk_contract.py``.
"""

from __future__ import annotations

import inspect

import pytest

import openai_sdk_stub as sdk

openai = pytest.importorskip("openai")


@pytest.mark.parametrize("name", sdk.MIRRORED)
def test_real_sdk_exposes_the_class(name: str) -> None:
    assert inspect.isclass(getattr(openai, name))


@pytest.mark.parametrize("name", sdk.MIRRORED)
@pytest.mark.parametrize("base", sdk.MIRRORED)
def test_subclass_relations_match(name: str, base: str) -> None:
    stub = issubclass(getattr(sdk, name), getattr(sdk, base))
    real = issubclass(getattr(openai, name), getattr(openai, base))
    assert stub == real, f"{name} <: {base}: stub {stub}, real {real}"


@pytest.mark.parametrize("name", sdk.MIRRORED)
def test_constructor_parameters_match(name: str) -> None:
    def params(cls: type) -> list[tuple[str, object]]:
        sig = inspect.signature(cls.__init__)
        return [(p.name, p.kind) for p in sig.parameters.values()]

    assert params(getattr(sdk, name)) == params(getattr(openai, name))


def test_status_error_attributes_match_the_real_sdk() -> None:
    httpx = pytest.importorskip("httpx2")
    request = httpx.Request("POST", "https://api.openai.com/v1/images/generations")
    response = httpx.Response(429, headers={"retry-after": "20"}, request=request)
    body = {"message": "slow", "code": "rate_limit_exceeded"}
    real = openai.RateLimitError("slow", response=response, body=body)
    stub = sdk.status_error(429, "slow", code="rate_limit_exceeded", headers={"retry-after": "20"})
    for e in (real, stub):
        assert e.status_code == 429
        assert e.code == "rate_limit_exceeded"
        assert e.response.headers.get("retry-after") == "20"


def test_openai_client_accepts_the_pinned_kwargs() -> None:
    params = inspect.signature(openai.OpenAI.__init__).parameters
    for kw in ("api_key", "base_url", "max_retries", "timeout"):
        assert kw in params
