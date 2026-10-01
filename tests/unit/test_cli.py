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
        assert "birthday" in result.stdout

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
            app, ["templates", "--occasion", "christmas", "--format", "json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert len(payload["templates"]) > 0
        assert all(t["occasion"] == "christmas" for t in payload["templates"])

    def test_templates_unknown_occasion_exits_zero_with_no_results(
        self, runner: CliRunner
    ) -> None:
        # Filter that matches nothing should not error; it should just say so.
        result = runner.invoke(app, ["templates", "--occasion", "nonexistent"])
        assert result.exit_code == 0
        assert "No templates found" in result.stdout

    def test_templates_empty_catalog_exits_one_with_error_on_stderr(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An empty bundled catalog means a broken install (D4: fail loud),
        # even when the user layer has templates (#79).
        import holiday_card.core.templates as templates_module

        monkeypatch.setattr(templates_module, "data_path", lambda _kind: tmp_path)
        user = tmp_path / "xdg" / "holiday-card" / "templates"
        user.mkdir(parents=True)
        (user / "mine.yaml").write_text(_CLASSIC_YAML.read_text())
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        result = runner.invoke(app, ["templates"])
        assert result.exit_code == 1
        assert (
            f"Error: no templates found in {tmp_path} — "
            "installation is missing bundled data"
        ) in result.stderr
        assert result.stdout == ""


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
            app, ["themes", "--occasion", "christmas", "--format", "json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert len(payload["themes"]) > 0
        assert all(t["occasion"] == "christmas" for t in payload["themes"])

    def test_themes_empty_catalog_exits_one_with_error_on_stderr(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOLIDAY_CARD_THEMES", str(tmp_path))
        result = runner.invoke(app, ["themes"])
        assert result.exit_code == 1
        assert (
            f"Error: no themes found in {tmp_path} — "
            "installation is missing bundled data"
        ) in result.stderr
        assert result.stdout == ""


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

    def test_create_birthday_balloons_writes_a_pdf(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "birthday.pdf"
        result = runner.invoke(
            app,
            [
                "create",
                "birthday-balloons",
                "-m", "Happy Birthday!",
                "--inside-message", "Hope your day is amazing",
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
                "create", "christmas-family-photo",
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
        assert result.stdout.startswith(f"Template invalid: {bad}\n")
        assert "  - <file>: " in result.stdout

    @staticmethod
    def _bad_classic(tmp_path: Path, **greeting_changes: object) -> Path:
        import yaml

        from holiday_card.core.data_paths import data_path

        data = yaml.safe_load(
            (data_path("templates") / "christmas" / "classic.yaml").read_text()
        )
        front = next(p for p in data["panels"] if p["position"] == "front")
        front["text_elements"][0].update(greeting_changes)
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump(data))
        return path

    def test_issue_reproduction_lists_every_problem(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # The #57 reproduction: typo'd keys, an unknown font and x: 99.
        bad = self._bad_classic(
            tmp_path, colr="red", font_famly="Lato", font_family="NotAFont", x=99
        )
        result = runner.invoke(app, ["validate", str(bad)])

        assert result.exit_code == 2
        assert result.stdout.startswith(f"Template invalid: {bad}\n")
        lines = [ln for ln in result.stdout.splitlines() if ln.startswith("  - ")]
        assert lines == [
            "  - panels[0].text_elements[0].colr: Extra inputs are not permitted",
            "  - panels[0].text_elements[0].font_famly: Extra inputs are not permitted",
        ]
        assert "Traceback" not in result.output

    def test_font_and_bounds_problems_exit_two(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        bad = self._bad_classic(tmp_path, font_family="NotAFont", x=99)
        result = runner.invoke(app, ["validate", str(bad)])

        assert result.exit_code == 2
        lines = [ln for ln in result.stdout.splitlines() if ln.startswith("  - ")]
        assert len(lines) == 2
        assert lines[0].startswith(
            "  - panels[front].text_elements[greeting].font_family: unknown font 'NotAFont'"
        )
        assert lines[1].startswith(
            "  - panels[front].text_elements[greeting]: text anchor (99, 2.75) in is outside"
        )
        assert "Template valid" not in result.stdout

    def test_every_listed_template_validates(self, runner: CliRunner) -> None:
        listing = runner.invoke(app, ["templates", "--format", "json"])
        ids = [t["id"] for t in json.loads(listing.stdout)["templates"]]
        assert len(ids) == 21
        for template_id in ids:
            result = runner.invoke(app, ["validate", template_id])
            assert result.exit_code == 0, (template_id, result.output)


# ---------------------------------------------------------------------------
# schema (#57)
# ---------------------------------------------------------------------------

class TestSchemaCommand:
    def test_schema_prints_json_that_forbids_unknown_text_keys(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["schema"])
        assert result.exit_code == 0
        schema = json.loads(result.stdout)
        assert schema["title"] == "Template"
        assert schema["$defs"]["TextElement"]["additionalProperties"] is False

    def test_schema_output_writes_the_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "p.json"
        result = runner.invoke(app, ["schema", "-o", str(out)])
        assert result.exit_code == 0
        assert json.loads(out.read_text())["title"] == "Template"
        stdout_schema = runner.invoke(app, ["schema"]).stdout
        assert out.read_text() == stdout_schema


# ---------------------------------------------------------------------------
# Fail loud on ignored or contradictory inputs (#60)
# ---------------------------------------------------------------------------

_CLASSIC_YAML = (
    Path(__file__).resolve().parents[2]
    / "src/holiday_card/data/templates/christmas/classic.yaml"
)


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty cwd; every refusal below must leave it empty."""
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def _written(work: Path) -> list[str]:
    return sorted(str(p.relative_to(work)) for p in work.rglob("*"))


def _custom_templates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, old: str, new: str
) -> None:
    """Point the catalog at a copy of christmas-classic with one edit."""
    text = _CLASSIC_YAML.read_text()
    assert old in text
    occasion_dir = tmp_path / "templates" / "christmas"
    occasion_dir.mkdir(parents=True)
    (occasion_dir / "classic.yaml").write_text(text.replace(old, new, 1))
    monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(tmp_path / "templates"))


def _refused(result: object, workdir: Path, *needles: str) -> None:
    out = result.output  # type: ignore[attr-defined]
    assert result.exit_code == 2, out  # type: ignore[attr-defined]
    for needle in needles:
        assert needle in out, out
    assert _written(workdir) == []


_TWINKLE_OVER_GRADIENT = """    shape_elements:
      - type: rectangle
        x: 0
        y: 0
        width: 4.25
        height: 5.5
        fill:
          type: linear_gradient
          angle: 90
          stops:
            - {position: 0, color: "#000033"}
            - {position: 1, color: "#333366"}
      - id: "twinkle"
        type: star
        center_x: 2.0
        center_y: 1.0
        outer_radius: 0.3
        inner_radius: 0.15
        fill_color: "#FFFFFF"
        opacity: 0.6
        z_index: 1
    text_elements:
      - id: "greeting"
"""


class TestTranslucencyOnPdfxTargets:
    """PDF/X refuses translucency over a non-solid backdrop (#71, D10)."""

    def test_moo_a6_refuses_a_translucent_star_over_a_gradient(
        self, runner: CliRunner, workdir: Path, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _custom_templates(tmp_path, monkeypatch, '    text_elements:\n      - id: "greeting"\n',
                          _TWINKLE_OVER_GRADIENT)
        result = runner.invoke(
            app, ["create", "christmas-classic", "--export-for", "moo-a6", "-o", "out"]
        )
        _refused(result, workdir, "Error: ", "christmas-classic/front/", "twinkle", "gradient")
        assert "Traceback" not in result.output

    @pytest.mark.usefixtures("workdir")
    def test_letter_keeps_the_same_template_translucent(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _custom_templates(tmp_path, monkeypatch, '    text_elements:\n      - id: "greeting"\n',
                          _TWINKLE_OVER_GRADIENT)
        result = runner.invoke(app, ["create", "christmas-classic", "-o", "card.pdf"])
        assert result.exit_code == 0, result.output


class TestCreateFailsLoud:
    def test_unknown_theme(self, runner: CliRunner, workdir: Path) -> None:
        from holiday_card.core.themes import discover_themes

        ids = sorted(t["id"] for t in discover_themes())
        result = runner.invoke(app, ["create", "christmas-classic", "--theme", "nope"])
        _refused(result, workdir, "Error: Unknown theme 'nope'. Available: " + ", ".join(ids))

    def test_voice_not_shipped_for_sympathy(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        from holiday_card.core.sentiments import get_sentiments_dir

        result = runner.invoke(
            app, ["create", "sympathy-spare", "--voice", "witty", "-o", "card.pdf"]
        )
        _refused(
            result, workdir,
            "Error: voice 'witty' is not available for occasion 'sympathy'. "
            "Available: warm, spare, devotional",
        )
        assert str(get_sentiments_dir()) not in result.output
        assert "Warning" not in result.output

    def test_voice_missing_one_role_file(
        self,
        runner: CliRunner,
        workdir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        lib = tmp_path / "sentiments"
        (lib / "christmas" / "warm").mkdir(parents=True)
        (lib / "christmas" / "warm" / "cover.yaml").write_text(
            "voice: warm\noccasion: christmas\nrole: cover\nsentiments: [Hi]\n"
        )
        monkeypatch.setenv("HOLIDAY_CARD_SENTIMENTS", str(lib))
        from holiday_card.core.sentiments import reset_cache

        reset_cache()
        result = runner.invoke(
            app, ["create", "christmas-classic", "--voice", "warm", "-o", "c.pdf"]
        )
        reset_cache()
        _refused(
            result, workdir,
            "Error: voice 'warm' is not available for occasion 'christmas'. "
            "Available: (none)",
        )
        assert str(lib) not in result.output

    def test_blank_inside_with_inside_message(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "--blank-inside", "--inside-message", "HI"]
        )
        _refused(result, workdir, "Error: --blank-inside cannot be combined with --inside-message")

    def test_blank_inside_with_inside_message_md(
        self, runner: CliRunner, workdir: Path, tmp_path: Path
    ) -> None:
        letter = tmp_path / "l.md"
        letter.write_text("Hello **there**.\n")
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--blank-inside", "--inside-message-md", str(letter)],
        )
        _refused(
            result, workdir, "Error: --blank-inside cannot be combined with --inside-message-md"
        )

    def test_seed_without_voice(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(app, ["create", "christmas-classic", "--seed", "7"])
        _refused(result, workdir, "Error: --seed only applies with --voice")

    def test_signature_font_without_signature(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "--signature-font", "Caveat"]
        )
        _refused(result, workdir, "Error: --signature-font requires --signature")

    def test_fold_type_incompatible_with_panels(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "--fold-type", "tri_fold"]
        )
        _refused(
            result, workdir,
            "Error: fold type 'tri_fold' needs panels left/center/right; "
            "template has front/back/inside_left/inside_right",
        )

    def test_unsupported_output_extension(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(app, ["create", "christmas-classic", "-o", "x.docx"])
        _refused(
            result, workdir, "Error: unsupported output extension '.docx' (use .pdf or .svg)"
        )

    def test_format_conflicts_with_extension(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "-o", "x.svg", "--format", "pdf"]
        )
        _refused(result, workdir, "Error: --format pdf conflicts with output extension '.svg'")

    def test_png_output_points_at_preview(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(app, ["create", "christmas-classic", "-o", "card.png"])
        _refused(
            result, workdir,
            "Error: unsupported output extension '.png'",
            "use 'holiday-card preview' for PNG",
        )

    def test_per_panel_target_refuses_file_output(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "--export-for", "moo-a6", "-o", "single.pdf"]
        )
        _refused(
            result, workdir,
            "Error: --export-for moo-a6 writes one file per panel; "
            "-o must be a directory, not 'single.pdf'",
        )

    def test_per_panel_target_refuses_existing_file(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        (workdir / "existing").write_text("keep me")
        result = runner.invoke(
            app, ["create", "christmas-classic", "--export-for", "moo-a6", "-o", "existing"]
        )
        assert result.exit_code == 2, result.output
        assert "-o must be a directory, not 'existing'" in result.output
        assert (workdir / "existing").read_text() == "keep me"

    @pytest.mark.parametrize("command", ["create", "preview"])
    def test_unknown_template_font(
        self,
        runner: CliRunner,
        workdir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        command: str,
    ) -> None:
        _custom_templates(
            tmp_path, monkeypatch, 'font_family: "PlayfairDisplay"', 'font_family: "NotAFont"'
        )
        args = [command, "christmas-classic"]
        args += ["--no-open", "-o", "p.png"] if command == "preview" else []
        result = runner.invoke(app, args)
        _refused(
            result, workdir,
            "Error: unknown font 'NotAFont' in christmas-classic/front/",
            "Available: Caveat, Comfortaa,",
        )

    def test_preview_default_output_writes_no_directory_on_error(
        self,
        runner: CliRunner,
        workdir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _custom_templates(
            tmp_path, monkeypatch, 'font_family: "PlayfairDisplay"', 'font_family: "NotAFont"'
        )
        result = runner.invoke(app, ["preview", "christmas-classic", "--no-open"])
        _refused(result, workdir, "unknown font 'NotAFont'")

    def test_unknown_template_font_per_panel_writes_no_directory(
        self,
        runner: CliRunner,
        workdir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _custom_templates(
            tmp_path, monkeypatch, 'font_family: "Cormorant"', 'font_family: "NotAFont"'
        )
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--export-for", "per-panel-pdf", "-o", "panels"],
        )
        _refused(result, workdir, "unknown font 'NotAFont' in christmas-classic/inside_right/")

    def test_unknown_signature_font(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--signature", "C",
             "--signature-font", "NotAFont", "-o", "card.pdf"],
        )
        _refused(result, workdir, "Error: unknown font 'NotAFont'", "Available: Caveat,")

    def test_missing_panel_background_image_file(
        self,
        runner: CliRunner,
        workdir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _custom_templates(
            tmp_path, monkeypatch,
            '    position: "front"\n',
            '    position: "front"\n    background_image: "x.png"\n',
        )
        result = runner.invoke(app, ["create", "christmas-classic", "-o", "card.pdf"])
        _refused(result, workdir, "image file not found")

    def test_template_font_file(
        self,
        runner: CliRunner,
        workdir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _custom_templates(
            tmp_path, monkeypatch,
            'font_family: "PlayfairDisplay"',
            'font_family: "PlayfairDisplay"\n        font_file: "mine.ttf"',
        )
        result = runner.invoke(app, ["create", "christmas-classic", "-o", "card.pdf"])
        _refused(result, workdir, "font_file is not supported")


class TestCreateStillWorks:
    """Behavior #60 must not change."""

    def test_suffixless_output_gets_extension(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(app, ["create", "christmas-classic", "-o", "out"])
        assert result.exit_code == 0, result.output
        assert (workdir / "out.pdf").is_file()

    def test_voice_with_blank_inside(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--voice", "warm", "--blank-inside",
             "--seed", "1", "-o", "c.svg"],
        )
        assert result.exit_code == 0, result.output
        assert "Inside: (blank)" in result.output
        assert (workdir / "c.svg").is_file()

    def test_letter_flags_with_blank_inside(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--blank-inside", "--signature", "C",
             "--signature-font", "Caveat", "-o", "c.pdf"],
        )
        assert result.exit_code == 0, result.output
        assert (workdir / "c.pdf").is_file()

    def test_per_panel_target_accepts_existing_directory_with_dot(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        (workdir / "moo.v2").mkdir()
        result = runner.invoke(
            app, ["create", "christmas-classic", "--export-for", "per-panel-pdf", "-o", "moo.v2"]
        )
        assert result.exit_code == 0, result.output
        assert (workdir / "moo.v2" / "front.pdf").is_file()


@pytest.mark.usefixtures("workdir")
class TestDebugFlag:
    @pytest.fixture
    def boom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from holiday_card.core.generators import CardGenerator

        def _raise(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(CardGenerator, "generate", _raise)

    @pytest.mark.usefixtures("boom")
    def test_debug_reraises_the_original_exception(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(
            app, ["--debug", "create", "christmas-classic", "-o", "c.pdf"]
        )
        assert isinstance(result.exception, RuntimeError)
        assert str(result.exception) == "boom"

    @pytest.mark.usefixtures("boom")
    def test_debug_env_var(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOLIDAY_CARD_DEBUG", "1")
        result = runner.invoke(app, ["create", "christmas-classic", "-o", "c.pdf"])
        assert isinstance(result.exception, RuntimeError)

    @pytest.mark.usefixtures("boom")
    def test_without_debug_hints_at_the_flag(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["create", "christmas-classic", "-o", "c.pdf"])
        assert result.exit_code == 1
        assert "boom" in result.output
        assert "(re-run with --debug for a traceback)" in result.output

    def test_debug_reraises_in_preview(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from holiday_card.renderers.png_backend import PNGRenderer

        def _raise(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(PNGRenderer, "render", _raise)
        result = runner.invoke(
            app, ["--debug", "preview", "christmas-classic", "--no-open", "-o", "p.png"]
        )
        assert isinstance(result.exception, RuntimeError)


# ---------------------------------------------------------------------------
# One pipeline behind create, preview and --debug-emit-ir (#78, D15)
# ---------------------------------------------------------------------------

_CONTENT_FLAGS = [
    "--voice", "spare", "--seed", "3", "--theme", "christmas-red-green",
    "--salutation", "Dear A,", "--ps", "P",
]
_OUTPUT_FIELDS = {"output", "output_format", "export_for", "fold_marks"}


@pytest.mark.usefixtures("workdir")
class TestPipelineParity:
    @pytest.fixture
    def captured(self, monkeypatch: pytest.MonkeyPatch) -> list[object]:
        """Record every CardRequest the CLI hands to the core builder."""
        import holiday_card.cli.commands as commands

        seen: list[object] = []

        def _wrap(real):  # type: ignore[no-untyped-def]
            def _spy(request, **kwargs):  # type: ignore[no-untyped-def]
                seen.append(request)
                return real(request, **kwargs)
            return _spy

        monkeypatch.setattr(commands, "build_card", _wrap(commands.build_card))
        monkeypatch.setattr(
            commands, "build_card_with_report", _wrap(commands.build_card_with_report)
        )
        return seen

    def test_create_preview_and_debug_ir_build_the_same_request(
        self, runner: CliRunner, captured: list[object]
    ) -> None:
        invocations = [
            ["create", "christmas-classic", "-o", "c.pdf", *_CONTENT_FLAGS],
            ["preview", "christmas-classic", "--no-open", "-o", "p.png", *_CONTENT_FLAGS],
            ["create", "christmas-classic", "--debug-emit-ir", *_CONTENT_FLAGS],
        ]
        for args in invocations:
            result = runner.invoke(app, args)
            assert result.exit_code == 0, (args, result.output)
        assert len(captured) == 3
        projections = [r.model_dump(exclude=_OUTPUT_FIELDS) for r in captured]  # type: ignore[attr-defined]
        assert projections[0] == projections[1] == projections[2]
        assert projections[0]["voice"] == "spare"
        assert projections[0]["salutation"] == "Dear A,"

    def test_debug_emit_ir_equals_compile_of_build_card(self, runner: CliRunner) -> None:
        from holiday_card.core.card_request import CardRequest, build_card
        from holiday_card.core.compiler import compile_card

        result = runner.invoke(
            app, ["create", "christmas-classic", "--debug-emit-ir", *_CONTENT_FLAGS]
        )
        assert result.exit_code == 0, result.output
        request = CardRequest(
            template="christmas-classic", voice="spare", seed=3,
            theme="christmas-red-green", salutation="Dear A,", postscript="P",
        )
        expected = [json.loads(c.model_dump_json()) for c in compile_card(build_card(request))]
        assert json.loads(result.stdout) == expected

    def test_debug_emit_ir_refuses_a_bad_fold_type(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "--debug-emit-ir", "--fold-type", "octa_fold"]
        )
        _refused(
            result, workdir,
            "Error: Invalid fold type 'octa_fold'. Valid options: half_fold, quarter_fold, tri_fold",
        )

    def test_debug_emit_ir_sees_the_letter_flags(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["create", "christmas-classic", "--debug-emit-ir", "--signature", "Chris"],
        )
        assert result.exit_code == 0, result.output
        texts = [c["run"]["text"] for c in json.loads(result.stdout) if c["cmd"] == "draw_text"]
        assert "Chris" in texts

    def test_preview_accepts_every_content_flag(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(
            app,
            [
                "preview", "christmas-classic", "--no-open", "-o", "p.png",
                "-m", "Hi", "--inside-message", "Body", "-t", "christmas-red-green",
                "-f", "half_fold", "--signoff", "Love,", "--signature", "C",
                "--signature-font", "Caveat",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (workdir / "p.png").is_file()

    def test_preview_refuses_contradictory_flags_like_create(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["preview", "christmas-classic", "--no-open", "-o", "p.png",
             "--blank-inside", "--inside-message", "HI"],
        )
        _refused(result, workdir, "Error: --blank-inside cannot be combined with --inside-message")

    def test_preview_reports_a_missing_photo_slot(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        photo = Path(__file__).resolve().parents[2] / (
            "src/holiday_card/data/templates/christmas/placeholder-photo.jpg"
        )
        result = runner.invoke(
            app, ["preview", "christmas-classic", "--no-open", "-o", "p.png", "-i", str(photo)]
        )
        _refused(result, workdir, "Error: christmas-classic has no photo slot", "Templates with photo slots:")

    def test_create_export_target_listing_is_unchanged(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(app, ["create", "christmas-classic", "--export-for", "nope"])
        _refused(
            result, workdir,
            "Error: \"unknown export target 'nope'. Available: letter, moo-a6, per-panel-pdf\"",
            "Available --export-for targets:",
            "  moo-a6: ",
        )

    def test_create_bad_format_message_is_unchanged(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(app, ["create", "christmas-classic", "--format", "png"])
        _refused(
            result, workdir,
            "Error: --format must be one of ('pdf', 'svg') or 'auto', got 'png'",
        )

    def test_create_unknown_voice_message_is_unchanged(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        result = runner.invoke(app, ["create", "christmas-classic", "--voice", "yelling"])
        _refused(
            result, workdir,
            "Error: Unknown --voice value 'yelling'. "
            "Available: warm, witty, spare, devotional, irreverent",
        )

    def test_create_letter_with_markdown_message_is_unchanged(
        self, runner: CliRunner, workdir: Path, tmp_path: Path
    ) -> None:
        md = tmp_path / "l.md"
        md.write_text("Hi\n")
        result = runner.invoke(
            app, ["create", "christmas-classic", "--ps", "x", "--inside-message-md", str(md)]
        )
        _refused(
            result, workdir,
            "Error: --inside-message-md cannot be combined with "
            "--salutation / --signoff / --signature / --ps "
            "(letter parts use a separate authoring surface). "
            "Either drop the Markdown file or move the letter "
            "structure into the body of the Markdown.",
        )

    def test_create_empty_markdown_message_is_unchanged(
        self, runner: CliRunner, workdir: Path, tmp_path: Path
    ) -> None:
        md = tmp_path / "empty.md"
        md.write_text("  \n\n ")
        result = runner.invoke(
            app, ["create", "christmas-classic", "--inside-message-md", str(md)]
        )
        _refused(result, workdir, f"Error reading {md}: ")

    def test_create_missing_markdown_message_is_unchanged(
        self, runner: CliRunner, workdir: Path, tmp_path: Path
    ) -> None:
        md = tmp_path / "missing.md"
        result = runner.invoke(
            app, ["create", "christmas-classic", "--inside-message-md", str(md)]
        )
        _refused(result, workdir, f"Error: --inside-message-md file not found: {md}")

    def test_create_summary_still_reports_picks_and_letter(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "-o", "c.pdf", *_CONTENT_FLAGS]
        )
        assert result.exit_code == 0, result.output
        assert "  Voice: spare" in result.output
        assert "  Picked cover: " in result.output
        assert "  Picked inside: " in result.output
        assert "  Inside: letter (salutation, body, P.S.)" in result.output

    def test_create_summary_counts_markdown_paragraphs(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        md = tmp_path / "l.md"
        md.write_text("One.\n\nTwo.\n")
        result = runner.invoke(
            app, ["create", "christmas-classic", "-o", "c.pdf", "--inside-message-md", str(md)]
        )
        assert result.exit_code == 0, result.output
        assert "  Inside: Markdown (2 paragraphs)" in result.output


class TestFoldTypeAlias:
    """``half_fold`` is the legacy spelling of the 4-up quarter fold (#58).

    Shipped templates say ``quarter_fold``; filtering by either spelling
    must list the same templates.
    """

    def _ids(self, runner: CliRunner, fold_type: str) -> list[str]:
        result = runner.invoke(
            app, ["templates", "--fold-type", fold_type, "--format", "json"]
        )
        assert result.exit_code == 0, result.output
        return sorted(t["id"] for t in json.loads(result.output)["templates"])

    def test_half_fold_and_quarter_fold_list_the_same_templates(
        self, runner: CliRunner
    ) -> None:
        quarter = self._ids(runner, "quarter_fold")
        assert len(quarter) == 21
        assert self._ids(runner, "half_fold") == quarter

    def test_tri_fold_lists_nothing(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["templates", "--fold-type", "tri_fold"])
        assert result.exit_code == 0
        assert "No templates found." in result.output


class TestInitScaffold:
    """``init`` scaffolds a quarter-fold template with no panel coordinates (#58)."""

    def test_scaffold_has_no_panel_coordinates_and_defaults_to_quarter_fold(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        import yaml

        result = runner.invoke(app, ["init", "my-card", "--output", str(tmp_path)])
        assert result.exit_code == 0, result.output
        data = yaml.safe_load((tmp_path / "my-card.yaml").read_text())
        assert data["fold_type"] == "quarter_fold"
        for panel in data["panels"]:
            assert not {"x", "y", "rotation"} & set(panel), panel["id"]

    def test_scaffold_loads_and_imposes(self, runner: CliRunner, tmp_path: Path) -> None:
        from holiday_card.core.imposition import panel_placements
        from holiday_card.core.models import Card, PanelPosition
        from holiday_card.core.templates import load_template_from_file

        result = runner.invoke(app, ["init", "my-card", "--output", str(tmp_path)])
        assert result.exit_code == 0, result.output
        template = load_template_from_file(tmp_path / "my-card.yaml")
        card = Card(
            name="c", template_id=template.id, fold_type=template.fold_type,
            panels=template.panels,
        )
        assert panel_placements(card)[PanelPosition.INSIDE_LEFT].quadrant == "TR"


_EDGE_GREETING = """    text_elements:
      - id: "greeting"
        content: "Merry Christmas!"
        x: 2.125  # Center of panel"""


class TestPanelFitOption:
    """``create --panel-fit`` and the safe-zone warning (#73, D8 / D4)."""

    def test_panel_fit_with_letter_exits_2(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "--panel-fit", "letterbox", "-o", "c.pdf"]
        )
        _refused(result, workdir, "Error: --panel-fit only applies to targets")

    def test_letterbox_with_moo_a6_exits_0(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(
            app, ["create", "christmas-classic", "--export-for", "moo-a6",
                  "--panel-fit", "letterbox", "-o", "out"],
        )
        assert result.exit_code == 0, result.output
        assert sorted(p.name for p in (workdir / "out").iterdir()) == [
            "back.pdf", "front.pdf", "inside-left.pdf", "inside-right.pdf",
        ]

    def test_text_outside_the_safe_zone_warns_on_stderr_and_exits_0(
        self, runner: CliRunner, workdir: Path, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _custom_templates(
            tmp_path, monkeypatch, _EDGE_GREETING,
            # Centre-aligned at x=0.05": half the greeting hangs off the panel.
            _EDGE_GREETING.replace("x: 2.125  # Center of panel", "x: 0.05"),
        )
        result = runner.invoke(
            app, ["create", "christmas-classic", "--export-for", "moo-a6", "-o", "out"]
        )
        assert result.exit_code == 0, result.output
        assert "Warning: " in result.stderr
        assert "greeting" in result.stderr
        assert (workdir / "out" / "front.pdf").exists()


# ---------------------------------------------------------------------------
# Template paths, the layered search path and init → create (#79)
# ---------------------------------------------------------------------------


def _next_step(output: str) -> list[str]:
    """The argv of the ``holiday-card create …`` line ``init`` printed."""
    import shlex

    lines = [ln.strip() for ln in output.splitlines() if ln.strip().startswith("holiday-card create")]
    assert len(lines) == 1, output
    argv = shlex.split(lines[0])
    assert argv[0] == "holiday-card"
    return argv[1:]


@pytest.fixture
def authoring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty cwd with an isolated XDG data home and no env layer."""
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("HOLIDAY_CARD_TEMPLATES", raising=False)
    return work


@pytest.mark.usefixtures("authoring")
class TestInitThenCreate:
    def test_init_writes_to_the_user_layer(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(app, ["init", "foo"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "xdg/holiday-card/templates/generic/foo.yaml").is_file()

    def test_printed_next_step_works(self, runner: CliRunner, authoring: Path) -> None:
        init = runner.invoke(app, ["init", "foo"])
        assert init.exit_code == 0, init.output
        argv = _next_step(init.stdout)
        assert argv[:2] == ["create", "foo"]
        result = runner.invoke(app, [*argv, "-o", "x.pdf"])
        assert result.exit_code == 0, result.output
        assert (authoring / "x.pdf").read_bytes().startswith(b"%PDF")

    def test_create_by_printed_path(
        self, runner: CliRunner, authoring: Path, tmp_path: Path
    ) -> None:
        assert runner.invoke(app, ["init", "foo"]).exit_code == 0
        path = tmp_path / "xdg/holiday-card/templates/generic/foo.yaml"
        result = runner.invoke(app, ["create", str(path), "-o", "x.pdf"])
        assert result.exit_code == 0, result.output
        assert (authoring / "x.pdf").is_file()

    def test_scaffold_validates(self, runner: CliRunner) -> None:
        assert runner.invoke(app, ["init", "foo"]).exit_code == 0
        result = runner.invoke(app, ["validate", "foo"])
        assert result.exit_code == 0, result.output

    def test_init_refuses_to_overwrite(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        assert runner.invoke(app, ["init", "foo"]).exit_code == 0
        path = tmp_path / "xdg/holiday-card/templates/generic/foo.yaml"
        path.write_text("edited")
        result = runner.invoke(app, ["init", "foo"])
        assert result.exit_code == 2
        assert "already exists" in result.stderr
        assert "--force" in result.stderr
        assert path.read_text() == "edited"

    def test_init_force_overwrites(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        assert runner.invoke(app, ["init", "foo"]).exit_code == 0
        path = tmp_path / "xdg/holiday-card/templates/generic/foo.yaml"
        path.write_text("edited")
        result = runner.invoke(app, ["init", "foo", "--force"])
        assert result.exit_code == 0, result.output
        assert "id: foo" in path.read_text()

    def test_init_rejects_an_unknown_occasion(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(app, ["init", "bar", "--occasion", "wedding"])
        assert result.exit_code == 2
        assert "wedding" in result.stderr
        for valid in ("christmas", "generic", "pet_loss"):
            assert valid in result.stderr
        assert not (tmp_path / "xdg").exists()

    def test_init_with_known_occasion_sets_it(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(app, ["init", "bday", "--occasion", "birthday"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "xdg/holiday-card/templates/birthday/bday.yaml").is_file()

    def test_init_outside_the_search_path_prints_a_path(
        self, runner: CliRunner
    ) -> None:
        init = runner.invoke(app, ["init", "foo", "--output", "tpl"])
        assert init.exit_code == 0, init.output
        argv = _next_step(init.stdout)
        assert argv[:2] == ["create", "tpl/foo.yaml"]
        result = runner.invoke(app, [*argv, "-o", "x.pdf"])
        assert result.exit_code == 0, result.output

    def test_voice_uses_the_path_templates_occasion(
        self, runner: CliRunner
    ) -> None:
        assert runner.invoke(
            app, ["init", "gone", "--occasion", "pet_loss", "--output", "tpl"]
        ).exit_code == 0
        # pet_loss ships no witty voice (generic does), so the refusal proves
        # the path-loaded template's own occasion was used.
        result = runner.invoke(
            app, ["create", "tpl/gone.yaml", "--voice", "witty", "-o", "x.pdf"]
        )
        assert result.exit_code == 2
        assert "'pet_loss'" in result.stderr


@pytest.mark.usefixtures("authoring")
class TestTemplatePaths:
    @pytest.fixture
    def tpl(self, authoring: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        # An env entry that doesn't exist must not hide the built-ins.
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", "/nonexistent")
        (authoring / "tpl").mkdir()
        path = authoring / "tpl" / "my.yaml"
        path.write_text(_CLASSIC_YAML.read_text())
        return path

    @pytest.mark.usefixtures("tpl")
    def test_create_relative_path(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["create", "./tpl/my.yaml", "-o", "x.pdf"])
        assert result.exit_code == 0, result.output

    def test_create_absolute_path(self, runner: CliRunner, tpl: Path) -> None:
        result = runner.invoke(app, ["create", str(tpl), "-o", "x.pdf"])
        assert result.exit_code == 0, result.output

    @pytest.mark.usefixtures("tpl")
    def test_validate_relative_path(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["validate", "./tpl/my.yaml"])
        assert result.exit_code == 0, result.output

    @pytest.mark.usefixtures("tpl")
    def test_builtins_stay_reachable(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["create", "christmas-modern", "-o", "x.pdf"])
        assert result.exit_code == 0, result.output

    def test_missing_path_exits_two_naming_it(
        self, runner: CliRunner, authoring: Path
    ) -> None:
        result = runner.invoke(app, ["create", "does/not/exist.yaml", "-o", "x.pdf"])
        assert result.exit_code == 2
        assert "Template not found: does/not/exist.yaml" in result.stderr
        assert not (authoring / "x.pdf").exists()

    def test_listing_adds_env_templates_to_the_builtins(
        self, runner: CliRunner, tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        extra = tmp_path / "extra"
        extra.mkdir()
        (extra / "x.yaml").write_text(
            _CLASSIC_YAML.read_text().replace(
                'id: "christmas-classic"', 'id: "extra-card"', 1
            )
        )
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(extra))
        result = runner.invoke(app, ["templates", "--format", "json"])
        assert result.exit_code == 0, result.output
        listed = json.loads(result.stdout)["templates"]
        assert sum(t["source"] == "builtin" for t in listed) == 21
        assert {t["id"]: t["source"] for t in listed}["extra-card"] == "env"


# ---------------------------------------------------------------------------
# Discovery surface (#80, D16): short flags, listing tables, help panels,
# exit codes. Rich help is rendered at a fixed width so it is deterministic.
# ---------------------------------------------------------------------------

_WIDE = {"COLUMNS": "120"}


def _plain(output: str) -> str:
    # Rich forces colour under GITHUB_ACTIONS; compare the text without ANSI styles.
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _help(runner: CliRunner, *command: str) -> str:
    result = runner.invoke(app, [*command, "--help"], env=_WIDE)
    assert result.exit_code == 0, result.output
    return _plain(result.output)


def _help_line(help_text: str, long: str) -> str:
    # The one option row that declares ``long`` (``--out`` must not match ``--output``).
    import re

    rows = [line for line in help_text.splitlines() if re.match(_option_row(long), line)]
    assert len(rows) == 1, f"{long}: {rows}"
    return rows[0]


def _option_row(long: str) -> str:
    # A Rich option row: the box edge, an optional required ``*``, then the flag.
    return rf"│\s+(\*\s+)?{long}(?![\w-])"


def _short_flags(line: str) -> set[str]:
    import re

    return set(re.findall(r"(?<![\w-])-[a-zA-Z](?![\w-])", line))


class TestShortFlags:
    @pytest.mark.parametrize(
        ("command", "long", "short"),
        [
            ((), "--version", "-V"),
            (("templates",), "--occasion", None),
            (("templates",), "--fold-type", "-f"),
            (("templates",), "--format", None),
            (("themes",), "--occasion", None),
            (("themes",), "--format", None),
            (("create",), "--message", "-m"),
            (("create",), "--output", "-o"),
            (("create",), "--fold-type", "-f"),
            (("create",), "--image", "-i"),
            (("create",), "--theme", "-t"),
            (("preview",), "--message", "-m"),
            (("preview",), "--output", "-o"),
            (("preview",), "--dpi", "-d"),
            (("preview",), "--fold-type", "-f"),
            (("preview",), "--image", "-i"),
            (("preview",), "--theme", "-t"),
            (("init",), "--occasion", None),
            (("init",), "--fold-type", "-f"),
            (("init",), "--output", "-o"),
            (("ai-asset", "generate"), "--output", "-o"),
            (("ai-asset", "generate"), "--provider", None),
            (("ai-asset", "generate"), "--model", None),
            (("ai-asset", "generate"), "--max-cost", None),
        ],
    )
    def test_short_flag_table(
        self, runner: CliRunner, command: tuple[str, ...], long: str, short: str | None
    ) -> None:
        line = _help_line(_help(runner, *command), long)
        assert _short_flags(line) == ({short} if short else set()), line

    def test_ai_asset_has_no_out_option(self, runner: CliRunner) -> None:
        import re

        text = _help(runner, "ai-asset", "generate")
        assert not any(re.match(_option_row("--out"), line) for line in text.splitlines())

    @pytest.mark.parametrize("command", ["templates", "themes"])
    def test_dash_o_is_no_longer_occasion(self, runner: CliRunner, command: str) -> None:
        result = runner.invoke(app, [command, "-o", "christmas"])
        assert result.exit_code == 2
        assert "No such option: -o" in _plain(result.output)

    def test_long_occasion_still_filters(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["templates", "--occasion", "christmas"])
        assert result.exit_code == 0, result.output

    def test_init_dash_o_is_the_output_dir(self, runner: CliRunner, tmp_path: Path) -> None:
        out = tmp_path / "d"
        result = runner.invoke(app, ["init", "x", "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert (out / "x.yaml").is_file()

    def test_ai_asset_out_is_gone(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["ai-asset", "generate", "--subject", "pine", "--out", str(tmp_path / "p.png")],
        )
        assert result.exit_code == 2
        assert "No such option: --out" in _plain(result.output)


def _table_rows(output: str) -> tuple[list[str], list[list[str]]]:
    # The header, then one row per line up to the blank line before the count.
    lines = output.splitlines()
    rows = []
    for line in lines[1:]:
        if not line.strip():
            break
        rows.append(line.split())
    return lines[0].split(), rows


class TestListingTables:
    def test_template_table_starts_with_the_id(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["templates"])
        assert result.exit_code == 0, result.output
        header, rows = _table_rows(result.output)
        assert header[:3] == ["ID", "OCCASION", "FOLD"]
        assert header[-1] == "NAME"
        assert "SOURCE" not in header  # every template is builtin
        assert "DESCRIPTION" not in header
        payload = json.loads(runner.invoke(app, ["templates", "--format", "json"]).output)
        ids = {t["id"] for t in payload["templates"]}
        assert len(rows) == len(ids) == 21
        assert {row[0] for row in rows} == ids

    def test_every_listed_id_is_accepted_by_create(self, runner: CliRunner, tmp_path: Path) -> None:
        # The acceptance criterion: `create <id> -o x.pdf` exits 0 for every row.
        _, rows = _table_rows(runner.invoke(app, ["templates"]).output)
        for row in rows:
            out = tmp_path / f"{row[0]}.pdf"
            result = runner.invoke(app, ["create", row[0], "-o", str(out)])
            assert result.exit_code == 0, (row[0], result.output)
            assert out.is_file()

    def test_template_rows_sorted_by_occasion_then_id(self, runner: CliRunner) -> None:
        _, rows = _table_rows(runner.invoke(app, ["templates"]).output)
        keys = [(row[1], row[0]) for row in rows]
        assert keys == sorted(keys)

    def test_ids_are_not_truncated(self, runner: CliRunner) -> None:
        _, rows = _table_rows(runner.invoke(app, ["templates"]).output)
        assert "christmas-holiday-masterpiece" in {row[0] for row in rows}

    def test_source_column_appears_with_a_user_template(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = tmp_path / "xdg" / "holiday-card" / "templates"
        user.mkdir(parents=True)
        source = _CLASSIC_YAML.read_text()
        assert 'id: "christmas-classic"' in source
        (user / "mine.yaml").write_text(
            source.replace('id: "christmas-classic"', 'id: "aaa-mine"', 1)
        )
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        result = runner.invoke(app, ["templates"])
        assert result.exit_code == 0, result.output
        header, rows = _table_rows(result.output)
        assert header == ["ID", "OCCASION", "FOLD", "SOURCE", "NAME"]
        sources = {row[0]: row[3] for row in rows}
        assert sources["aaa-mine"] == "user"
        assert sources["christmas-classic"] == "builtin"

    def test_theme_table_shows_ids_sorted(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["themes"])
        assert result.exit_code == 0, result.output
        header, rows = _table_rows(result.output)
        assert header[:2] == ["ID", "OCCASION"]
        assert header[-1] == "NAME"
        payload = json.loads(runner.invoke(app, ["themes", "--format", "json"]).output)
        assert {row[0] for row in rows} == {t["id"] for t in payload["themes"]}
        keys = [(row[1], row[0]) for row in rows]
        assert keys == sorted(keys)

    def test_every_listed_theme_id_is_accepted_by_create(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        _, rows = _table_rows(runner.invoke(app, ["themes"]).output)
        theme = rows[0][0]
        out = tmp_path / "t.pdf"
        result = runner.invoke(app, ["create", "christmas-classic", "-t", theme, "-o", str(out)])
        assert result.exit_code == 0, result.output

    @pytest.mark.parametrize("command", ["templates", "themes"])
    def test_unknown_format_is_a_usage_error(self, runner: CliRunner, command: str) -> None:
        result = runner.invoke(app, [command, "--format", "xml"])
        assert result.exit_code == 2
        assert "xml" in _plain(result.output)

    def test_json_keeps_full_descriptions(self, runner: CliRunner) -> None:
        payload = json.loads(runner.invoke(app, ["templates", "--format", "json"]).output)
        assert any(len(t["description"]) > 30 for t in payload["templates"])


class TestHelpPanels:
    _PANELS = {
        "Content": [
            "--message", "--inside-message", "--inside-message-md", "--voice",
            "--seed", "--blank-inside", "--theme", "--image",
        ],
        "Inside letter": ["--salutation", "--signoff", "--signature", "--ps", "--signature-font"],
        "Layout": ["--fold-type"],
        "Output": ["--output"],
    }

    @staticmethod
    def _panel_of(help_text: str, long: str) -> str:
        import re

        panel = None
        for line in help_text.splitlines():
            header = re.match(r"╭─ (.+?) ─", line)
            if header:
                panel = header.group(1)
            elif re.match(_option_row(long), line):
                assert panel is not None
                return panel
        raise AssertionError(f"{long} not in help")

    @pytest.mark.parametrize("command", ["create", "preview"])
    def test_options_are_grouped(self, runner: CliRunner, command: str) -> None:
        text = _help(runner, command)
        for panel, options in self._PANELS.items():
            for option in options:
                assert self._panel_of(text, option) == panel, (command, option)

    @pytest.mark.parametrize("command", ["create", "preview"])
    def test_panels_appear_in_reading_order(self, runner: CliRunner, command: str) -> None:
        import re

        panels = re.findall(r"╭─ (.+?) ─", _help(runner, command))
        assert panels == ["Arguments", "Options", "Content", "Inside letter", "Layout", "Output"]

    def test_create_only_options(self, runner: CliRunner) -> None:
        text = _help(runner, "create")
        assert self._panel_of(text, "--with-fold-marks") == "Layout"
        for option in ("--format", "--export-for"):
            assert self._panel_of(text, option) == "Output"
        assert "--debug-emit-ir" not in text

    def test_preview_only_options(self, runner: CliRunner) -> None:
        text = _help(runner, "preview")
        for option in ("--dpi", "--open"):
            assert self._panel_of(text, option) == "Output"


class TestExitCodes:
    def test_values_are_stable(self) -> None:
        from holiday_card.cli.exit_codes import ExitCode

        assert {c.name: c.value for c in ExitCode} == {
            "OK": 0,
            "ERROR": 1,
            "USAGE": 2,
            "CONSENT_REQUIRED": 3,
            "ENVIRONMENT": 4,
            "RAIL_REFUSED": 5,
            "PROVIDER_REFUSED": 6,
            "PROVIDER_ERROR": 7,
        }

    def test_root_help_lists_every_code(self, runner: CliRunner) -> None:
        import re

        text = _help(runner)
        assert "Exit codes" in text
        for code in range(8):
            assert re.search(rf"(?m)^\s*{code}\s+\S", text), code

    def test_commands_use_named_exit_codes(self) -> None:
        import re

        import holiday_card.cli.commands as commands

        source = Path(commands.__file__).read_text()
        assert not re.search(r"typer\.Exit\([0-9]", source)
