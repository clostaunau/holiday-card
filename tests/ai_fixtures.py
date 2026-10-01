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
    transparent: bool = False  # a motif: ``color`` in the middle half, transparent around it

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        shape: RequestShape,
        seed: int | None,
        transparent: bool = False,
    ) -> GeneratedImage:
        del prompt, reference_path, seed  # the ImageClient signature; unused here
        assert isinstance(shape, PixelSize)
        assert transparent == self.transparent
        w, h = shape.width_px, shape.height_px
        if transparent:
            img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
            img.paste((*self.color, 255), (w // 4, h // 4, 3 * w // 4, 3 * h // 4))
        else:
            img = Image.new("RGB", (w, h), self.color)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return GeneratedImage(
            image_bytes=buf.getvalue(), media_type="image/png",
            cost_usd=None, cost_source="unknown", generation_id=None, provider_route=None,
        )


def bake_fake_ai_asset(
    dir: Path,
    name: str = "art.png",
    *,
    model: str = "gpt-image-2",
    size: tuple[int, int] = (1314, 1824),
    color: tuple[int, int, int] = (10, 120, 60),
    timestamp: str = BAKE_TIMESTAMP,
    transparent: bool = False,
) -> Path:
    """Bake ``dir / name`` (+ its sidecar) through the real bake; return the asset path.

    ``transparent`` bakes an RGBA motif (#169): ``color`` over the middle half
    of each axis, fully transparent around it.
    """
    consent = dir / ".ai-consent.json"
    record_consent(consent, AIProvider.OPENAI)
    client = SolidImageClient(model=model, color=color, transparent=transparent)
    out = dir / name
    generate_ai_asset(
        prompt="watercolor pine bough border",
        occasion=OccasionType.CHRISTMAS,
        out_path=out,
        request=AIRequest(
            prompt="watercolor pine bough border",
            width_px=size[0], height_px=size[1], shape=PixelSize(*size),
            provider=client.provider, model=model, dpi=300, reference_path=None,
            transparent=transparent,
        ),
        client=client,
        consent_path=consent,
        timestamp=timestamp,
    )
    return out
