"""POD-aware sizing + authoring-time generate orchestration (Leapfrog 3).

This is the seam the panel endorsed (consensus-ai-feature.md): an
authoring-time ``ai-asset generate`` step that bakes one image to disk
with a provenance sidecar and **never** sits in the render path. The
actual model call is an injected :class:`ImageClient`, so the
orchestration is fully testable without a network or ``OPENAI_API_KEY``.

Responsibilities, in order:

1. **Consent** — refuse unless the first-use acknowledgement is logged.
2. **Hard rails** — refuse sympathy-class / trademark / religious /
   likeness requests unless ``override=True`` (the
   ``--i-know-what-im-doing`` path), recording the overridden reasons.
3. **Generate** — call the client with ``moderation="auto"`` and the
   POD-resolved pixel dimensions.
4. **Bake** — write the PNG tagged as sRGB IEC61966-2.1 and a sibling
   ``<asset>.license.yaml`` provenance sidecar.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageCms

from holiday_card.core.ai_provenance import (
    LicenseRecord,
    has_consented,
    write_sidecar,
)
from holiday_card.core.ai_rails import RailViolation, evaluate_rails
from holiday_card.core.models import OccasionType
from holiday_card.utils.measurements import DEFAULT_BLEED

__all__ = [
    "AIRequest",
    "GeneratedImage",
    "GenerationResult",
    "ImageClient",
    "ConsentRequiredError",
    "RailRefusedError",
    "round_to_multiple",
    "build_ai_request",
    "generate_ai_asset",
]

SRGB_PROFILE_NAME = "sRGB IEC61966-2.1"


class ConsentRequiredError(RuntimeError):
    """Raised when generation is attempted before first-use consent."""


class RailRefusedError(RuntimeError):
    """Raised when a hard rail blocks generation and no override was given."""

    def __init__(self, violations: list[RailViolation]) -> None:
        self.violations = violations
        joined = "; ".join(f"[{v.category}] {v.reason}" for v in violations)
        super().__init__(f"AI imagery refused by hard rails: {joined}")


@dataclass(frozen=True)
class AIRequest:
    """A resolved, POD-aware generation request (no model call yet)."""

    prompt: str
    width_px: int
    height_px: int
    dpi: int = 300
    reference_path: str | None = None
    moderation: str = "auto"


@dataclass(frozen=True)
class GeneratedImage:
    """What an :class:`ImageClient` returns: raw PNG bytes + metadata."""

    png_bytes: bytes
    cost_usd: float
    model_version: str | None = None


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a successful bake."""

    asset_path: Path
    sidecar_path: Path
    cost_usd: float
    overridden: list[RailViolation] = field(default_factory=list)


class ImageClient(Protocol):
    """The injectable image-generation seam.

    The real implementation wraps the OpenAI Images API; tests inject a
    fake. Keeping this a Protocol is what keeps the OpenAI dependency out
    of the import graph unless the user installs ``holiday-card[ai]``.
    """

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        width_px: int,
        height_px: int,
        moderation: str,
        seed: int | None,
    ) -> GeneratedImage: ...


def round_to_multiple(n: int, base: int = 16) -> int:
    """Round ``n`` to the nearest positive multiple of ``base``.

    Never returns zero — POD pipelines reject a zero-pixel dimension.
    """
    # Round half *up* (not banker's rounding) so a print target never
    # silently under-resolves on the .5 boundary.
    rounded = int(n / base + 0.5) * base
    return rounded if rounded >= base else base


def build_ai_request(
    *,
    prompt: str,
    trim_width_in: float,
    trim_height_in: float,
    bleed_in: float = DEFAULT_BLEED,
    dpi: int = 300,
    reference_path: str | None = None,
    moderation: str = "auto",
) -> AIRequest:
    """Resolve print geometry to a pixel-sized request.

    The image is sized to **trim + 2×bleed** so the model paints into the
    bleed band; the render pipeline crops inward to trim. Pixel
    dimensions are computed at ``dpi`` and rounded to /16 multiples (POD
    services round-trip /16 cleanly). Never lets the user sit at
    1024×1024 against a print target.
    """
    full_w_in = trim_width_in + 2 * bleed_in
    full_h_in = trim_height_in + 2 * bleed_in
    return AIRequest(
        prompt=prompt,
        width_px=round_to_multiple(round(full_w_in * dpi)),
        height_px=round_to_multiple(round(full_h_in * dpi)),
        dpi=dpi,
        reference_path=reference_path,
        moderation=moderation,
    )


def _srgb_profile_bytes() -> bytes:
    """Return an sRGB ICC profile as bytes for embedding into the PNG."""
    profile = ImageCms.createProfile("sRGB")
    return ImageCms.ImageCmsProfile(profile).tobytes()


def generate_ai_asset(
    *,
    prompt: str,
    occasion: OccasionType,
    out_path: Path,
    request: AIRequest,
    client: ImageClient,
    consent_path: Path,
    timestamp: str,
    style: str | None = None,
    seed: int | None = None,
    model: str = "gpt-image-2",
    override: bool = False,
) -> GenerationResult:
    """Bake one AI asset to disk with a provenance sidecar.

    Enforces consent and hard rails *before* spending any money, then
    writes an sRGB-tagged PNG and a ``<asset>.license.yaml`` sidecar.
    """
    if not has_consented(consent_path):
        raise ConsentRequiredError(
            "AI imagery requires a one-time consent acknowledgement first."
        )

    violations = evaluate_rails(occasion, prompt)
    if violations and not override:
        raise RailRefusedError(violations)

    generated = client.generate(
        prompt=prompt,
        reference_path=request.reference_path,
        width_px=request.width_px,
        height_px=request.height_px,
        moderation=request.moderation,
        seed=seed,
    )

    # Re-encode as sRGB-tagged PNG (the model emits untagged sRGB).
    with Image.open(io.BytesIO(generated.png_bytes)) as img:
        rgb = img.convert("RGB")
        width_px, height_px = rgb.size
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(out_path, format="PNG", icc_profile=_srgb_profile_bytes())

    record = LicenseRecord(
        prompt=prompt,
        style=style,
        reference=request.reference_path,
        model=model,
        model_version=generated.model_version,
        seed=seed,
        timestamp=timestamp,
        cost_usd=generated.cost_usd,
        width_px=width_px,
        height_px=height_px,
        color_profile=SRGB_PROFILE_NAME,
        override_reasons=[f"[{v.category}] {v.reason}" for v in violations],
    )
    sidecar = write_sidecar(out_path, record)

    return GenerationResult(
        asset_path=out_path,
        sidecar_path=sidecar,
        cost_usd=generated.cost_usd,
        overridden=violations if override else [],
    )
