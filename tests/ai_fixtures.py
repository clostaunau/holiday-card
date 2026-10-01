"""Bake real AI assets in tests, with no network and no API key (#144).

``bake_fake_ai_asset`` runs the real ``generate_ai_asset`` with an in-test
``ImageClient`` that returns a solid PNG, so the file on disk carries the
same marker and sidecar a live bake writes. #145 and #153 reuse it.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from holiday_card.core.ai_assets import (
    AIRequest,
    GeneratedImage,
    PixelSize,
    RequestShape,
    generate_ai_asset,
)
from holiday_card.core.ai_provenance import record_consent
from holiday_card.core.ai_providers import AIProvider
from holiday_card.core.models import OccasionType

BAKE_TIMESTAMP = "2026-10-02T09:14:03+00:00"


@dataclass
class SolidImageClient:
    """An ``ImageClient`` that returns one solid-colour PNG of the requested size."""

    model: str
    color: tuple[int, int, int]
    provider: AIProvider = AIProvider.OPENAI

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        shape: RequestShape,
        seed: int | None,
    ) -> GeneratedImage:
        del prompt, reference_path, seed  # the ImageClient signature; unused here
        assert isinstance(shape, PixelSize)
        buf = io.BytesIO()
        Image.new("RGB", (shape.width_px, shape.height_px), self.color).save(buf, "PNG")
        return GeneratedImage(
            image_bytes=buf.getvalue(), media_type="image/png",
            cost_usd=None, cost_source="unknown",
        )


def bake_fake_ai_asset(
    dir: Path,
    name: str = "art.png",
    *,
    model: str = "gpt-image-2",
    size: tuple[int, int] = (1314, 1824),
    color: tuple[int, int, int] = (10, 120, 60),
    timestamp: str = BAKE_TIMESTAMP,
) -> Path:
    """Bake ``dir / name`` (+ its sidecar) through the real bake; return the asset path."""
    consent = dir / ".ai-consent.json"
    record_consent(consent)
    client = SolidImageClient(model=model, color=color)
    out = dir / name
    generate_ai_asset(
        prompt="watercolor pine bough border",
        occasion=OccasionType.CHRISTMAS,
        out_path=out,
        request=AIRequest(
            prompt="watercolor pine bough border",
            width_px=size[0], height_px=size[1], shape=PixelSize(*size),
            provider=client.provider, model=model, dpi=300, reference_path=None,
        ),
        client=client,
        consent_path=consent,
        timestamp=timestamp,
    )
    return out
