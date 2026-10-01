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
3. **Generate** — call the client with the request shape its provider
   and model accept (:func:`choose_request_shape`); a request sized for
   another model is refused.
4. **Bake** — open the model's bytes as untrusted input
   (:func:`open_generated_image`: PNG / JPEG / WebP only, matching the
   declared type, one frame, at most ``MAX_IMAGE_PIXELS``; a transparent
   request keeps the alpha and must show some), then cover-crop + LANCZOS-resample the result to exactly
   trim + 2×bleed at 300 PPI, write it as a PNG tagged sRGB IEC61966-2.1
   with ``dpi=(300, 300)`` and a sibling ``<asset>.license.yaml``
   provenance sidecar recording the generated size and native PPI.
"""

from __future__ import annotations

import base64
import binascii
import io
import itertools
import math
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, assert_never

from PIL import Image, ImageCms, PngImagePlugin

from holiday_card.core.ai_cost import CostEstimate, check_cost_cap, estimate_max_cost
from holiday_card.core.ai_openrouter_models import (
    RESOLUTION_LONG_EDGE_PX,
    aspect_ratio_value,
    openrouter_model,
)
from holiday_card.core.ai_provenance import (
    AI_MARKER_KEY,
    AIMarker,
    LicenseRecord,
    has_consented,
    marker_text,
    sidecar_path_for,
    write_sidecar,
)
from holiday_card.core.ai_providers import AIProvider, policy_urls_for
from holiday_card.core.ai_rails import RailViolation, evaluate_rails
from holiday_card.core.export_targets import ExportTarget
from holiday_card.core.images import MAX_IMAGE_PIXELS, probe_image
from holiday_card.core.models import OccasionType
from holiday_card.utils.measurements import DEFAULT_BLEED, fitted_panel_background_in

if TYPE_CHECKING:
    from holiday_card.core.ai_openrouter_models import OpenRouterModel

__all__ = [
    "MODEL_SIZE_POLICIES",
    "MODEL_SIZE_POLICIES_VERIFIED",
    "ModelSizePolicy",
    "AIRequest",
    "AssetPurpose",
    "PixelSize",
    "AspectSize",
    "RequestShape",
    "GeneratedImage",
    "GenerationResult",
    "request_shape_record",
    "ImageClient",
    "ImageMediaType",
    "CostSource",
    "MAX_IMAGE_BYTES",
    "ImagePayloadError",
    "ConsentRequiredError",
    "RailRefusedError",
    "decode_b64_image",
    "open_generated_image",
    "probe_generated_image",
    "RESOLUTION_LONG_EDGE_PX",
    "aspect_ratio_value",
    "choose_aspect_shape",
    "choose_request_shape",
    "choose_request_size",
    "size_is_allowed",
    "build_ai_request",
    "build_panel_background_request",
    "generate_ai_asset",
]

SRGB_PROFILE_NAME = "sRGB IEC61966-2.1"


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
    # Upper bound (USD) for one request at the largest size this policy can
    # emit, at quality "auto"; set only from a dated, cited OpenAI price in
    # docs/industry-review/openai-image-api-snapshot.md. None: --max-cost
    # cannot be checked for this model (#151, D4).
    max_price_usd: float | None = None


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


# The date MODEL_SIZE_POLICIES was verified against the OpenAI
# image-generation guide and the images.generate / images.edit API reference
# (see docs/industry-review/openai-image-api-snapshot.md).
MODEL_SIZE_POLICIES_VERIFIED = "2026-09-29"

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


def choose_aspect_shape(entry: OpenRouterModel, target_w: int, target_h: int) -> AspectSize:
    """The aspect ratio and resolution tier to request from ``entry`` (spec §5.3).

    The aspect is the one nearest the target's in log space (equal log
    distance = equal cover-crop); a tie goes to the narrower ratio, then the
    smaller string, so the result never depends on catalogue order. The
    tier is the smallest whose long edge covers the target's, else the
    largest offered; ``None`` when the endpoint advertises none.
    """
    t = math.log(target_w / target_h)

    def key(r: str) -> tuple[float, float, str]:
        v = aspect_ratio_value(r)
        return (round(abs(math.log(v) - t), 9), v, r)

    aspect = min(entry.aspect_ratios, key=key)
    if not entry.resolutions:
        return AspectSize(aspect, None)
    tiers = sorted(entry.resolutions, key=entry.tier_long_edge_px)
    long_edge = max(target_w, target_h)
    covering = [r for r in tiers if entry.tier_long_edge_px(r) >= long_edge]
    return AspectSize(aspect, covering[0] if covering else tiers[-1])


class ConsentRequiredError(RuntimeError):
    """Raised when generation is attempted before first-use consent."""


class RailRefusedError(RuntimeError):
    """Raised when a hard rail blocks generation and no override was given."""

    def __init__(self, violations: list[RailViolation]) -> None:
        self.violations = violations
        joined = "; ".join(f"[{v.category}] {v.reason}" for v in violations)
        super().__init__(f"AI imagery refused by hard rails: {joined}")


@dataclass(frozen=True)
class PixelSize:
    """A request sized in pixels (OpenAI's ``size``)."""

    width_px: int
    height_px: int


@dataclass(frozen=True)
class AspectSize:
    """A request sized by aspect ratio and resolution tier (OpenRouter, spec §5.3).

    ``aspect_ratio`` is an enum value such as ``"3:4"``, never ``"auto"``;
    ``resolution`` is a tier (``"1K"``, ``"2K"`` …) or ``None`` when the
    endpoint has none.
    """

    aspect_ratio: str
    resolution: str | None


RequestShape = PixelSize | AspectSize

# What a bake is sized for: the whole page (trim + 2×bleed) or a panel's
# ``background_image`` on a fitting target (#168).
AssetPurpose = Literal["page", "panel_background"]


@dataclass(frozen=True)
class AIRequest:
    """A resolved, POD-aware generation request (no model call yet).

    ``width_px`` × ``height_px`` is the exact baked size (trim + 2×bleed at
    ``dpi`` for a ``page``, the placed background rect for a
    ``panel_background``); ``shape`` is what is sent to ``provider`` /
    ``model``, whose output the bake resamples to the target.
    ``purpose`` and ``export_target`` are recorded in the sidecar.
    """

    prompt: str
    width_px: int
    height_px: int
    shape: RequestShape
    provider: AIProvider
    model: str
    dpi: int = 300
    reference_path: str | None = None
    purpose: AssetPurpose = "page"
    export_target: str | None = None
    transparent: bool = False  # a motif on a transparent background (#169)


ImageMediaType = Literal["image/png", "image/jpeg", "image/webp"]
CostSource = Literal["reported", "unknown"]

MAX_IMAGE_BYTES = 32 * 1024 * 1024
"""Largest decoded model image accepted (spec §6.3)."""

# Pillow format -> the media type it satisfies. MPO is a JPEG with an MPF
# marker (as in core/images.py); a multi-frame one is refused anyway.
_PILLOW_MEDIA_TYPES: dict[str, ImageMediaType] = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "MPO": "image/jpeg",
    "WEBP": "image/webp",
}


