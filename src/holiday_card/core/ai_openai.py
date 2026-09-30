"""OpenAI image-client adapter (Leapfrog 3, ``holiday-card[ai]`` extra).

This is the only module that imports ``openai``. It is loaded lazily so
the project remains fully functional without the ``[ai]`` extra — the
panel's "refuse to be a default code path" requirement (risk #8). Tests
drive it with a fake ``openai`` client object (no network); it refuses a
``size`` its model does not accept before calling the API (#87).

SDK errors become a redacted :class:`~holiday_card.core.ai_errors.ProviderError`
(#142). The client is pinned to the OpenAI host (``OPENAI_BASE_URL`` is
ignored), never retries a billed call, and times out after
:data:`OPENAI_TIMEOUT_S`.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Iterable

from pydantic import SecretStr

from holiday_card.core.ai_assets import (
    DEFAULT_AI_MODEL,
    GeneratedImage,
    size_is_allowed,
)
from holiday_card.core.ai_errors import ProviderError, ProviderErrorKind, parse_retry_after

__all__ = ["OpenAIImageClient", "make_image_client", "AIDependencyError", "OPENAI_TIMEOUT_S"]

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_TIMEOUT_S = 300.0
_REFUSAL_CODES = frozenset({"moderation_blocked", "content_policy_violation"})

# gpt-image pricing is per-image and tier-dependent; we surface the
# value OpenAI returns when available and fall back to this estimate.
_FALLBACK_COST_USD = 0.04


class AIDependencyError(RuntimeError):
    """Raised when the AI extra or API key is missing."""


class OpenAIImageClient:
    """Thin wrapper over the OpenAI Images API.

    Constructed only by :func:`make_image_client`, which validates that
    the ``openai`` package and ``OPENAI_API_KEY`` are present first.
    """

    def __init__(
        self,
        client: object,
        model: str = DEFAULT_AI_MODEL,
        *,
        api_key: SecretStr | None = None,
    ) -> None:
        size_is_allowed(model, 1024, 1024)  # unknown model -> ValueError (D4)
        self._client = client
        self._model = model
        # Used only to redact provider error text; never logged.
        self._api_key = api_key

    @property
    def model(self) -> str:
        """The model every request is sent to."""
        return self._model

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        width_px: int,
        height_px: int,
        moderation: str,
        seed: int | None,  # noqa: ARG002 — OpenAI images API has no seed param today
    ) -> GeneratedImage:
        size = f"{width_px}x{height_px}"
        if not size_is_allowed(self._model, width_px, height_px):
            raise ValueError(f"{self._model} does not accept size {size}")
        kwargs = {
            "model": self._model,
            "prompt": prompt,
            "size": size,
            "moderation": moderation,
            "n": 1,
        }
        mapped: ProviderError | None = None
        try:
            if reference_path is not None:
                with open(reference_path, "rb") as fh:
                    response = self._client.images.edit(image=fh, **kwargs)  # type: ignore[attr-defined]
            else:
                response = self._client.images.generate(**kwargs)  # type: ignore[attr-defined]
        except Exception as e:
            secrets = [self._api_key.get_secret_value()] if self._api_key else []
            mapped = _map_openai_error(e, secrets)
            if mapped is None:
                raise
        if mapped is not None:
            # `from None`, and outside the handler, so the raw SDK error (its
            # unredacted text) is neither __cause__ nor __context__ (B904-clean).
            raise mapped from None

        data = getattr(response, "data", None) or []
        b64 = getattr(data[0], "b64_json", None) if data else None
        if not b64:
            raise ProviderError("the provider returned no image", kind="refused")
        png_bytes = base64.b64decode(b64)
        cost = getattr(response, "cost_usd", None)
        return GeneratedImage(
            png_bytes=png_bytes,
            cost_usd=float(cost) if cost is not None else _FALLBACK_COST_USD,
            model_version=getattr(response, "model", None) or self._model,
        )


def _map_openai_error(e: Exception, secrets: Iterable[str]) -> ProviderError | None:
    """Classify an openai-python exception; ``None`` if it is not one.

    Anything unrecognised (a bug, an ``OSError``) is re-raised unchanged
    by the caller rather than relabelled as a provider error.
    """
    try:
        import openai
    except ImportError:
        return None
    if isinstance(e, openai.APIConnectionError):  # includes APITimeoutError
        return ProviderError(str(e), kind="transient", secrets=secrets)
    if isinstance(e, openai.APIStatusError):
        status = e.status_code
        response = getattr(e, "response", None)
        headers = getattr(response, "headers", None)
        retry_after = parse_retry_after(headers.get("retry-after") if headers is not None else None)
        kind: ProviderErrorKind
        if status == 400 and e.code in _REFUSAL_CODES:
            kind = "refused"
        elif status in (401, 403):  # 403: unverified org / unsupported region
            kind = "environment"
        elif status == 429:
            kind = "environment" if e.code == "insufficient_quota" else "transient"
        elif status in (408, 409) or status >= 500:
            kind = "transient"
        else:  # 400, 404, 422 and any other 4xx
            kind = "usage"
        return ProviderError(
            str(e), kind=kind, status=status, retry_after_s=retry_after, secrets=secrets
        )
    if isinstance(e, openai.APIError):  # e.g. a response that fails validation
        return ProviderError(str(e), kind="transient", secrets=secrets)
    return None


def make_image_client(model: str = DEFAULT_AI_MODEL) -> OpenAIImageClient:
    """Construct a live OpenAI client, validating extras + key first.

    Raises :class:`AIDependencyError` with an actionable message when the
    ``[ai]`` extra is not installed or ``OPENAI_API_KEY`` is unset.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise AIDependencyError(
            "OPENAI_API_KEY is not set. AI imagery requires an OpenAI API "
            "key (and `pip install holiday-card[ai]`)."
        )
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover - exercised only without extra
        raise AIDependencyError(
            "the AI extra is not installed. Run `pip install holiday-card[ai]`."
        ) from e
    # A pinned host (the env's OPENAI_BASE_URL is ignored) and no retries:
    # an image generation is billed and not idempotent.
    sdk_client = OpenAI(api_key=api_key, base_url=OPENAI_BASE_URL, max_retries=0, timeout=OPENAI_TIMEOUT_S)
    return OpenAIImageClient(sdk_client, model=model, api_key=SecretStr(api_key))
