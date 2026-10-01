"""Provenance sidecars + first-use consent for AI imagery (Leapfrog 3).

Two non-negotiables from the panel (consensus-ai-feature.md, agreements
A2 and A5):

1. **Bake-to-disk with a provenance sidecar.** Every generated asset
   gets a sibling ``<asset>.license.yaml`` capturing the prompt, model,
   seed, timestamp, the provider-reported cost (or ``unknown``), the
   provider and request shape, the provider's policy URLs at generation
   time, and a placeholder for the user's own commercial-use determination. The
   bake also marks the PNG with an ``iTXt`` chunk (:data:`AI_MARKER_KEY`)
   naming its sidecar. :func:`require_sidecar` is the one check, and it is
   enforced by ``compiler.embedded_ai_assets`` (every compile, so
   ``create``, ``preview`` and ``validate``) and by
   ``generators.fill_photo_slots``, which refuses any AI asset as a photo
   (rail 8); #153 adds panel backgrounds to the compiler walk. The marker
   is detection, not DRM: an editor re-save or a JPEG conversion may drop
   it, so a sibling sidecar alone also marks a file as an AI asset (the
   legacy rule, which v1.3.0 assets rely on).

2. **First-use consent, per provider.** A one-time, logged
   acknowledgement that the user has read that provider's policies, the
   IP-responsibility caveat, and the POD-disclosure obligation. Stored as
   JSON under the user's config dir; default refusal until acknowledged.
   A v1.3.0 consent file (one flat flag) still counts for OpenAI only.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal, assert_never

import yaml
from PIL import Image
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from holiday_card.core.ai_providers import PROVIDERS, AIProvider, upstream_vendor

# No cycle: core.images never imports this module.
from holiday_card.core.images import ImageSourceError

__all__ = [
    "consent_notice",
    "LicenseRecord",
    "sidecar_path_for",
    "write_sidecar",
    "read_sidecar",
    "default_consent_path",
    "has_consented",
    "record_consent",
    "AI_MARKER_KEY",
    "AIProvenanceError",
    "AIMarker",
    "marker_text",
    "read_ai_marker",
    "is_ai_asset",
    "require_sidecar",
    "photo_slot_refusal",
    "ai_disclosure_label",
]

_HEADER = """\
holiday-card AI imagery — first-use acknowledgement
---------------------------------------------------
AI image generation is intended for PERSONAL USE. We do not recommend AI
imagery for cards you intend to sell.

By proceeding you acknowledge:
"""

_COMMON_BULLETS = """\
  * AI-generated assets may inadvertently contain protected material;
    you are responsible for what you print and sell.
  * US copyright law currently denies protection to purely AI-generated
    output, and many print-on-demand services require AI disclosure.