class ImagePayloadError(ValueError):
    """The model returned bytes the bake refuses to decode (never a partial asset)."""


@dataclass(frozen=True)
class GeneratedImage:
    """What an :class:`ImageClient` returns: the encoded image + metadata.

    ``cost_usd`` is what the provider reported (``cost_source="reported"``)
    or ``None`` (``"unknown"``); a cost is never estimated.
    ``generation_id`` / ``provider_route`` are what a routing provider
    (OpenRouter) reports; direct providers pass ``None`` (no default: a
    client states them).
    """

    image_bytes: bytes
    media_type: ImageMediaType
    cost_usd: float | None
    cost_source: CostSource
    model_version: str | None = None
    generation_id: str | None = field(kw_only=True)
    provider_route: str | None = field(kw_only=True)

    def __post_init__(self) -> None:
        if (self.cost_source == "reported") != (self.cost_usd is not None):
            raise ValueError(
                f"cost_source {self.cost_source!r} does not match cost_usd {self.cost_usd!r}: "
                "'reported' needs a cost, 'unknown' must have none"
            )


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a successful bake."""

    asset_path: Path
    sidecar_path: Path
    cost_usd: float | None
    cost_source: CostSource
    width_px: int
    height_px: int
    native_ppi: float
    policy_urls: tuple[str, ...]
    provider_route: str | None  # the pinned OpenRouter endpoint; None for a direct provider
    overridden: list[RailViolation] = field(default_factory=list)
    cost_estimate: CostEstimate | None = None  # the --max-cost upper bound; None without a cap


class ImageClient(Protocol):
    """The injectable, provider-neutral image-generation seam.

    Live clients come from :func:`holiday_card.core.ai_providers.make_image_client`;
    tests inject a fake. Keeping this a Protocol is what keeps provider SDKs
    out of the import graph unless the user installs ``holiday-card[ai]``.
    ``provider`` / ``model`` are what the client calls; the sidecar records
    the model. A client refuses a ``shape``, ``seed`` or ``transparent``
    background its model cannot take. The returned bytes are untrusted: the bake decodes them only
    through :func:`open_generated_image`.
    """

    @property
    def provider(self) -> AIProvider: ...

    @property
    def model(self) -> str: ...

    def generate(
        self,
        *,
        prompt: str,
        reference_path: str | None,
        shape: RequestShape,
        seed: int | None,
        transparent: bool = False,
    ) -> GeneratedImage: ...


def decode_b64_image(b64: str, *, max_bytes: int = MAX_IMAGE_BYTES) -> bytes:
    """Decode a provider's base64 image, refusing oversize or malformed input.

    The length is checked before anything is decoded, and characters
    outside the base64 alphabet are an error rather than silently skipped.

    Raises:
        ImagePayloadError: If the text could decode to more than
            ``max_bytes`` or is not valid base64.
    """
    if len(b64) > 4 * math.ceil(max_bytes / 3):
        raise ImagePayloadError(
            f"the base64 image is {len(b64)} characters, over the {max_bytes}-byte limit"
        )
    try:
        return base64.b64decode(b64, validate=True)
    except binascii.Error as e:
        raise ImagePayloadError("the image is not valid base64") from e


@contextmanager
def _checked_image(image_bytes: bytes, media_type: ImageMediaType) -> Iterator[Image.Image]:
    """Open ``image_bytes`` header-only and apply every refusal; no pixel is decoded.

    Exceptions raised inside the ``with`` body are mapped the same way.
    """
    try:
        with warnings.catch_warnings():
            # Pillow warns (not raises) between its own limit and 2x it.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes), formats=["PNG", "JPEG", "WEBP"]) as img:
                found = _PILLOW_MEDIA_TYPES.get(img.format or "")
                if found != media_type:
                    raise ImagePayloadError(
                        f"the image is {img.format or 'an unknown format'}, "
                        f"not the declared {media_type}"
                    )
                width, height = img.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise ImagePayloadError(
                        f"the image is {width}x{height} ({width * height / 1e6:.1f} "
                        f"megapixels); the limit is {MAX_IMAGE_PIXELS / 1e6:.0f} megapixels"
                    )
                frames = getattr(img, "n_frames", 1)
                if frames > 1:
                    raise ImagePayloadError(f"the image has {frames} frames; only one is accepted")
                yield img
    except ImagePayloadError:
        raise
    except Image.UnidentifiedImageError as e:
        raise ImagePayloadError("the bytes are not a PNG, JPEG or WebP image") from e
    except (
        OSError,
        SyntaxError,
        ValueError,
        EOFError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as e:
        raise ImagePayloadError(f"the image could not be decoded ({type(e).__name__})") from e


def probe_generated_image(image_bytes: bytes, media_type: ImageMediaType) -> tuple[int, int]:
    """Header-only check of model output: the refusals of :func:`open_generated_image`
    without decoding a pixel. Returns ``(width, height)``.

    Raises:
        ImagePayloadError: For every refusal.
    """
    with _checked_image(image_bytes, media_type) as img:
        return img.size


def open_generated_image(
    image_bytes: bytes, media_type: ImageMediaType, *, keep_alpha: bool = False
) -> Image.Image:
    """Decode model output as untrusted input and return a loaded RGB copy
    (RGBA with ``keep_alpha`` when the image has alpha; RGB still when not).

    Only PNG, JPEG and WebP decoders are consulted (never EPS / Ghostscript),
    the bytes must be the declared ``media_type``, a single frame, and at
    most ``MAX_IMAGE_PIXELS`` (checked before any pixel is decoded).

    Raises:
        ImagePayloadError: For every refusal; the message names the reason,
            never the bytes.
    """
    with _checked_image(image_bytes, media_type) as img:
        img.load()
        if keep_alpha:
            return img.convert("RGBA") if _has_alpha(img) else img.convert("RGB")
        return img.convert("RGB")


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA", "La", "RGBa") or "transparency" in img.info


def _require_transparency(img: Image.Image) -> None:
    """Refuse a "transparent" result with no transparent pixel (#169; #140: advertised isn't proof)."""
    if img.mode != "RGBA":
        raise ImagePayloadError(
            "a transparent background was requested, but the image has no alpha channel"
        )
    low, _high = img.getchannel("A").getextrema()
    if low == 255:
        raise ImagePayloadError(
            "a transparent background was requested, but every pixel is opaque"
        )


def request_shape_record(shape: RequestShape) -> dict[str, str]:
    """The sidecar's ``request_shape`` for ``shape``: what was actually sent."""
    match shape:
        case PixelSize(width_px=w, height_px=h):
            return {"size": f"{w}x{h}"}
        case AspectSize(aspect_ratio=ratio, resolution=str(tier)):
            return {"aspect_ratio": ratio, "resolution": tier}
        case AspectSize(aspect_ratio=ratio):
            return {"aspect_ratio": ratio}
        case _:
            assert_never(shape)


def choose_request_shape(
    provider: AIProvider, model: str, target_w: int, target_h: int
) -> RequestShape:
    """The request shape ``provider`` / ``model`` accepts for a target size.

    OpenAI takes pixels: :func:`choose_request_size`. OpenRouter takes an
    aspect ratio and a resolution tier: :func:`choose_aspect_shape`.

    Raises:
        ValueError: If ``model`` has no size policy.
    """
    match provider:
        case AIProvider.OPENAI:
            return PixelSize(*choose_request_size(model, target_w, target_h))
        case AIProvider.OPENROUTER:
            return choose_aspect_shape(openrouter_model(model), target_w, target_h)
        case _:
            assert_never(provider)


def build_ai_request(
    *,
    prompt: str,
    trim_width_in: float,
    trim_height_in: float,
    bleed_in: float = DEFAULT_BLEED,
    dpi: int = 300,
    reference_path: str | None = None,
    provider: AIProvider,
    model: str,
    export_target: str | None = None,
    transparent: bool = False,
) -> AIRequest:
    """Resolve print geometry to a request for ``provider`` / ``model``.

    The baked image is exactly **trim + 2×bleed** at ``dpi`` (``round(in ×
    dpi)``, no /16 rounding) so the model paints into the bleed band and
    the render pipeline crops inward to trim. The request shape is
    :func:`choose_request_shape` (/16 rounding applies only there).
    """
    width_px = round((trim_width_in + 2 * bleed_in) * dpi)
    height_px = round((trim_height_in + 2 * bleed_in) * dpi)
    return AIRequest(
        prompt=prompt,
        width_px=width_px,
        height_px=height_px,
        shape=choose_request_shape(provider, model, width_px, height_px),
        provider=provider,
        model=model,
        dpi=dpi,
        reference_path=reference_path,
        export_target=export_target,
        transparent=transparent,
    )


def build_panel_background_request(
    *,
    prompt: str,
    target: ExportTarget,
    panel_width_in: float,
    panel_height_in: float,
    dpi: int = 300,
    reference_path: str | None = None,
    provider: AIProvider,
    model: str,
    transparent: bool = False,
) -> AIRequest:
    """A request sized for a panel ``background_image`` on ``target`` (#168).

    The bake covers the panel's background rect as placed on the page:
    :func:`~holiday_card.utils.measurements.fitted_panel_background_in`
    for the target's fit and bleed (an imposition target places the panel
    natively). Pixels round **up** (as ``images._pixels_at`` does), so the
    placed image never prints below ``dpi``.
    """
    fit = target.panel_fit if target.layout == "per-panel" else "native"
    bleed_in = target.geometry.bleed_in if target.geometry is not None else target.bleed_in
    width_in, height_in = fitted_panel_background_in(
        panel_width_in, panel_height_in, target.geometry, fit, bleed_in
    )
    width_px = math.ceil(round(width_in * dpi, 6))
    height_px = math.ceil(round(height_in * dpi, 6))
    return AIRequest(
        prompt=prompt,
        width_px=width_px,
        height_px=height_px,
        shape=choose_request_shape(provider, model, width_px, height_px),
        provider=provider,
        model=model,
        dpi=dpi,
        reference_path=reference_path,
        purpose="panel_background",
        export_target=target.name,
        transparent=transparent,
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
    # Pillow premultiplies RGBA here, so transparent colour never fringes (#169).
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
    max_cost_usd: float | None = None,
) -> GenerationResult:
    """Bake one AI asset to disk with a provenance sidecar.

    Enforces consent and hard rails *before* spending any money, then
    resamples the result to exactly ``request.width_px`` ×
    ``request.height_px`` and writes an sRGB-tagged 300 PPI PNG, marked with
    an :data:`~holiday_card.core.ai_provenance.AI_MARKER_KEY` ``iTXt`` chunk,
    and a ``<asset>.license.yaml`` sidecar. The sidecar's ``model`` is
    ``client.model``, the model actually called.

    With ``max_cost_usd``, the offline upper-bound estimate
    (:func:`~holiday_card.core.ai_cost.estimate_max_cost`) runs after the
    rails and before the call; without it, no estimate is computed.

    Raises:
        ValueError: If ``request`` was sized for another provider or model
            than ``client`` calls (checked before anything is spent).
        NoPriceOnRecordError: A cap was given but the model has no recorded
            price or bound (nothing is spent).
        CostCapExceededError: The estimate is above ``max_cost_usd``
            (nothing is spent).
    """
    if not has_consented(consent_path, client.provider):
        raise ConsentRequiredError(
            f"AI imagery with {client.provider.value} requires a one-time consent "
            "acknowledgement first."
        )

    violations = evaluate_rails(occasion, prompt)
    if violations and not override:
        raise RailRefusedError(violations)

    if (client.provider, client.model) != (request.provider, request.model):
        raise ValueError(
            f"the request was sized for {request.provider.value} model {request.model!r}, "
            f"but the client calls {client.provider.value} model {client.model!r}"
        )

    estimate: CostEstimate | None = None
    if max_cost_usd is not None:
        reference = (
            probe_image(Path(request.reference_path)) if request.reference_path else None
        )
        estimate = estimate_max_cost(
            client.provider, client.model, request.shape, prompt=prompt, reference=reference
        )
        check_cost_cap(estimate, max_cost_usd)

    generated = client.generate(
        prompt=prompt,
        reference_path=request.reference_path,
        shape=request.shape,
        seed=seed,
        transparent=request.transparent,
    )

    # Decode as untrusted input before anything touches the disk, then
    # re-encode as an sRGB-tagged PNG (drops ancillary metadata).
    target = (request.width_px, request.height_px)
    decoded = open_generated_image(
        generated.image_bytes, generated.media_type, keep_alpha=request.transparent
    )
    if request.transparent:
        _require_transparency(decoded)
    generated_w, generated_h = decoded.size
    baked = _cover_resample(decoded, target)
    # The marker names the sidecar by basename only: it travels with the
    # file, so it must not leak the author's directories.
    marker = PngImagePlugin.PngInfo()
    marker.add_itxt(AI_MARKER_KEY, marker_text(AIMarker(
        sidecar=sidecar_path_for(out_path).name, model=client.model, timestamp=timestamp,
    )))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    baked.save(
        out_path,
        format="PNG",
        icc_profile=_srgb_profile_bytes(),
        dpi=(request.dpi, request.dpi),
        pnginfo=marker,
    )
    native_ppi = min(generated_w / target[0], generated_h / target[1]) * request.dpi

    policy_urls = policy_urls_for(client.provider, client.model)
    record = LicenseRecord(
        prompt=prompt,
        style=style,
        reference=request.reference_path,
        provider=client.provider,
        requested_model=request.model,
        model=client.model,
        model_version=generated.model_version,
        provider_route=generated.provider_route,
        request_shape=request_shape_record(request.shape),
        generation_id=generated.generation_id,
        seed=seed,
        timestamp=timestamp,
        cost_usd=generated.cost_usd,
        cost_source=generated.cost_source,
        media_type=generated.media_type,
        width_px=target[0],
        height_px=target[1],
        generated_width_px=generated_w,
        generated_height_px=generated_h,
        native_ppi=native_ppi,
        color_profile=SRGB_PROFILE_NAME,
        policy_urls=list(policy_urls),
        override_reasons=[f"[{v.category}] {v.reason}" for v in violations],
        cost_cap_usd=max_cost_usd,
        cost_estimate_usd=None if estimate is None else estimate.usd,
        purpose=request.purpose,
        export_target=request.export_target,
        background="transparent" if request.transparent else None,
    )
    sidecar = write_sidecar(out_path, record)

    return GenerationResult(
        asset_path=out_path,
        sidecar_path=sidecar,
        cost_usd=generated.cost_usd,
        cost_source=generated.cost_source,
        width_px=target[0],
        height_px=target[1],
        native_ppi=native_ppi,
        policy_urls=policy_urls,
        provider_route=generated.provider_route,
        overridden=violations if override else [],
        cost_estimate=estimate,
    )
