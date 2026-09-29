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
        # An empty bundled catalog means a broken install (D4: fail loud).
        monkeypatch.setenv("HOLIDAY_CARD_TEMPLATES", str(tmp_path))
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
        # Either yaml-parse error or template-validation error — both acceptable.
        assert ("invalid" in result.stderr.lower()
                or "error" in result.stderr.lower())


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
            "Available: devotional, spare, warm",
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
            "Error: voice 'warm' has no inside sentiment for occasion 'christmas'",
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

    def test_panel_background_image(
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
        _refused(result, workdir, "panel background_image is not supported (panel front)")

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
