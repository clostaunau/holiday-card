"""CLI smoke and behavior tests for the holiday-card Typer app.

Exercises the public command surface declared in
``src/holiday_card/cli/commands.py`` via Typer's CliRunner. Before this
file existed, ``cli/commands.py`` (556 LOC) had 0% coverage.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from holiday_card import __version__
from holiday_card.cli.commands import app


@pytest.fixture
def runner() -> CliRunner:
    """Return a Typer CliRunner. (Modern Click captures stderr separately by default.)"""
    return CliRunner()


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_flag_prints_version_and_exits_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout
        assert "holiday-card" in result.stdout


# ---------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------

class TestTemplatesCommand:
    def test_templates_lists_at_least_one_per_shipped_occasion(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["templates"])
        assert result.exit_code == 0
        # Each shipped occasion directory contributes templates that should
        # show up in the default table view.
        assert "christmas" in result.stdout
        assert "valentine" in result.stdout

    def test_templates_json_format_is_valid_json_with_templates_key(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["templates", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "templates" in payload
        assert isinstance(payload["templates"], list)
        assert len(payload["templates"]) > 0
        # Each entry has the keys the CLI's table view depends on.
        first = payload["templates"][0]
        for key in ("id", "name", "occasion", "fold_type"):
            assert key in first, f"missing key {key!r} in {first!r}"

    def test_templates_filtered_by_occasion_returns_only_that_occasion(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(
            app, ["templates", "--occasion", "valentine", "--format", "json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert len(payload["templates"]) > 0
        assert all(t["occasion"] == "valentine" for t in payload["templates"])

    def test_templates_unknown_occasion_exits_zero_with_no_results(
        self, runner: CliRunner
    ) -> None:
        # Filter that matches nothing should not error; it should just say so.
        result = runner.invoke(app, ["templates", "--occasion", "nonexistent"])
        assert result.exit_code == 0
        assert "No templates found" in result.stdout


# ---------------------------------------------------------------------------
# themes
# ---------------------------------------------------------------------------

class TestThemesCommand:
    def test_themes_lists_at_least_one_theme(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["themes"])
        assert result.exit_code == 0
        assert "theme(s) found" in result.stdout

    def test_themes_filtered_by_occasion_only_returns_that_occasion(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(
            app, ["themes", "--occasion", "valentine", "--format", "json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert len(payload["themes"]) > 0
        assert all(t["occasion"] == "valentine" for t in payload["themes"])


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

class TestCreateCommand:
    def test_create_christmas_classic_writes_a_pdf(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "card.pdf"
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "-m", "Merry Christmas!", "-o", str(out)],
        )
        assert result.exit_code == 0, result.stderr
        assert out.exists()
        assert out.stat().st_size > 1000, "PDF unexpectedly small"
        # Real PDF starts with the %PDF magic number.
        assert out.read_bytes()[:4] == b"%PDF"

    def test_create_valentine_hearts_writes_a_pdf(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "valentine.pdf"
        result = runner.invoke(
            app,
            [
                "create",
                "valentine-hearts",
                "-m", "Be Mine!",
                "--inside-message", "You make my heart smile",
                "-o", str(out),
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert out.exists()
        assert out.read_bytes()[:4] == b"%PDF"

    def test_create_appends_pdf_extension_when_missing(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out_without_ext = tmp_path / "card"  # note: no .pdf
        result = runner.invoke(
            app, ["create", "christmas-classic", "-o", str(out_without_ext)]
        )
        assert result.exit_code == 0, result.stderr
        # The CLI auto-appends .pdf.
        assert (tmp_path / "card.pdf").exists()

    def test_create_unknown_template_exits_with_helpful_listing(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "out.pdf"
        result = runner.invoke(
            app, ["create", "this-template-does-not-exist", "-o", str(out)]
        )
        assert result.exit_code == 2
        # Error path lists available templates so the user can recover.
        assert "Available templates" in result.stderr
        assert not out.exists()

    def test_create_invalid_fold_type_exits_two_and_names_valid_options(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "out.pdf"
        result = runner.invoke(
            app,
            [
                "create", "christmas-classic",
                "--fold-type", "octa_fold",
                "-o", str(out),
            ],
        )
        assert result.exit_code == 2
        assert "Invalid fold type" in result.stderr
        assert "half_fold" in result.stderr
        assert not out.exists()

    def test_create_missing_image_file_exits_two(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "out.pdf"
        missing = tmp_path / "no-such-image.jpg"
        result = runner.invoke(
            app,
            [
                "create", "christmas-classic",
                "-i", str(missing),
                "-o", str(out),
            ],
        )
        assert result.exit_code == 2
        assert "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

class TestValidateCommand:
    def test_validate_known_template_id_exits_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["validate", "christmas-classic"])
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()
        # Reports the metadata the user cares about.
        assert "Occasion:" in result.stdout
        assert "Fold type:" in result.stdout

    def test_validate_unknown_template_exits_two(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["validate", "no-such-template"])
        assert result.exit_code == 2
        assert "not found" in result.stderr.lower()

    def test_validate_yaml_path_to_invalid_file_exits_two(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        bad = tmp_path / "broken.yaml"
        bad.write_text("this: is: not: a: template:\n  - oops")
        result = runner.invoke(app, ["validate", str(bad)])
        assert result.exit_code == 2
        # Either yaml-parse error or template-validation error — both acceptable.
        assert ("invalid" in result.stderr.lower()
                or "error" in result.stderr.lower())
