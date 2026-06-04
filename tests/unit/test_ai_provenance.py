"""Provenance + first-use-consent tests for AI imagery (Leapfrog 3).

Every baked AI asset gets a sibling ``<asset>.license.yaml`` sidecar
(consensus-ai-feature.md, "Sidecar provenance YAML"), and the first use
of the feature is gated behind a logged consent acknowledgement. These
tests pin both.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from holiday_card.core.ai_provenance import (
    OPENAI_USAGE_POLICY_URL,
    LicenseRecord,
    has_consented,
    read_sidecar,
    record_consent,
    sidecar_path_for,
    write_sidecar,
)


def _record() -> LicenseRecord:
    return LicenseRecord(
        prompt="watercolor pine bough border",
        style="watercolor",
        reference="fonts/curated/sample.png",
        model="gpt-image-2",
        seed=42,
        timestamp="2027-01-15T10:00:00Z",
        cost_usd=0.04,
        width_px=1280,
        height_px=1792,
    )


class TestSidecarPath:
    def test_sidecar_is_sibling_with_license_yaml_suffix(self) -> None:
        assert sidecar_path_for(Path("assets/ai/border.png")) == Path(
            "assets/ai/border.license.yaml"
        )


class TestLicenseRecord:
    def test_defaults_include_policy_url_and_srgb_profile(self) -> None:
        record = _record()
        assert record.openai_policy_url == OPENAI_USAGE_POLICY_URL
        assert record.color_profile == "sRGB IEC61966-2.1"
        # Commercial-use determination is an explicit placeholder for the user.
        assert record.commercial_use_determination == "UNREVIEWED"


class TestSidecarRoundTrip:
    def test_write_then_read_round_trips(self, tmp_path: Path) -> None:
        asset = tmp_path / "border.png"
        asset.write_bytes(b"\x89PNG fake")
        record = _record()

        sidecar = write_sidecar(asset, record)

        assert sidecar == tmp_path / "border.license.yaml"
        assert sidecar.exists()
        loaded = read_sidecar(asset)
        assert loaded == record

    def test_read_missing_sidecar_raises(self, tmp_path: Path) -> None:
        asset = tmp_path / "no-sidecar.png"
        asset.write_bytes(b"x")
        with pytest.raises(FileNotFoundError):
            read_sidecar(asset)


class TestConsentGate:
    def test_fresh_path_has_not_consented(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "ai-consent.json"
        assert has_consented(consent_file) is False

    def test_recording_consent_persists(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "ai-consent.json"
        record_consent(consent_file)
        assert has_consented(consent_file) is True

    def test_record_consent_creates_parent_dirs(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "nested" / "dir" / "ai-consent.json"
        record_consent(consent_file)
        assert consent_file.exists()
        assert has_consented(consent_file) is True
