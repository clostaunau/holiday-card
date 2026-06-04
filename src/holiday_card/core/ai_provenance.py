"""Provenance sidecars + first-use consent for AI imagery (Leapfrog 3).

Two non-negotiables from the panel (consensus-ai-feature.md, agreements
A2 and A5):

1. **Bake-to-disk with a provenance sidecar.** Every generated asset
   gets a sibling ``<asset>.license.yaml`` capturing the prompt, model,
   seed, timestamp, cost, the OpenAI policy URL at generation time, and
   a placeholder for the user's own commercial-use determination. The
   render pipeline refuses to embed any AI asset whose sidecar is
   missing — this is what preserves the reproducibility moat.

2. **First-use consent.** A one-time, logged acknowledgement that the
   user has read the OpenAI usage policy, the IP-responsibility caveat,
   and the POD-disclosure obligation. Stored as JSON under the user's
   config dir; default refusal until acknowledged.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

__all__ = [
    "OPENAI_USAGE_POLICY_URL",
    "CONSENT_NOTICE",
    "LicenseRecord",
    "sidecar_path_for",
    "write_sidecar",
    "read_sidecar",
    "default_consent_path",
    "has_consented",
    "record_consent",
]

# Captured into every sidecar so a later OpenAI ToS change can be diffed
# against the policy in force when the asset was baked (risk #2).
OPENAI_USAGE_POLICY_URL = "https://openai.com/policies/usage-policies"

CONSENT_NOTICE = """\
holiday-card AI imagery — first-use acknowledgement
---------------------------------------------------
AI image generation is intended for PERSONAL USE. We do not recommend AI
imagery for cards you intend to sell.

By proceeding you acknowledge:
  * You have read the OpenAI usage policy: {policy}
  * AI-generated assets may inadvertently contain protected material;
    you are responsible for what you print and sell.
  * US copyright law currently denies protection to purely AI-generated
    output, and many print-on-demand services require AI disclosure.

This acknowledgement is recorded once to {path}.
""".format(policy=OPENAI_USAGE_POLICY_URL, path="{path}")


class LicenseRecord(BaseModel):
    """Provenance sidecar for one baked AI asset.

    Serialized to ``<asset>.license.yaml`` next to the PNG. Frozen-ish in
    spirit (we never mutate after writing) but kept a plain model so it
    round-trips cleanly through YAML.
    """

    prompt: str
    style: str | None = None
    reference: str | None = None
    model: str = "gpt-image-2"
    model_version: str | None = None
    seed: int | None = None
    timestamp: str
    cost_usd: float | None = None
    width_px: int | None = None
    height_px: int | None = None
    color_profile: str = "sRGB IEC61966-2.1"
    openai_policy_url: str = OPENAI_USAGE_POLICY_URL
    # The user fills this in themselves; we never decide it for them.
    commercial_use_determination: str = "UNREVIEWED"
    override_reasons: list[str] = Field(default_factory=list)


def sidecar_path_for(asset_path: Path) -> Path:
    """Return the ``<asset>.license.yaml`` sibling path for ``asset_path``."""
    return asset_path.with_suffix(".license.yaml")


def write_sidecar(asset_path: Path, record: LicenseRecord) -> Path:
    """Write ``record`` as the sidecar next to ``asset_path``; return its path."""
    sidecar = sidecar_path_for(asset_path)
    sidecar.write_text(
        yaml.safe_dump(record.model_dump(), sort_keys=False, default_flow_style=False)
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


def default_consent_path() -> Path:
    """Return the consent log path under the user's config dir.

    Honors ``XDG_CONFIG_HOME``; falls back to ``~/.config``.
    """
    import os

    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "holiday-card" / "ai-consent.json"


def has_consented(path: Path) -> bool:
    """Return ``True`` if a consent record exists and is acknowledged."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("acknowledged"))


def record_consent(path: Path) -> None:
    """Persist a consent acknowledgement to ``path`` (creating parents)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "acknowledged": True,
        "timestamp": datetime.now(UTC).isoformat(),
        "policy_url": OPENAI_USAGE_POLICY_URL,
    }
    path.write_text(json.dumps(payload, indent=2))
