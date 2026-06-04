"""OpenAI image-client adapter (Leapfrog 3, ``holiday-card[ai]`` extra).

This is the only module that imports ``openai``. It is loaded lazily so
the project remains fully functional without the ``[ai]`` extra — the
panel's "refuse to be a default code path" requirement (risk #8). Tests
never touch this module; they inject a fake :class:`ImageClient`.
"""

from __future__ import annotations

import base64
import os

from holiday_card.core.ai_assets import GeneratedImage

__all__ = ["OpenAIImageClient", "make_image_client", "AIDependencyError"]

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

    def __init__(self, client: object, model: str = "gpt-image-1") -> None:
        self._client = client
        self._model = model

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
        kwargs = {
            "model": self._model,
            "prompt": prompt,
            "size": size,
            "moderation": moderation,
            "n": 1,
        }
        if reference_path is not None:
            with open(reference_path, "rb") as fh:
                response = self._client.images.edit(image=fh, **kwargs)  # type: ignore[attr-defined]
        else:
            response = self._client.images.generate(**kwargs)  # type: ignore[attr-defined]

        b64 = response.data[0].b64_json
        png_bytes = base64.b64decode(b64)
        cost = getattr(response, "cost_usd", None)
        return GeneratedImage(
            png_bytes=png_bytes,
            cost_usd=float(cost) if cost is not None else _FALLBACK_COST_USD,
            model_version=getattr(response, "model", None) or self._model,
        )


def make_image_client() -> OpenAIImageClient:
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
    return OpenAIImageClient(OpenAI(api_key=api_key))
