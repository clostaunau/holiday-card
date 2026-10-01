"""AI assets through the CLI: provenance enforced, never a photo (#144).

A template may place a baked AI asset as an ordinary image element, but it
renders only while its sidecar is intact; ``-i`` refuses any AI asset
(rail 8). Every refusal is ``Error: …``, exit 2, no file, no traceback.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner, Result

from ai_fixtures import bake_fake_ai_asset
from holiday_card.cli.commands import app
from holiday_card.core.ai_provenance import LicenseRecord, sidecar_path_for, write_sidecar
from holiday_card.core.data_paths import data_path

runner = CliRunner()


def _plain(output: str) -> str:
    # Rich forces colour under GITHUB_ACTIONS; compare the text without ANSI styles.
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _invoke(*args: str) -> Result:
    return runner.invoke(app, list(args))


def _assert_refused(result: Result, *needles: str) -> None:
    out = _plain(result.output)
    assert result.exit_code == 2, out
    assert "Error:" in out
    assert "Traceback" not in out
    for needle in needles:
        assert needle in out, out


@pytest.fixture
def ai_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """christmas-classic plus a baked AI asset on the front panel, in ``tmp_path``."""
    monkeypatch.chdir(tmp_path)
    bake_fake_ai_asset(tmp_path, "border.png", size=(300, 450))  # 300 PPI in its slot
    doc = yaml.safe_load((data_path("templates") / "christmas" / "classic.yaml").read_text())
    doc["id"] = "ai-border"
    front = next(p for p in doc["panels"] if p["position"] == "front")
    front["image_elements"] = [{
        "id": "border", "source_path": "border.png",
        "x": 0.25, "y": 0.25, "width": 1.0, "height": 1.5,
    }]
    path = tmp_path / "ai-border.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def test_template_with_an_intact_ai_asset_renders(ai_template: Path) -> None:
    result = _invoke("create", str(ai_template), "-o", "card.pdf")
    assert result.exit_code == 0, _plain(result.output)
    assert Path("card.pdf").exists()


def test_template_whose_asset_lost_its_sidecar_is_refused(ai_template: Path) -> None:
    sidecar_path_for(ai_template.parent / "border.png").unlink()
    result = _invoke("create", str(ai_template), "-o", "card.pdf")
    _assert_refused(
        result, "ai-border/front/image_elements[0]", "border.license.yaml", "ai-asset generate",
    )
    assert not Path("card.pdf").exists()


def test_validate_reports_the_missing_sidecar_as_a_compile_problem(ai_template: Path) -> None:
    sidecar_path_for(ai_template.parent / "border.png").unlink()
    result = _invoke("validate", str(ai_template))
    out = _plain(result.output)
    assert result.exit_code == 2, out
    assert "<compile>" in out
    assert "border.license.yaml" in out


@pytest.fixture
def baked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return bake_fake_ai_asset(tmp_path, "me.png", size=(64, 96))


@pytest.fixture
def legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A v1.3.0-style asset: no marker, only a sibling sidecar."""
    from PIL import Image

    monkeypatch.chdir(tmp_path)
    path = tmp_path / "old.png"
    Image.new("RGB", (64, 96), "green").save(path)
    write_sidecar(path, LicenseRecord(
        prompt="p", provider="openai", requested_model="gpt-image-1", model="gpt-image-1",
        timestamp="t", policy_urls=["https://openai.com/policies/usage-policies"],
    ))
    return path


@pytest.mark.parametrize("asset", ["baked", "legacy"])
def test_create_refuses_an_ai_asset_as_a_photo(
    asset: str, request: pytest.FixtureRequest,
) -> None:
    path: Path = request.getfixturevalue(asset)
    result = _invoke("create", "christmas-family-photo", "-i", str(path), "-o", "card.pdf")
    _assert_refused(result, "rail 8")
    assert "photo slots" not in _plain(result.output)  # not PhotoSlotError's advice
    assert not Path("card.pdf").exists()


@pytest.mark.parametrize("asset", ["baked", "legacy"])
def test_preview_refuses_an_ai_asset_as_a_photo(
    asset: str, request: pytest.FixtureRequest,
) -> None:
    path: Path = request.getfixturevalue(asset)
    result = _invoke(
        "preview", "christmas-family-photo", "-i", str(path), "--no-open", "-o", "p.png",
    )
    _assert_refused(result, "rail 8")
    assert not Path("p.png").exists()


@pytest.mark.parametrize("target", ["per-panel-pdf", "moo-a6"])
def test_per_panel_export_enforces_the_sidecar(ai_template: Path, target: str) -> None:
    ok = _invoke("create", str(ai_template), "--export-for", target, "-o", "ok/")
    assert ok.exit_code == 0, _plain(ok.output)
    assert (Path("ok") / "front.pdf").exists()

    sidecar_path_for(ai_template.parent / "border.png").unlink()
    result = _invoke("create", str(ai_template), "--export-for", target, "-o", "out/")
    _assert_refused(result, "ai-border/front/image_elements[0]", "border.license.yaml")
    assert not Path("out").exists()
