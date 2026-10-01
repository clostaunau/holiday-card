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

from collections.abc import Iterable

from pydantic import SecretStr

from holiday_card.core.ai_assets import (
    GeneratedImage,
    ImageMediaType,
    PixelSize,
    RequestShape,
    decode_b64_image,
    size_is_allowed,
)
from holiday_card.core.ai_errors import ProviderError, ProviderErrorKind, parse_retry_after
from holiday_card.core.ai_providers import AIDependencyError, AIProvider

__all__ = ["OpenAIImageClient", "make_openai_client", "OPENAI_TIMEOUT_S"]

_PINNED_BASE_URL = "https://api.openai.com/v1"
OPENAI_TIMEOUT_S = 300.0
_REFUSAL_CODES = frozenset({"moderation_blocked", "content_policy_violation"})
# 429s that retrying cannot fix: out of credit or over a spend / usage limit
# (OpenAI error-code guide, accessed 2026-09-30).
_QUOTA_CODES = frozenset(
    {
        "insufficient_quota",
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    }
)
# ImagesResponse.output_format -> media type; PNG is the documented default.
_MEDIA_TYPES: dict[str, ImageMediaType] = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


class OpenAIImageClient:
    """Thin wrapper over the OpenAI Images API.

    Constructed by :func:`make_openai_client` (via
    :func:`holiday_card.core.ai_providers.make_image_client`, which checks
    the model and ``OPENAI_API_KEY`` first).
    """

    def __init__(
        self,
        client: object,
        model: str,
        *,
        api_key: SecretStr | None = None,
    ) -> None:
        size_is_allowed(model, 1024, 1024)  # unknown model -> ValueError (D4)
        self._client = client
        self._model = model
        # Used only to redact provider error text; never logged.
        self._api_key = api_key

    @property
    def provider(self) -> AIProvider:
        """Always :attr:`AIProvider.OPENAI`."""
        return AIProvider.OPENAI

    @property
    def model(self) -> str:
        """The model every request is sent to."""
        return self._model

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        shape: RequestShape,
        seed: int | None,
    ) -> GeneratedImage:
        """Generate (or, with a reference, edit) one image.

        Raises:
            ValueError: Before any API call, for a non-pixel ``shape``, any
                ``seed`` (the Images API has none) or a size ``model``
                does not accept.
        """
        if not isinstance(shape, PixelSize):
            raise ValueError(f"openai takes a pixel size, got {shape!r}")
        if seed is not None:
            raise ValueError(
                f"openai model {self._model!r} takes no seed; the image could not be reproduced"
            )
        size = f"{shape.width_px}x{shape.height_px}"
        if not size_is_allowed(self._model, shape.width_px, shape.height_px):
            raise ValueError(f"{self._model} does not accept size {size}")
        kwargs = {
            "model": self._model,
            "prompt": prompt,
            "size": size,
            "moderation": "auto",
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
        output_format = getattr(response, "output_format", None)
        # The SDK's ImagesResponse carries token `usage`, never a USD cost,
        # so the cost is unknown rather than estimated (#141).
        return GeneratedImage(
            image_bytes=decode_b64_image(b64),
            media_type=_MEDIA_TYPES.get(output_format or "png", "image/png"),
            cost_usd=None,
            cost_source="unknown",
            model_version=getattr(response, "model", None) or self._model,
            generation_id=None,
            provider_route=None,
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
            kind = "environment" if e.code in _QUOTA_CODES else "transient"
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


def make_openai_client(*, api_key: str, model: str) -> OpenAIImageClient:
    """Construct a live OpenAI client for ``model``.

    Raises:
        AIDependencyError: If the ``[ai]`` extra is not installed.
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise AIDependencyError(
            "the AI extra is not installed. Run `pip install holiday-card[ai]`."
        ) from e
    # A pinned host (the env's OPENAI_BASE_URL is ignored) and no retries:
    # an image generation is billed and not idempotent.
    sdk_client = OpenAI(api_key=api_key, base_url=_PINNED_BASE_URL, max_retries=0, timeout=OPENAI_TIMEOUT_S)
    return OpenAIImageClient(sdk_client, model=model, api_key=SecretStr(api_key))
