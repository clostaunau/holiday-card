"""Counts and claims in README.md / CLAUDE.md / help text match the code (#88).

The template count is asserted against ``discover_templates``. Test counts
are not asserted anywhere: README no longer states one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer.main
from typer.testing import CliRunner

from holiday_card.cli import commands
from holiday_card.cli.commands import app
from holiday_card.core.data_paths import data_path
from holiday_card.core.models import OccasionType
from holiday_card.core.templates import discover_templates

REPO_ROOT = Path(__file__).resolve().parents[2]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
CLAUDE_MD = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
COMMANDS_SRC = Path(commands.__file__).read_text(encoding="utf-8")
HISTORICAL_BANNER = "> **Historical** — commands may not match the current CLI; see README."
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _shipped_count() -> int:
    return len(discover_templates(data_path("templates")))


def _plain(text: str) -> str:
    return " ".join(_ANSI.sub("", text).split())


def _option_help(command: str, flag: str) -> str:
    cmd = typer.main.get_command(app).commands[command]  # type: ignore[attr-defined]
    for param in cmd.params:
        if flag in param.opts:
            return str(param.help)
    raise AssertionError(f"{command} has no {flag}")


# --- counts ------------------------------------------------------------------


def test_readme_template_count_matches_discovery() -> None:
    m = re.search(r"(\d+) ship-quality templates", README)
    assert m, "README no longer states the template count"
    assert int(m.group(1)) == _shipped_count()


@pytest.mark.parametrize(
    "pattern",
    [r"# YAML card templates \((\d+)\)", r"All (\d+) shipped templates"],
)
def test_claude_md_template_count_matches_discovery(pattern: str) -> None:
    m = re.search(pattern, CLAUDE_MD)
    assert m, f"CLAUDE.md no longer matches {pattern!r}"
    assert int(m.group(1)) == _shipped_count()


def test_readme_states_no_test_count() -> None:
    assert not re.search(r"\b\d+ tests\b", README)


def test_readme_numbered_list_matches_its_heading() -> None:
    words = {"five": 5, "six": 6, "seven": 7}
    m = re.search(r"## (\w+) things you can do today", README, re.IGNORECASE)
    assert m
    section = README[m.end():].split("\n## ", 1)[0]
    items = re.findall(r"^# \d+\. ", section, re.MULTILINE)
    assert words[m.group(1).lower()] == len(items)


# --- README claims ---------------------------------------------------------------


def test_readme_output_formats_say_png_is_preview_only() -> None:
    row = next(line for line in README.splitlines() if line.startswith("| **Output formats**"))
    assert "PNG" in row and "preview" in row


def test_readme_markdown_mode_mentions_italic() -> None:
    m = re.search(r"# 6\. Christmas-letter mode.*?```", README, re.DOTALL)
    assert m and "italic" in m.group(0)


def test_no_nonexistent_reference_image_in_docs() -> None:
    assert "motif.png" not in README
    assert "motif.png" not in COMMANDS_SRC


# --- help text -----------------------------------------------------------------


def test_create_output_help_names_both_formats_and_directories() -> None:
    text = _option_help("create", "--output")
    assert ".pdf" in text and ".svg" in text and "directory" in text


def test_inside_message_md_help_lists_italic_and_no_lato_only_claim() -> None:
    text = _option_help("create", "--inside-message-md")
    assert "*italic*" in text and "***bold-italic***" in text
    assert "only curated font" not in text


def test_init_help_lists_every_occasion() -> None:
    result = CliRunner().invoke(app, ["init", "--help"], terminal_width=200)
    assert result.exit_code == 0
    plain = _plain(result.output)
    missing = [o.value for o in OccasionType if o.value not in plain]
    assert not missing, missing


def test_init_scaffold_uses_no_helvetica() -> None:
    assert '"Helvetica"' not in COMMANDS_SRC


def test_root_help_mentions_every_output_format() -> None:
    result = CliRunner().invoke(app, ["--help"], terminal_width=200)
    plain = _plain(result.output)
    assert "PDF" in plain and "SVG" in plain and "PNG" in plain


# --- historical specs ---------------------------------------------------------


@pytest.mark.parametrize(
    "path", sorted((REPO_ROOT / "specs").glob("*/quickstart.md")), ids=lambda p: p.parent.name
)
def test_spec_quickstart_starts_with_historical_banner(path: Path) -> None:
    assert path.read_text(encoding="utf-8").splitlines()[0] == HISTORICAL_BANNER
