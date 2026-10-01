"""Provenance + first-use-consent tests for AI imagery (Leapfrog 3).

Every baked AI asset gets a sibling ``<asset>.license.yaml`` sidecar
(consensus-ai-feature.md, "Sidecar provenance YAML"), and the first use
of the feature is gated behind a logged consent acknowledgement. These
tests pin both.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from holiday_card.core.ai_provenance import (
    LicenseRecord,
    consent_notice,
    has_consented,
    read_sidecar,
    record_consent,
    sidecar_path_for,
    write_sidecar,
)
from holiday_card.core.ai_providers import PROVIDERS, AIProvider

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ai"
OPENAI_POLICY = "https://openai.com/policies/usage-policies"


def _record(**fields: object) -> LicenseRecord:
    base: dict[str, object] = {
        "prompt": "watercolor pine bough border",
        "style": "watercolor",
        "reference": "fonts/curated/sample.png",
        "provider": AIProvider.OPENAI,
        "requested_model": "gpt-image-2",
        "model": "gpt-image-2",
        "request_shape": {"size": "1328x1824"},
        "seed": 42,
        "timestamp": "2027-01-15T10:00:00Z",
        "cost_usd": 0.04,
        "media_type": "image/png",
        "width_px": 1280,
        "height_px": 1792,
        "policy_urls": [OPENAI_POLICY],
    }
    return LicenseRecord.model_validate({**base, **fields})


class TestSidecarPath:
    def test_sidecar_is_sibling_with_license_yaml_suffix(self) -> None:
        assert sidecar_path_for(Path("assets/ai/border.png")) == Path(
            "assets/ai/border.license.yaml"
        )


class TestLicenseRecord:
    def test_defaults_include_srgb_profile_and_unreviewed(self) -> None:
        record = _record()
        assert record.color_profile == "sRGB IEC61966-2.1"
        # Commercial-use determination is an explicit placeholder for the user.
        assert record.commercial_use_determination == "UNREVIEWED"

    def test_cost_source_defaults_to_unknown(self) -> None:
        assert _record().cost_source == "unknown"

    def test_legacy_policy_field_is_gone(self) -> None:
        assert "openai_policy_url" not in LicenseRecord.model_fields

    @pytest.mark.parametrize("name", ["provider", "requested_model", "policy_urls"])
    def test_provider_fields_are_required(self, name: str) -> None:
        data = _record().model_dump(mode="json")
        del data[name]
        with pytest.raises(ValidationError, match=name):
            LicenseRecord.model_validate(data)

    def test_unknown_key_is_refused(self) -> None:
        data = {**_record().model_dump(mode="json"), "colr_profile": "x"}
        with pytest.raises(ValidationError, match="colr_profile"):
            LicenseRecord.model_validate(data)

    def test_no_field_can_hold_a_secret(self) -> None:
        secretish = re.compile(r"(?i)key|secret|token|authorization")
        assert [n for n in LicenseRecord.model_fields if secretish.search(n)] == []


class TestSidecarRoundTrip:
    @pytest.mark.parametrize(
        "shape",
        [{"size": "1328x1824"}, {"aspect_ratio": "3:4", "resolution": "2K"}, {"aspect_ratio": "3:4"}],
    )
    def test_write_then_read_round_trips(self, tmp_path: Path, shape: dict[str, str]) -> None:
        asset = tmp_path / "border.png"
        asset.write_bytes(b"\x89PNG fake")
        record = _record(request_shape=shape)

        sidecar = write_sidecar(asset, record)

        assert sidecar == tmp_path / "border.license.yaml"
        assert sidecar.exists()
        loaded = read_sidecar(asset)
        assert loaded == record
        assert yaml.safe_load(sidecar.read_text())["provider"] == "openai"

    def test_read_missing_sidecar_raises(self, tmp_path: Path) -> None:
        asset = tmp_path / "no-sidecar.png"
        asset.write_bytes(b"x")
        with pytest.raises(FileNotFoundError):
            read_sidecar(asset)


class TestLegacySidecar:
    """O7: a v1.3.0 sidecar (``openai_policy_url``) is read for one release, never written."""

    def _legacy(self, tmp_path: Path) -> Path:
        asset = tmp_path / "border.png"
        asset.write_bytes(b"x")
        shutil.copy(FIXTURES / "v1.3.0-border.license.yaml", sidecar_path_for(asset))
        return asset

    def test_v1_3_0_sidecar_loads_as_openai(self, tmp_path: Path) -> None:
        record = read_sidecar(self._legacy(tmp_path))
        assert record.provider is AIProvider.OPENAI
        assert record.requested_model == record.model == "gpt-image-2"
        assert record.policy_urls == [OPENAI_POLICY]
        assert record.request_shape is None
        assert record.generation_id is None
        assert record.provider_route is None
        assert record.media_type is None
        # 0.04 may be v1.3.0's invented figure (#141).
        assert record.cost_usd == 0.04
        assert record.cost_source == "unknown"

    def test_rewriting_migrates_to_the_provider_neutral_shape(self, tmp_path: Path) -> None:
        asset = self._legacy(tmp_path)
        sidecar = write_sidecar(asset, read_sidecar(asset))
        data = yaml.safe_load(sidecar.read_text())
        assert "openai_policy_url" not in data
        assert data["provider"] == "openai"
        assert data["policy_urls"] == [OPENAI_POLICY]

    def test_mixing_legacy_and_new_keys_is_refused(self) -> None:
        data = yaml.safe_load((FIXTURES / "v1.3.0-border.license.yaml").read_text())
        with pytest.raises(ValidationError, match="legacy"):
            LicenseRecord.model_validate({**data, "provider": "openai"})
        with pytest.raises(ValidationError, match="legacy"):
            LicenseRecord.model_validate({**data, "policy_urls": [OPENAI_POLICY]})

    def test_validation_does_not_mutate_the_input(self) -> None:
        data = yaml.safe_load((FIXTURES / "v1.3.0-border.license.yaml").read_text())
        before = dict(data)
        LicenseRecord.model_validate(data)
        assert data == before


_ISO_UTC = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00"


class TestConsentFile:
    def test_fresh_path_has_not_consented(self, tmp_path: Path) -> None:
        assert has_consented(tmp_path / "ai-consent.json", AIProvider.OPENAI) is False

    def test_record_consent_writes_the_provider_neutral_shape(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "ai-consent.json"
        record_consent(consent_file, AIProvider.OPENAI)
        assert has_consented(consent_file, AIProvider.OPENAI) is True
        data = json.loads(consent_file.read_text())
        assert list(data) == ["providers"]
        entry = data["providers"]["openai"]
        assert list(entry) == ["acknowledged", "timestamp", "policy_urls"]
        assert entry["acknowledged"] is True
        assert re.fullmatch(_ISO_UTC, entry["timestamp"])
        assert entry["policy_urls"] == [OPENAI_POLICY]
        assert consent_file.read_text() == json.dumps(data, indent=2)

    def test_v1_3_0_consent_counts_for_openai(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "ai-consent.json"
        shutil.copy(FIXTURES / "v1.3.0-ai-consent.json", consent_file)
        before = consent_file.read_bytes()
        assert has_consented(consent_file, AIProvider.OPENAI) is True
        assert consent_file.read_bytes() == before  # reading never rewrites

    def test_another_providers_consent_is_not_openais(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "ai-consent.json"
        consent_file.write_text('{"providers": {"openrouter": {"acknowledged": true}}}')
        assert has_consented(consent_file, AIProvider.OPENAI) is False

    def test_recording_preserves_unknown_providers(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "ai-consent.json"
        other = {"acknowledged": True, "timestamp": "2027-01-01T00:00:00+00:00",
                 "policy_urls": ["https://openrouter.ai/terms"], "future": {"x": [1, 2]}}
        consent_file.write_text(json.dumps({"providers": {"openrouter": other}}))
        record_consent(consent_file, AIProvider.OPENAI)
        data = json.loads(consent_file.read_text())
        assert data["providers"]["openrouter"] == other
        assert has_consented(consent_file, AIProvider.OPENAI) is True

    def test_recording_migrates_the_legacy_file(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "ai-consent.json"
        shutil.copy(FIXTURES / "v1.3.0-ai-consent.json", consent_file)
        record_consent(consent_file, AIProvider.OPENAI)
        data = json.loads(consent_file.read_text())
        assert list(data) == ["providers"]
        assert data["providers"]["openai"] == {
            "acknowledged": True,
            "timestamp": "2026-06-02T10:00:00+00:00",
            "policy_urls": [OPENAI_POLICY],
        }

    @pytest.mark.parametrize(
        "text",
        [
            '{"providers": []}',
            "null",
            "[]",
            "{not json",
            '{"providers": {"openai": {"acknowledged": "yes"}}}',
            '{"providers": {"openai": true}}',
            '{"acknowledged": "yes"}',
            '{"acknowledged": true, "providers": {}}',
        ],
    )
    def test_malformed_files_are_not_consent(self, tmp_path: Path, text: str) -> None:
        consent_file = tmp_path / "ai-consent.json"
        consent_file.write_text(text)
        assert has_consented(consent_file, AIProvider.OPENAI) is False

    def test_record_consent_creates_parent_dirs(self, tmp_path: Path) -> None:
        consent_file = tmp_path / "nested" / "dir" / "ai-consent.json"
        record_consent(consent_file, AIProvider.OPENAI)
        assert has_consented(consent_file, AIProvider.OPENAI) is True
        assert [p.name for p in consent_file.parent.iterdir()] == ["ai-consent.json"]


# The v1.3.0 CONSENT_NOTICE, formatted with path=/x/ai-consent.json (byte-identical, #147).
V1_3_0_OPENAI_NOTICE = (
    "holiday-card AI imagery \u2014 first-use acknowledgement\n"
    "---------------------------------------------------\n"
    "AI image generation is intended for PERSONAL USE. We do not recommend AI\n"
    "imagery for cards you intend to sell.\n"
    "\n"
    "By proceeding you acknowledge:\n"
    "  * You have read the OpenAI usage policy: https://openai.com/policies/usage-policies\n"
    "  * AI-generated assets may inadvertently contain protected material;\n"
    "    you are responsible for what you print and sell.\n"
    "  * US copyright law currently denies protection to purely AI-generated\n"
    "    output, and many print-on-demand services require AI disclosure.\n"
    "\n"
    "This acknowledgement is recorded once to /x/ai-consent.json.\n"
)


class TestConsentNotice:
    def test_openai_notice_is_byte_identical_to_v1_3_0(self) -> None:
        notice = consent_notice(AIProvider.OPENAI, path=Path("/x/ai-consent.json"))
        assert notice == V1_3_0_OPENAI_NOTICE

    @pytest.mark.parametrize("provider", list(AIProvider))
    def test_every_notice_names_its_policies_and_the_path(self, provider: AIProvider) -> None:
        path = Path("/somewhere/ai-consent.json")
        notice = consent_notice(provider, path=path)
        for url in PROVIDERS[provider].policy_urls:
            assert url in notice
        assert str(path) in notice


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
    return write_sidecar(asset, _record(**{"prompt": "p", "model": "gpt-image-2",
                                           "timestamp": "2026-10-02T09:14:03+00:00", **fields}))


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

    assert ai_disclosure_label(_record(model="gpt-image-2")) == "gpt-image-2"


def test_disclosure_label_names_the_router_for_openrouter() -> None:
    from holiday_card.core.ai_provenance import ai_disclosure_label

    record = _record(
        provider=AIProvider.OPENROUTER,
        requested_model="google/gemini-3-pro-image",
        model="google/gemini-3-pro-image",
        provider_route="google-ai-studio/global",
        request_shape={"aspect_ratio": "3:4", "resolution": "2K"},
    )
    assert ai_disclosure_label(record) == "google/gemini-3-pro-image via openrouter"


# --- #150: the OpenRouter consent notice ------------------------------------------

OPENROUTER_BLURB = """\
  * Your prompt and reference image are sent to OpenRouter AND to the
    upstream vendor of the model you chose (for example Google or Black
    Forest Labs). holiday-card pins that one vendor and never falls back.
  * You have read the OpenRouter Terms of Service:
    https://openrouter.ai/terms
    Ownership of the output, and what you may do with it, is set by the
    upstream vendor's model terms; OpenRouter grants no licence of its own.
    That vendor's terms URL is recorded in each asset's .license.yaml sidecar.
  * OpenRouter's data-retention and training settings are ACCOUNT-LEVEL
    settings of your OpenRouter account; this tool cannot opt out per
    request. Review them before you send a private image:
    https://openrouter.ai/workspaces/default/settings
  * Reference images are NOT screened for trademarks or real people's
    likenesses; only the text prompt is checked. You are responsible for
    what you upload: do not send a reference you do not have the rights to.
