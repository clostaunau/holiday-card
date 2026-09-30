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
3. **Generate** — call the client with ``moderation="auto"`` and a
   request size the client's model accepts (:func:`choose_request_size`).
4. **Bake** — cover-crop + LANCZOS-resample the result to exactly
   trim + 2×bleed at 300 PPI, write it as a PNG tagged sRGB IEC61966-2.1
   with ``dpi=(300, 300)`` and a sibling ``<asset>.license.yaml``
   provenance sidecar recording the generated size and native PPI.
"""

from __future__ import annotations

import io
import itertools
import math
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
    "DEFAULT_AI_MODEL",
    "MODEL_SIZE_POLICIES",
    "ModelSizePolicy",
    "AIRequest",
    "GeneratedImage",
    "GenerationResult",
    "ImageClient",
    "ConsentRequiredError",
    "RailRefusedError",
    "choose_request_size",
    "size_is_allowed",
    "build_ai_request",
    "generate_ai_asset",
]

SRGB_PROFILE_NAME = "sRGB IEC61966-2.1"

#: The one model the live client calls and the sidecar records (issue #87).
DEFAULT_AI_MODEL = "gpt-image-2"


@dataclass(frozen=True)
class ModelSizePolicy:
    """The ``size`` values one image model accepts.

    ``fixed_sizes`` lists the only accepted sizes; ``None`` means flexible,
    bounded by the remaining fields (``None`` = unbounded).
    """

    model: str
    fixed_sizes: tuple[tuple[int, int], ...] | None
    multiple: int = 16
    max_edge: int | None = None
    max_aspect: float | None = None
    min_pixels: int | None = None
    max_pixels: int | None = None


_LEGACY_SIZES = ((1024, 1024), (1536, 1024), (1024, 1536))


def _flexible(model: str) -> ModelSizePolicy:
    return ModelSizePolicy(
        model=model,
        fixed_sizes=None,
        multiple=16,
        max_edge=3840,
        max_aspect=3.0,
        min_pixels=655_360,
        max_pixels=8_294_400,
    )


# Verified 2026-09-29 against the OpenAI image-generation guide and the
# images.generate / images.edit API reference (see
# docs/industry-review/openai-image-api-snapshot.md).
MODEL_SIZE_POLICIES: dict[str, ModelSizePolicy] = {
    "gpt-image-1": ModelSizePolicy("gpt-image-1", _LEGACY_SIZES),
    "gpt-image-1-mini": ModelSizePolicy("gpt-image-1-mini", _LEGACY_SIZES),
    "gpt-image-1.5": ModelSizePolicy("gpt-image-1.5", _LEGACY_SIZES),
    "gpt-image-2": _flexible("gpt-image-2"),
    "gpt-image-2.5-sunburst": _flexible("gpt-image-2.5-sunburst"),
    "gpt-image-2.5-flare": _flexible("gpt-image-2.5-flare"),
}


def _policy(model: str) -> ModelSizePolicy:
    try:
        return MODEL_SIZE_POLICIES[model]
    except KeyError:
        known = ", ".join(sorted(MODEL_SIZE_POLICIES))
        raise ValueError(f"unknown image model {model!r}; known: {known}") from None


def _fits(p: ModelSizePolicy, w: int, h: int) -> bool:
    if p.fixed_sizes is not None:
        return (w, h) in p.fixed_sizes
    return (
        w > 0
        and h > 0
        and w % p.multiple == 0
        and h % p.multiple == 0
        and (p.max_edge is None or max(w, h) <= p.max_edge)
        and (p.max_aspect is None or max(w, h) / min(w, h) <= p.max_aspect)
        and (p.min_pixels is None or w * h >= p.min_pixels)
        and (p.max_pixels is None or w * h <= p.max_pixels)
    )


def size_is_allowed(model: str, width_px: int, height_px: int) -> bool:
    """Whether ``model`` accepts ``size=f"{width_px}x{height_px}"``.

    Raises ``ValueError`` for a model with no policy (D4).
    """
    return _fits(_policy(model), width_px, height_px)


def choose_request_size(model: str, target_w: int, target_h: int) -> tuple[int, int]:
    """Pick the API ``size`` to request for a ``target_w``×``target_h`` bake.

    Fixed-size models get the size whose aspect is closest to the target's
    (ties go to the larger area). Flexible models get the target itself
    when valid; otherwise the target with its aspect clamped, scaled
    uniformly into the pixel / edge limits and snapped to ``multiple``,
    preferring to round up so the request never under-resolves. Raises
    ``ValueError`` for an unknown model or when no valid size exists.
    """
    p = _policy(model)
    if p.fixed_sizes is not None:
        target_aspect = math.log(target_w / target_h)
        return min(
            p.fixed_sizes,
            key=lambda s: (abs(math.log(s[0] / s[1]) - target_aspect), -s[0] * s[1]),
        )
    if _fits(p, target_w, target_h):
        return target_w, target_h

    w, h = float(target_w), float(target_h)
    if p.max_aspect is not None and max(w, h) / min(w, h) > p.max_aspect:
        # Widen the short edge; the bake's cover-crop trims it back off.
        if w > h:
            h = w / p.max_aspect
        else:
            w = h / p.max_aspect
    scale = 1.0
    if p.max_edge is not None:
        scale = min(scale, p.max_edge / max(w, h))
    if p.max_pixels is not None:
        scale = min(scale, math.sqrt(p.max_pixels / (w * h)))
    if p.min_pixels is not None and w * h * scale * scale < p.min_pixels:
        scale = math.sqrt(p.min_pixels / (w * h))
    w, h = w * scale, h * scale

    m = p.multiple

    def snaps(v: float) -> set[int]:
        return {max(m, math.floor(v / m) * m), max(m, math.ceil(v / m) * m)}

    candidates = [
        (cw, ch)
        for cw, ch in itertools.product(sorted(snaps(w)), sorted(snaps(h)))
        if _fits(p, cw, ch)
    ]
    if not candidates:
        raise ValueError(
            f"no {model} size can serve a {target_w}x{target_h} px target"
        )
    # Prefer no under-resolved axis, then the smallest change.
    return min(
        candidates,
        key=lambda c: ((c[0] < w) + (c[1] < h), abs(c[0] - w) + abs(c[1] - h)),
    )


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
    """A resolved, POD-aware generation request (no model call yet).

    ``width_px`` × ``height_px`` is the exact baked size (trim + 2×bleed at
    ``dpi``); ``request_width_px`` × ``request_height_px`` is the size sent
    to ``model``, which the bake resamples to the target.
    """

    prompt: str
    width_px: int
    height_px: int
    request_width_px: int
    request_height_px: int
    model: str = DEFAULT_AI_MODEL
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
    width_px: int
    height_px: int
    native_ppi: float
    overridden: list[RailViolation] = field(default_factory=list)


class ImageClient(Protocol):
    """The injectable image-generation seam.

    The real implementation wraps the OpenAI Images API; tests inject a
    fake. Keeping this a Protocol is what keeps the OpenAI dependency out
    of the import graph unless the user installs ``holiday-card[ai]``.
    ``model`` is the model the client calls; the sidecar records it.
    """

    @property
    def model(self) -> str: ...

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


def build_ai_request(
    *,
    prompt: str,
    trim_width_in: float,
    trim_height_in: float,
    bleed_in: float = DEFAULT_BLEED,
    dpi: int = 300,
    reference_path: str | None = None,
    moderation: str = "auto",
    model: str = DEFAULT_AI_MODEL,
) -> AIRequest:
    """Resolve print geometry to a pixel-sized request.

    The baked image is exactly **trim + 2×bleed** at ``dpi`` (``round(in ×
    dpi)``, no /16 rounding) so the model paints into the bleed band and
    the render pipeline crops inward to trim. The API request size is
    :func:`choose_request_size` for ``model`` (/16 rounding applies only
    there).
    """
    width_px = round((trim_width_in + 2 * bleed_in) * dpi)
    height_px = round((trim_height_in + 2 * bleed_in) * dpi)
    request_w, request_h = choose_request_size(model, width_px, height_px)
    return AIRequest(
        prompt=prompt,
        width_px=width_px,
        height_px=height_px,
        request_width_px=request_w,
        request_height_px=request_h,
        model=model,
        dpi=dpi,
        reference_path=reference_path,
        moderation=moderation,
    )


def _srgb_profile_bytes() -> bytes:
    """Return an sRGB ICC profile as bytes for embedding into the PNG."""
    profile = ImageCms.createProfile("sRGB")
    return ImageCms.ImageCmsProfile(profile).tobytes()


def _cover_resample(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Centre-crop ``img`` to ``size``'s aspect, then LANCZOS-resize to ``size``."""
    w, h = img.size
    tw, th = size
    if w * th > tw * h:  # too wide: trim the sides
        crop_w = h * tw / th
        left = (w - crop_w) / 2
        box = (left, 0.0, left + crop_w, float(h))
    else:  # too tall: trim top and bottom
        crop_h = w * th / tw
        top = (h - crop_h) / 2
        box = (0.0, top, float(w), top + crop_h)
    if (w, h) == size:
        return img
    return img.resize(size, Image.Resampling.LANCZOS, box=box)


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
    override: bool = False,
) -> GenerationResult:
    """Bake one AI asset to disk with a provenance sidecar.

    Enforces consent and hard rails *before* spending any money, then
    resamples the result to exactly ``request.width_px`` ×
    ``request.height_px`` and writes an sRGB-tagged 300 PPI PNG and a
    ``<asset>.license.yaml`` sidecar. The sidecar's ``model`` is
    ``client.model``, the model actually called.
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
        width_px=request.request_width_px,
        height_px=request.request_height_px,
        moderation=request.moderation,
        seed=seed,
    )

    # Re-encode as sRGB-tagged PNG (the model emits untagged sRGB).
    target = (request.width_px, request.height_px)
    with Image.open(io.BytesIO(generated.png_bytes)) as img:
        rgb = img.convert("RGB")
    generated_w, generated_h = rgb.size
    baked = _cover_resample(rgb, target)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    baked.save(
        out_path,
        format="PNG",
        icc_profile=_srgb_profile_bytes(),
        dpi=(request.dpi, request.dpi),
    )
    native_ppi = min(generated_w / target[0], generated_h / target[1]) * request.dpi

    record = LicenseRecord(
        prompt=prompt,
        style=style,
        reference=request.reference_path,
        model=client.model,
        model_version=generated.model_version,
        seed=seed,
        timestamp=timestamp,
        cost_usd=generated.cost_usd,
        width_px=target[0],
        height_px=target[1],
        generated_width_px=generated_w,
        generated_height_px=generated_h,
        native_ppi=native_ppi,
        color_profile=SRGB_PROFILE_NAME,
        override_reasons=[f"[{v.category}] {v.reason}" for v in violations],
    )
    sidecar = write_sidecar(out_path, record)

    return GenerationResult(
        asset_path=out_path,
        sidecar_path=sidecar,
        cost_usd=generated.cost_usd,
        width_px=target[0],
        height_px=target[1],
        native_ppi=native_ppi,
        overridden=violations if override else [],
    )
