"""``preview`` and ``init`` end to end through ``CliRunner`` (#84).

``preview`` renders the default ``letter`` sheet (8.5 x 11", no bleed since
#59) to PNG, so its pixel size is ``8.5·dpi x 11·dpi``. ``--open`` goes
through ``_open_in_default_viewer``; ``subprocess.run`` / ``os.startfile``
are replaced so nothing launches. The ``init → create`` round trip is #79's
(``TestInitThenCreate`` in ``test_cli.py``); these cover the scaffold itself.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner

from holiday_card.cli import commands
from holiday_card.cli.commands import app
from holiday_card.core.models import FoldType, PanelPosition
from holiday_card.core.template_checks import check_template
from holiday_card.core.templates import load_template_from_file, user_templates_dir


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def launched(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Record viewer launches instead of performing them."""
    calls: list[Any] = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **_kw: calls.append(argv))
    monkeypatch.setattr(os, "startfile", calls.append, raising=False)
    return calls


class TestPreview:
    @pytest.mark.parametrize("dpi", [36, 72])
    def test_png_has_the_letter_sheet_size_for_the_dpi(
        self, runner: CliRunner, tmp_path: Path, dpi: int
    ) -> None:
        out = tmp_path / "p.png"
        result = runner.invoke(
            app,
            ["preview", "christmas-classic", "--no-open", "-o", str(out), "--dpi", str(dpi)],
        )
        assert result.exit_code == 0, result.output
        with Image.open(out) as img:
            assert img.format == "PNG"
            assert img.size == (round(8.5 * dpi), 11 * dpi)
        assert f"Resolution: {dpi} DPI" in result.stdout

    def test_missing_template_exits_2_and_writes_nothing(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "p.png"
        result = runner.invoke(
            app, ["preview", "no-such-template", "--no-open", "-o", str(out)]
        )
        assert result.exit_code == 2, result.output
        assert "no-such-template" in result.stderr
        assert not out.exists()

    def test_png_suffix_is_appended_when_missing(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["preview", "christmas-classic", "--no-open", "--dpi", "36", "-o", str(tmp_path / "p")],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "p.png").is_file()
        assert not (tmp_path / "p").exists()

    def test_voice_and_letter_flags_reach_the_preview(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "p.png"
        result = runner.invoke(
            app,
            [
                "preview", "christmas-classic", "--no-open", "--dpi", "36", "-o", str(out),
                "--voice", "warm", "--seed", "1",
                "--salutation", "Dear Sam,", "--signoff", "Love,", "--signature", "C",
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.is_file()
        assert "warm" in result.stdout

    def test_open_launches_the_viewer_with_the_png(
        self, runner: CliRunner, tmp_path: Path, launched: list[Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        out = tmp_path / "p.png"
        result = runner.invoke(
            app, ["preview", "christmas-classic", "--open", "--dpi", "36", "-o", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert launched == [["open", str(out)]]

    def test_no_open_launches_nothing(
        self, runner: CliRunner, tmp_path: Path, launched: list[Any]
    ) -> None:
        result = runner.invoke(
            app,
            ["preview", "christmas-classic", "--no-open", "--dpi", "36", "-o", str(tmp_path / "p.png")],
        )
        assert result.exit_code == 0, result.output
        assert launched == []


class TestOpenInDefaultViewer:
    @pytest.mark.parametrize(
        ("platform", "expected"),
        [
            ("darwin", ["open", "x.png"]),
            ("linux", ["xdg-open", "x.png"]),
            ("win32", "x.png"),
        ],
    )
    def test_uses_the_platform_viewer(
        self, launched: list[Any], monkeypatch: pytest.MonkeyPatch,
        platform: str, expected: Any,
    ) -> None:
        monkeypatch.setattr(sys, "platform", platform)
        commands._open_in_default_viewer(Path("x.png"))
        assert launched == [expected]

    def test_unknown_platform_launches_nothing(
        self, launched: list[Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "platform", "plan9")
        commands._open_in_default_viewer(Path("x.png"))
        assert launched == []

    def test_a_viewer_failure_is_reported_not_raised(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def boom(*_a: object, **_kw: object) -> None:
            raise FileNotFoundError("xdg-open")

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(subprocess, "run", boom)
        commands._open_in_default_viewer(Path("x.png"))
        assert "could not auto-open" in capsys.readouterr().err


class TestInit:
    def test_scaffold_round_trips_through_the_loader_and_checks_clean(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app, ["init", "my-card", "--occasion", "birthday", "--output", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        path = tmp_path / "my-card.yaml"
        template = load_template_from_file(path)
        assert template.id == "my-card"
        assert template.name == "My Card"
        assert template.occasion == "birthday"
        assert template.fold_type == FoldType.QUARTER_FOLD
        assert [p.position for p in template.panels] == [
            PanelPosition.FRONT, PanelPosition.BACK,
            PanelPosition.INSIDE_LEFT, PanelPosition.INSIDE_RIGHT,
        ]
        assert check_template(template) == []
        # Every key the scaffold writes survives the loader (extra="forbid").
        raw = yaml.safe_load(path.read_text())
        assert raw["panels"][0]["text_elements"][0]["content"] == "Your Greeting Here"
        assert template.panels[0].text_elements[0].content == "Your Greeting Here"

    @pytest.mark.parametrize("fold_type", ["quarter_fold", "half_fold", "tri_fold"])
    def test_fold_type_is_honoured(
        self, runner: CliRunner, tmp_path: Path, fold_type: str
    ) -> None:
        result = runner.invoke(
            app, ["init", "f", "--fold-type", fold_type, "--output", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        assert yaml.safe_load((tmp_path / "f.yaml").read_text())["fold_type"] == fold_type
        assert load_template_from_file(tmp_path / "f.yaml").fold_type == FoldType(fold_type)

    def test_output_dir_is_used_and_the_user_dir_is_untouched(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "nested" / "dir"
        result = runner.invoke(app, ["init", "o", "--output", str(out_dir)])
        assert result.exit_code == 0, result.output
        assert (out_dir / "o.yaml").is_file()
        assert f"Template created: {out_dir / 'o.yaml'}" in result.stdout
        assert not (user_templates_dir() / "generic" / "o.yaml").exists()
