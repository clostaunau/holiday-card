"""Provenance + first-use-consent tests for AI imagery (Leapfrog 3).

Every baked AI asset gets a sibling ``<asset>.license.yaml`` sidecar
(consensus-ai-feature.md, "Sidecar provenance YAML"), and the first use
of the feature is gated behind a logged consent acknowledgement. These
tests pin both.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

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

    def test_cost_source_defaults_to_unknown(self) -> None:
        assert _record().cost_source == "unknown"


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

    def test_v1_3_0_sidecar_still_loads(self, tmp_path: Path) -> None:
        # Written before #141: no cost_source, and 0.04 may be the invented figure.
        asset = tmp_path / "old.png"
        asset.write_bytes(b"x")
        v130 = {
            "prompt": "watercolor pine bough border",
            "style": "watercolor",
            "reference": "ref.png",
            "model": "gpt-image-2",
            "model_version": "gpt-image-2",
            "seed": None,
            "timestamp": "2026-06-02T10:00:00",
            "cost_usd": 0.04,
            "width_px": 1314,
            "height_px": 1824,
            "generated_width_px": 1328,
            "generated_height_px": 1824,
            "native_ppi": 300.0,
            "color_profile": "sRGB IEC61966-2.1",
            "openai_policy_url": OPENAI_USAGE_POLICY_URL,
            "commercial_use_determination": "UNREVIEWED",
            "override_reasons": [],
        }
        (tmp_path / "old.license.yaml").write_text(yaml.safe_dump(v130, sort_keys=False))
        record = read_sidecar(asset)
        assert record.cost_usd == 0.04
        assert record.cost_source == "unknown"

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


# --- #144: the AI marker and the one provenance question ----------------------


def _png(path: Path, *, itxt: dict[str, str] | None = None) -> Path:
    from PIL import Image, PngImagePlugin

    info = PngImagePlugin.PngInfo()
    for key, value in (itxt or {}).items():
        info.add_itxt(key, value)
    Image.new("RGB", (8, 8), (1, 2, 3)).save(path, "PNG", pnginfo=info)
    return path


def _marked(tmp_path: Path, name: str = "art.png", **fields: str) -> Path:
    from holiday_card.core.ai_provenance import AI_MARKER_KEY, AIMarker, marker_text

    payload = {"sidecar": Path(name).with_suffix(".license.yaml").name,
               "model": "gpt-image-2", "timestamp": "2026-10-02T09:14:03+00:00", **fields}
    return _png(tmp_path / name, itxt={AI_MARKER_KEY: marker_text(AIMarker(**payload))})


def _sidecar(asset: Path, **fields: object) -> Path:
    record = LicenseRecord(**{"prompt": "p", "model": "gpt-image-2",
                              "timestamp": "2026-10-02T09:14:03+00:00", **fields})
    return write_sidecar(asset, record)


class TestAIMarker:
    def test_marker_text_round_trips(self) -> None:
        from holiday_card.core.ai_provenance import AIMarker, marker_text

        m = AIMarker(sidecar="a.license.yaml", model="m", timestamp="t")
        text = marker_text(m)
        assert AIMarker.model_validate_json(text) == m
        assert text == '{"model":"m","sidecar":"a.license.yaml","timestamp":"t","v":1}'

    def test_marker_refuses_a_path_as_sidecar(self) -> None:
        from pydantic import ValidationError

        from holiday_card.core.ai_provenance import AIMarker

        with pytest.raises(ValidationError):
            AIMarker(sidecar="/home/me/a.license.yaml", model="m", timestamp="t")

    def test_read_marker_is_none_for_a_jpeg(self, tmp_path: Path) -> None:
        from PIL import Image

        from holiday_card.core.ai_provenance import read_ai_marker

        p = tmp_path / "a.jpg"
        Image.new("RGB", (8, 8)).save(p, "JPEG")
        assert read_ai_marker(p) is None

    def test_read_marker_is_none_for_a_plain_png(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import read_ai_marker

        assert read_ai_marker(_png(tmp_path / "a.png")) is None

    def test_read_marker_is_none_for_another_itxt_key(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import read_ai_marker

        assert read_ai_marker(_png(tmp_path / "a.png", itxt={"Comment": "hi"})) is None

    def test_read_marker_parses_the_payload(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import read_ai_marker

        m = read_ai_marker(_marked(tmp_path))
        assert m is not None
        assert (m.sidecar, m.model) == ("art.license.yaml", "gpt-image-2")

    @pytest.mark.parametrize(
        "payload",
        ["not json", '{"v": 2, "sidecar": "a.license.yaml", "model": "m", "timestamp": "t"}'],
    )
    def test_read_marker_refuses_a_tampered_payload(self, tmp_path: Path, payload: str) -> None:
        from holiday_card.core.ai_provenance import (
            AI_MARKER_KEY,
            AIProvenanceError,
            read_ai_marker,
        )

        p = _png(tmp_path / "a.png", itxt={AI_MARKER_KEY: payload})
        with pytest.raises(AIProvenanceError, match="a.png"):
            read_ai_marker(p)

    def test_provenance_error_is_an_image_source_error(self) -> None:
        from holiday_card.core.ai_provenance import AIProvenanceError
        from holiday_card.core.images import ImageSourceError

        assert issubclass(AIProvenanceError, ImageSourceError)


class TestIsAIAsset:
    def test_marked_png_is_an_ai_asset(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import is_ai_asset

        assert is_ai_asset(_marked(tmp_path)) is True

    def test_unmarked_png_with_a_sidecar_is_a_legacy_ai_asset(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import is_ai_asset

        asset = _png(tmp_path / "old.png")
        _sidecar(asset)
        assert is_ai_asset(asset) is True

    def test_plain_png_is_not_an_ai_asset(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import is_ai_asset

        assert is_ai_asset(_png(tmp_path / "a.png")) is False


class TestRequireSidecar:
    def test_marked_asset_with_matching_sidecar_passes(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import require_sidecar

        asset = _marked(tmp_path)
        _sidecar(asset)
        assert require_sidecar(asset).model == "gpt-image-2"

    def test_legacy_asset_returns_its_record(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import require_sidecar

        asset = _png(tmp_path / "old.png")
        _sidecar(asset, model="gpt-image-1")
        assert require_sidecar(asset).model == "gpt-image-1"

    def test_missing_sidecar_names_it_and_the_fix(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import AIProvenanceError, require_sidecar

        with pytest.raises(AIProvenanceError) as exc:
            require_sidecar(_marked(tmp_path))
        msg = str(exc.value)
        assert "art.license.yaml" in msg
        assert "ai-asset generate" in msg
        assert isinstance(exc.value.__cause__, FileNotFoundError)

    def test_unparsable_sidecar_is_refused(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import AIProvenanceError, require_sidecar

        asset = _marked(tmp_path)
        sidecar_path_for(asset).write_text(": [unclosed")
        with pytest.raises(AIProvenanceError, match="art.license.yaml"):
            require_sidecar(asset)

    def test_invalid_sidecar_is_refused(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import AIProvenanceError, require_sidecar

        asset = _marked(tmp_path)
        sidecar_path_for(asset).write_text("prompt: p\n")
        with pytest.raises(AIProvenanceError, match="art.license.yaml"):
            require_sidecar(asset)

    def test_model_mismatch_is_refused(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import AIProvenanceError, require_sidecar

        asset = _marked(tmp_path)
        _sidecar(asset, model="flux.2-pro")
        with pytest.raises(AIProvenanceError, match="model"):
            require_sidecar(asset)

    def test_timestamp_mismatch_is_refused(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import AIProvenanceError, require_sidecar

        asset = _marked(tmp_path)
        _sidecar(asset, timestamp="2020-01-01T00:00:00+00:00")
        with pytest.raises(AIProvenanceError, match="timestamp"):
            require_sidecar(asset)

    def test_renamed_asset_is_refused(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import AIProvenanceError, require_sidecar

        original = _marked(tmp_path, "art.png")
        renamed = original.rename(tmp_path / "renamed.png")
        _sidecar(renamed)
        with pytest.raises(AIProvenanceError, match="renamed"):
            require_sidecar(renamed)

    def test_a_non_ai_file_is_refused(self, tmp_path: Path) -> None:
        from holiday_card.core.ai_provenance import AIProvenanceError, require_sidecar

        with pytest.raises(AIProvenanceError, match="not an AI asset"):
            require_sidecar(_png(tmp_path / "a.png"))


def test_disclosure_label_is_the_model() -> None:
    from holiday_card.core.ai_provenance import ai_disclosure_label

    record = LicenseRecord(prompt="p", model="gpt-image-2", timestamp="t")
    assert ai_disclosure_label(record) == "gpt-image-2"