"""


class TestOpenRouterConsentNotice:
    def test_blurb_is_pinned(self) -> None:
        assert PROVIDERS[AIProvider.OPENROUTER].consent_blurb == OPENROUTER_BLURB

    @pytest.mark.parametrize(
        "statement",
        [
            "sent to OpenRouter AND to the\n    upstream vendor",
            "never falls back",
            "https://openrouter.ai/terms",
            "OpenRouter grants no licence of its own",
            "ACCOUNT-LEVEL\n    settings of your OpenRouter account",
            "cannot opt out per\n    request",
            "https://openrouter.ai/workspaces/default/settings",
            "Reference images are NOT screened for trademarks or real people's\n    likenesses",
            "You are responsible for\n    what you upload",
            # The common lines stay as they are.
            "you are responsible for what you print and sell",
            "intended for PERSONAL USE",
        ],
    )
    def test_notice_states(self, statement: str) -> None:
        notice = consent_notice(AIProvider.OPENROUTER, path=Path("/x/ai-consent.json"))
        assert statement in notice

    def test_notice_names_the_pinned_vendor_at_run_time(self) -> None:
        notice = consent_notice(
            AIProvider.OPENROUTER,
            path=Path("/x/ai-consent.json"),
            model="google/gemini-3-pro-image",
        )
        assert (
            "  * For google/gemini-3-pro-image the upstream vendor is Google (AI Studio)"
            " (route google-ai-studio/global);\n"
            "    its terms govern the output: https://ai.google.dev/gemini-api/terms\n"
        ) in notice

    def test_openai_notice_ignores_the_model(self) -> None:
        path = Path("/x/ai-consent.json")
        assert consent_notice(AIProvider.OPENAI, path=path, model="gpt-image-2") == (
            consent_notice(AIProvider.OPENAI, path=path)
        )
