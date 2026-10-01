"""``scripts/refresh_openrouter_models.py``: the dev-only allowlist refresher (#148).

Every test replays the recorded catalogue under
``tests/fixtures/openrouter/`` with ``--from-dir``; nothing here touches the
network.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from holiday_card.core import ai_openrouter_models
from holiday_card.core.ai_openrouter_models import OPENROUTER_IMAGE_MODELS

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "refresh_openrouter_models.py"
_FIXTURES = _ROOT / "tests" / "fixtures" / "openrouter"
CATALOGUE = _FIXTURES / "catalogue"
DRIFTED = _FIXTURES / "catalogue-drifted"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("refresh_openrouter_models", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through it
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script()


def _json(path: Path) -> Any:
    return json.loads(path.read_text())


def _endpoint(model_id: str, tag: str, root: Path = CATALOGUE) -> dict[str, Any]:
    record = _json(root / "endpoints" / (model_id.replace("/", "__") + ".json"))
    return next(e for e in record["endpoints"] if e["provider_tag"] == tag)


def _model(model_id: str) -> dict[str, Any]:
    return next(m for m in _json(CATALOGUE / "images_models.json")["data"] if m["id"] == model_id)


def _table_rows(out: str) -> list[list[str]]:
    rows = [line for line in out.splitlines() if line.startswith("| ") and "---" not in line]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[1:]]


class TestEntryFromCatalogue:
    @pytest.mark.parametrize("model_id", sorted(OPENROUTER_IMAGE_MODELS))
    def test_reproduces_the_committed_entry(self, script: ModuleType, model_id: str) -> None:
        current = OPENROUTER_IMAGE_MODELS[model_id]
        live = script.entry_from_catalogue(
            _model(model_id),
            _endpoint(model_id, current.provider_tag),
            _json(CATALOGUE / "providers.json")["data"],
            snapshot_date="2026-10-14",
        )
        assert live.snapshot_date == "2026-10-14"
        # The terms review replaced each catalogue URL with the page that
        # governs output ownership (see the snapshot doc).
        # The terms URL and the --max-cost bounds (#151) are human-maintained.
        assert set(script.REVIEWED_FIELDS) == {
            "upstream_terms_url", "max_output_megapixels", "output_image_tokens",
            "input_image_tokens", "output_text_tokens", "output_text_usd_per_token",
            "bound_source", "observed_long_edge_px", "observed_source",
        }  # fmt: skip
        assert live.bound_source is None
        reviewed = {f: getattr(current, f) for f in script.REVIEWED_FIELDS}
        assert replace(live, snapshot_date=current.snapshot_date, **reviewed) == current

    def test_terms_url_comes_from_the_tags_base_slug(self, script: ModuleType) -> None:
        live = script.entry_from_catalogue(
            _model("google/gemini-3-pro-image"),
            _endpoint("google/gemini-3-pro-image", "google-ai-studio/global"),
            _json(CATALOGUE / "providers.json")["data"],
            snapshot_date="2026-10-14",
        )
        assert live.upstream_terms_url == "https://cloud.google.com/terms/"


class TestDiffEntry:
    def test_no_difference(self, script: ModuleType) -> None:
        entry = OPENROUTER_IMAGE_MODELS["openai/gpt-image-2"]
        assert script.diff_entry(entry, replace(entry, snapshot_date="2027-01-01")) == []

    def test_terms_url_is_a_reviewed_value_not_drift(self, script: ModuleType) -> None:
        entry = OPENROUTER_IMAGE_MODELS["openai/gpt-image-2"]
        live = replace(entry, upstream_terms_url="https://openai.com/policies/row-terms-of-use/")
        assert script.diff_entry(entry, live) == []

    def test_cost_bounds_are_reviewed_values_not_drift(self, script: ModuleType) -> None:
        entry = OPENROUTER_IMAGE_MODELS["google/gemini-3-pro-image"]
        live = replace(
            entry, output_image_tokens=None, input_image_tokens=None,
            output_text_tokens=None, output_text_usd_per_token=None, bound_source=None,
        )  # fmt: skip
        assert script.diff_entry(entry, live) == []

    def test_a_dropped_tier_drops_its_token_bound(self, script: ModuleType) -> None:
        entry = OPENROUTER_IMAGE_MODELS["google/gemini-3-pro-image"]
        kept = script.carry_reviewed(entry, ("1K", "2K"))
        assert dict(kept["output_image_tokens"]) == {"1K": 1120, "2K": 1120}
        assert kept["bound_source"] == entry.bound_source

    def test_no_bound_left_drops_the_source(self, script: ModuleType) -> None:
        entry = replace(
            OPENROUTER_IMAGE_MODELS["google/gemini-3.1-flash-image"],
            output_text_tokens=None,
            output_text_usd_per_token=None,
        )
        kept = script.carry_reviewed(entry, ("8K",))
        assert kept["output_image_tokens"] is None
        assert kept["bound_source"] is None

    def test_an_output_text_allowance_keeps_the_source(self, script: ModuleType) -> None:
        entry = OPENROUTER_IMAGE_MODELS["google/gemini-3.1-flash-image"]
        kept = script.carry_reviewed(entry, ("8K",))
        assert kept["output_image_tokens"] is None
        assert kept["output_text_tokens"] == entry.output_text_tokens
        assert kept["output_text_usd_per_token"] == entry.output_text_usd_per_token

    def test_observed_long_edges_are_reviewed_values_not_drift(self, script: ModuleType) -> None:
        entry = OPENROUTER_IMAGE_MODELS["google/gemini-3-pro-image"]
        live = replace(entry, observed_long_edge_px=None, observed_source=None)
        assert script.diff_entry(entry, live) == []

    def test_a_dropped_tier_drops_its_observed_long_edge(self, script: ModuleType) -> None:
        entry = OPENROUTER_IMAGE_MODELS["google/gemini-3-pro-image"]
        kept = script.carry_reviewed(entry, ("1K", "2K"))
        assert dict(kept["observed_long_edge_px"]) == {"2K": 2400}
        assert kept["observed_source"] == entry.observed_source
        gone = script.carry_reviewed(entry, ("1K",))
        assert gone["observed_long_edge_px"] is None
        assert gone["observed_source"] is None

    def test_gone(self, script: ModuleType) -> None:
        entry = OPENROUTER_IMAGE_MODELS["openai/gpt-image-2"]
        (diff,) = script.diff_entry(entry, None)
        assert (diff.field, diff.in_code) == ("endpoint", "pinned")
        assert diff.live.startswith("GONE")


class TestMain:
    def test_recorded_catalogue_has_no_drift(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert script.main(["--from-dir", str(CATALOGUE)]) == 0
        out = capsys.readouterr().out
        assert "0 differences in 5 curated models" in out
        assert "1 catalogue models are not curated" in out
        assert _table_rows(out) == []

    def test_drifted_catalogue_reports_three_rows(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert script.main(["--from-dir", str(DRIFTED)]) == 1
        out = capsys.readouterr().out
        assert "# OpenRouter image allowlist drift: fetched " in out
        assert "(entries snapshot 2026-09-30)" in out
        assert "3 differences in 5 curated models" in out
        assert sorted(_table_rows(out)) == sorted(
            [
                [
                    "google/gemini-3-pro-image",
                    "google-ai-studio/global",
                    "resolutions",
                    "1K 2K 4K",
                    "1K 2K",
                ],
                [
                    "bytedance-seed/seedream-4.5",
                    "seed",
                    "pricing",
                    "output_image/image/0.04; input_image/image/0",
                    "output_image/image/0.035; input_image/image/0",
                ],
                [
                    "black-forest-labs/flux.2-pro",
                    "black-forest-labs",
                    "endpoint",
                    "pinned",
                    "GONE: no endpoint with this provider_tag",
                ],
            ]
        )

    def test_emit_python_for_an_unreviewed_model_cannot_be_pasted(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = script.main(
            ["--from-dir", str(CATALOGUE), "--emit", "python", "--add", "recraft/recraft-v4.1@recraft"]
        )
        assert code == 1  # a new model is a change to review
        out = capsys.readouterr().out
        block = next(b for b in out.split("\n\n") if 'id="recraft/recraft-v4.1"' in b)
        assert 'upstream_terms_url="TODO-REVIEW"' in block
        with pytest.raises(ValueError, match="upstream_terms_url"):
            eval(block.strip().rstrip(","), vars(ai_openrouter_models))

    def test_emit_python_round_trips_the_curated_entries(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert script.main(["--from-dir", str(CATALOGUE), "--emit", "python"]) == 0
        out = capsys.readouterr().out
        blocks = [b for b in out.split("\n\n") if b.strip().startswith("OpenRouterModel(")]
        entries = [eval(b.strip().rstrip(","), vars(ai_openrouter_models)) for b in blocks]
        assert {e.id: replace(e, snapshot_date="2026-09-30") for e in entries} == dict(
            OPENROUTER_IMAGE_MODELS
        )

    def test_emit_python_comments_a_gone_entry(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert script.main(["--from-dir", str(DRIFTED), "--emit", "python"]) == 1
        out = capsys.readouterr().out
        assert "# black-forest-labs/flux.2-pro: GONE" in out
        assert 'id="black-forest-labs/flux.2-pro"' not in out

    def test_add_with_several_endpoints_needs_a_tag(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert script.main(["--from-dir", str(CATALOGUE), "--add", "google/gemini-3-pro-image"]) == 2
        err = capsys.readouterr().err
        assert "google-ai-studio/global" in err
        assert "google-vertex/global" in err

    def test_add_with_an_unknown_tag(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        argv = ["--from-dir", str(CATALOGUE), "--add", "recraft/recraft-v4.1@nope"]
        assert script.main(argv) == 2
        assert "nope" in capsys.readouterr().err

    def test_add_an_unknown_model(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert script.main(["--from-dir", str(CATALOGUE), "--add", "nope/nope"]) == 2
        assert "nope/nope" in capsys.readouterr().err

    def test_add_in_table_mode_is_a_new_row(
        self, script: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        argv = ["--from-dir", str(CATALOGUE), "--add", "recraft/recraft-v4.1"]
        assert script.main(argv) == 1
        (row,) = _table_rows(capsys.readouterr().out)
        assert row[:3] == ["recraft/recraft-v4.1", "recraft", "entry"]
        assert row[4] == "new: not curated"

    def test_missing_from_dir_is_a_usage_error(
        self, script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert script.main(["--from-dir", str(tmp_path / "absent")]) == 2
        assert "absent" in capsys.readouterr().err

    def test_save_dir_writes_the_from_dir_layout(
        self, script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved = tmp_path / "saved"
        assert script.main(["--from-dir", str(CATALOGUE), "--save-dir", str(saved)]) == 0
        capsys.readouterr()
        assert script.main(["--from-dir", str(saved)]) == 0
        assert (saved / "providers.json").is_file()
        assert (saved / "endpoints" / "openai__gpt-image-2.json").is_file()

    def test_non_https_urls_are_refused(self, script: ModuleType) -> None:
        with pytest.raises(ValueError, match="https"):
            script.fetch_json("http://openrouter.ai/api/v1/providers")


def test_the_script_never_sends_a_key() -> None:
    source = _SCRIPT.read_text()
    assert "Authorization" not in source
    assert "API_KEY" not in source