"""

_TRAILER = """
This acknowledgement is recorded once to {path}.
"""


def consent_notice(provider: AIProvider, *, path: Path, model: str | None = None) -> str:
    """The first-use notice for ``provider``, naming the consent file ``path``.

    For a routed provider and a ``model``, it also names the upstream vendor
    the request goes to and that vendor's terms (from the allowlist). The
    OpenAI notice is byte-identical to the v1.3.0 notice.
    """
    vendor_bullet = ""
    if model is not None and (vendor := upstream_vendor(provider, model)) is not None:
        name, terms_url, route = vendor
        vendor_bullet = (
            f"  * For {model} the upstream vendor is {name} (route {route});\n"
            f"    its terms govern the output: {terms_url}\n"
        )
    return (
        _HEADER
        + PROVIDERS[provider].consent_blurb
        + vendor_bullet
        + _COMMON_BULLETS
        + _TRAILER.format(path=path)
    )


class LicenseRecord(BaseModel):
    """Provenance sidecar for one baked AI asset.

    Serialized to ``<asset>.license.yaml`` next to the PNG. Frozen-ish in
    spirit (we never mutate after writing) but kept a plain model so it
    round-trips cleanly through YAML. Unknown keys fail loud (D4). The
    API key never appears here: no field can hold it.
    """

    model_config = ConfigDict(extra="forbid")

    prompt: str
    style: str | None = None
    reference: str | None = None
    provider: AIProvider
    requested_model: str  # the id asked for (--model, or the provider default)
    model: str  # the id actually called
    model_version: str | None = None
    provider_route: str | None = None  # the pinned OpenRouter provider_tag; None for openai
    # {"size": "WxH"} | {"aspect_ratio": …, "resolution": …} | {"aspect_ratio": …};
    # None only for a legacy v1.3.0 sidecar.
    request_shape: dict[str, str] | None = None
    generation_id: str | None = None  # X-Generation-Id when the provider returns one
    seed: int | None = None
    timestamp: str
    cost_usd: float | None = None
    # "unknown" when the provider reported no cost; also what a v1.3.0
    # sidecar (no such key) reads as, since its 0.04 may be an invented figure.
    cost_source: Literal["reported", "unknown"] = "unknown"
    media_type: str | None = None  # what the model returned; None only for legacy
    # The baked file's size; ``generated_*`` is what the model returned,
    # and ``native_ppi`` the resolution that carries into the bake.
    width_px: int | None = None
    height_px: int | None = None
    generated_width_px: int | None = None
    generated_height_px: int | None = None
    native_ppi: float | None = None
    color_profile: str = "sRGB IEC61966-2.1"
    # Captured so a later ToS change can be diffed against the policies in
    # force when the asset was baked (risk #2).
    policy_urls: list[str]
    # The user fills this in themselves; we never decide it for them.
    commercial_use_determination: str = "UNREVIEWED"
    override_reasons: list[str] = Field(default_factory=list)

    # LEGACY(v1.3.0 sidecar, O7): delete in the first release after the one that ships this.
    @model_validator(mode="before")
    @classmethod
    def _read_v1_3_0(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "openai_policy_url" not in data:
            return data
        if "provider" in data or "policy_urls" in data:
            raise ValueError(
                "sidecar mixes the legacy openai_policy_url with provider-neutral fields"
            )
        legacy = dict(data)
        policy_url = legacy.pop("openai_policy_url")
        return {
            **legacy,
            "provider": AIProvider.OPENAI.value,
            "requested_model": legacy.get("model"),
            "policy_urls": [policy_url],
            "request_shape": None,
            "generation_id": None,
            "provider_route": None,
            "media_type": None,
        }


def sidecar_path_for(asset_path: Path) -> Path:
    """Return the ``<asset>.license.yaml`` sibling path for ``asset_path``."""
    return asset_path.with_suffix(".license.yaml")


def write_sidecar(asset_path: Path, record: LicenseRecord) -> Path:
    """Write ``record`` as the sidecar next to ``asset_path``; return its path."""
    sidecar = sidecar_path_for(asset_path)
    sidecar.write_text(
        yaml.safe_dump(
            record.model_dump(mode="json"), sort_keys=False, default_flow_style=False
        )
    )
    return sidecar


def read_sidecar(asset_path: Path) -> LicenseRecord:
    """Load the sidecar for ``asset_path``.

    Raises ``FileNotFoundError`` if the sidecar is missing — the
    "refuse to embed an AI asset without provenance" rule.
    """
    sidecar = sidecar_path_for(asset_path)
    if not sidecar.exists():
        raise FileNotFoundError(
            f"missing provenance sidecar {sidecar} for AI asset {asset_path}"
        )
    data = yaml.safe_load(sidecar.read_text())
    return LicenseRecord.model_validate(data)


AI_MARKER_KEY: Final = "holiday-card:ai-generated"


class AIProvenanceError(ImageSourceError):
    """An AI asset is used without intact provenance, or where AI imagery is refused (rail 8)."""


class AIMarker(BaseModel):
    """The ``iTXt`` payload the bake writes into every AI asset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    v: Literal[1] = 1
    sidecar: str = Field(min_length=1)  # basename of the sidecar, never a path
    model: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)

    @field_validator("sidecar")
    @classmethod
    def _basename_only(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("the marker names the sidecar by basename, never a path")
        return value


def marker_text(marker: AIMarker) -> str:
    """Serialize ``marker`` as compact, sorted-key JSON (the ``iTXt`` value)."""
    return json.dumps(marker.model_dump(), sort_keys=True, separators=(",", ":"))


def read_ai_marker(path: Path) -> AIMarker | None:
    """Return the AI marker in ``path``, or ``None`` if it is not a marked PNG.

    Call it only on a file that has passed ``images.probe_image`` (the bomb
    and format checks). A marker that is present but unreadable raises
    :class:`AIProvenanceError`: a tampered marker is not "no marker" (D4).
    """
    with Image.open(path) as img:
        if img.format != "PNG":
            return None
        text = getattr(img, "text", {}).get(AI_MARKER_KEY)
    if text is None:
        return None
    try:
        return AIMarker.model_validate_json(text)
    except ValidationError as e:
        raise AIProvenanceError(
            f"AI asset {path} has an unreadable {AI_MARKER_KEY} marker; re-bake it with "
            "'holiday-card ai-asset generate'"
        ) from e


def is_ai_asset(path: Path) -> bool:
    """True if ``path`` carries the AI marker or has a sibling sidecar (legacy assets)."""
    return read_ai_marker(path) is not None or sidecar_path_for(path).exists()


def require_sidecar(path: Path) -> LicenseRecord:
    """Load and cross-check the provenance of the AI asset ``path``.

    Raises :class:`AIProvenanceError` when the file is not an AI asset, was
    renamed away from the sidecar its marker names, has no sidecar, has one
    that is not a valid :class:`LicenseRecord`, or has one whose ``model`` /
    ``timestamp`` differ from the marker's (the sidecar of another asset).
    A legacy asset (no marker) passes when its sidecar validates.
    """
    marker = read_ai_marker(path)
    sidecar = sidecar_path_for(path)
    if marker is None and not sidecar.exists():
        raise AIProvenanceError(f"{path} is not an AI asset (no marker, no sidecar)")
    if marker is not None and marker.sidecar != sidecar.name:
        raise AIProvenanceError(
            f"AI asset {path} was renamed without its sidecar: its marker names "
            f"{marker.sidecar}, not {sidecar.name}; rename it back or re-bake it"
        )
    try:
        record = read_sidecar(path)
    except FileNotFoundError as e:
        raise AIProvenanceError(
            f"AI asset {path} has no provenance sidecar {sidecar.name}; re-bake it with "
            "'holiday-card ai-asset generate' or restore the sidecar"
        ) from e
    except (yaml.YAMLError, ValidationError, OSError, UnicodeDecodeError) as e:
        raise AIProvenanceError(
            f"AI asset {path} has an unreadable provenance sidecar {sidecar.name}; "
            "re-bake it with 'holiday-card ai-asset generate' or restore the sidecar"
        ) from e
    if marker is not None:
        for field_name in ("model", "timestamp"):
            if getattr(marker, field_name) != getattr(record, field_name):
                raise AIProvenanceError(
                    f"AI asset {path} does not match its sidecar {sidecar.name}: the "
                    f"marker's {field_name} is {getattr(marker, field_name)!r}, the "
                    f"sidecar's {getattr(record, field_name)!r} (a sidecar from another asset?)"
                )
    return record


def photo_slot_refusal(path: Path) -> AIProvenanceError:
    """The rail-8 error for the AI asset ``path`` offered as a photo."""
    try:
        model = f"model {require_sidecar(path).model}"
    except AIProvenanceError as e:
        model = f"model unknown: {e}"
    return AIProvenanceError(
        f"{path} is an AI-generated asset ({model}); AI imagery never replaces a photo "
        "(rail 8: no photo replacement). Place it as a template image element instead."
    )


def ai_disclosure_label(record: LicenseRecord) -> str:
    """The human-readable label a disclosure names for ``record``.

    The ONLY place the label is built: a routed model is ``<model> via
    openrouter``; a direct provider's label is the model alone.
    """
    match record.provider:
        case AIProvider.OPENAI:
            return record.model
        case AIProvider.OPENROUTER:
            return f"{record.model} via {record.provider.value}"
        case _:
            assert_never(record.provider)


def default_consent_path() -> Path:
    """Return the consent log path under the user's config dir.

    Honors ``XDG_CONFIG_HOME``; falls back to ``~/.config``.
    """
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "holiday-card" / "ai-consent.json"


def _read_consent(path: Path) -> dict[str, dict[str, object]]:
    """The per-provider consent entries in ``path``; ``{}`` when unreadable (fail closed).

    A v1.3.0 flat file (top-level ``acknowledged``) reads as OpenAI's entry
    only. Keys that are not :class:`AIProvider` values are kept, so a newer
    version's provider survives a downgrade's write.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    if "providers" in data:
        providers = data["providers"]
        return dict(providers) if isinstance(providers, dict) else {}
    if data.get("acknowledged") is True:
        policy_url = data.get("policy_url")
        return {
            AIProvider.OPENAI.value: {
                "acknowledged": True,
                "timestamp": data.get("timestamp"),
                "policy_urls": [policy_url] if policy_url is not None else [],
            }
        }
    return {}


def _acknowledged(entry: object) -> bool:
    return isinstance(entry, dict) and entry.get("acknowledged") is True


def has_consented(path: Path, provider: AIProvider) -> bool:
    """Return ``True`` if ``path`` records ``provider``'s acknowledgement (strictly ``true``)."""
    return _acknowledged(_read_consent(path).get(provider.value))


def record_consent(path: Path, provider: AIProvider) -> None:
    """Record ``provider``'s acknowledgement in ``path`` (creating parents).

    Other providers' entries are kept, an existing acknowledgement of
    ``provider`` keeps its timestamp, and a v1.3.0 file is migrated; the
    write is atomic (a temp file in the same directory, then ``os.replace``).
    """
    providers = _read_consent(path)
    # An existing acknowledgement keeps its date: that is when the user consented.
    if not _acknowledged(providers.get(provider.value)):
        providers[provider.value] = {
            "acknowledged": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "policy_urls": list(PROVIDERS[provider].policy_urls),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({"providers": providers}, indent=2))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
