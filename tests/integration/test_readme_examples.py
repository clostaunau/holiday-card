"""Every ``holiday-card …`` example in README.md's bash blocks runs and exits 0 (#88).

The examples are pulled out of the fenced ``bash`` blocks, run through
Typer's ``CliRunner`` in a fresh ``tmp_path`` cwd with the files they name
pre-seeded, and must exit 0. ``ai-asset`` (network) is skipped, and so is
anything that isn't a ``holiday-card`` line (``pipx``, ``pip``, ``uv run``).
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from holiday_card.cli.commands import app
from holiday_card.core.data_paths import data_path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
MIN_EXAMPLES = 6

_FENCE = re.compile(r"^```bash\s*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def extract_cli_examples(markdown: str) -> list[list[str]]:
    """Return the argv (after ``holiday-card``) of every CLI line in the bash blocks.

    ``\\`` continuations are joined, ``# …`` comments stripped (shell-style,
    so a ``#`` inside quotes is kept), and ``ai-asset`` lines skipped.
    """
    examples: list[list[str]] = []
    for block in _FENCE.findall(markdown):
        logical: list[str] = []
        pending = ""
        for raw in block.splitlines():
            if raw.rstrip().endswith("\\"):
                pending += raw.rstrip()[:-1] + " "
                continue
            logical.append(pending + raw)
            pending = ""
        if pending:
            logical.append(pending)
        for line in logical:
            argv = shlex.split(line, comments=True)
            if not argv or argv[0] != "holiday-card":
                continue
            if "ai-asset" in argv:
                continue
            examples.append(argv[1:])
    return examples


def _readme_examples() -> list[list[str]]:
    return extract_cli_examples(README.read_text(encoding="utf-8"))


# --- the extractor itself --------------------------------------------------


def test_extractor_joins_continuations_and_strips_comments() -> None:
    md = (
        "```bash\n"
        "# a comment line\n"
        'holiday-card create x -m "Hi # not a comment" \\\n'
        "  --inside-message y   # trailing comment\n"
        "pipx install holiday-card\n"
        "uv run holiday-card create z\n"
        "holiday-card ai-asset generate \\\n"
        "  --subject s\n"
        "```\n"
        "```text\n"
        "holiday-card create not-bash\n"
        "```\n"
    )
    assert extract_cli_examples(md) == [
        ["create", "x", "-m", "Hi # not a comment", "--inside-message", "y"],
    ]


def test_readme_has_enough_examples() -> None:
    # A parser regression must not pass vacuously with zero cases.
    assert len(_readme_examples()) >= MIN_EXAMPLES


# --- the README examples ----------------------------------------------------


def _seed_workspace(root: Path, home: Path) -> None:
    builtin = data_path("templates")
    photo = builtin / "christmas" / "placeholder-photo.jpg"
    (root / "letter.md").write_text(
        "Dear all,\n\nWhat a **year**. We *mostly* survived it.\n\nLove,  \nUs\n",
        encoding="utf-8",
    )
    shutil.copy(builtin / "christmas" / "classic.yaml", root / "my-template.yaml")
    for name in ("cover.jpg", "star.jpg", "me.jpg"):
        shutil.copy(photo, root / name)
    home.mkdir()
    shutil.copy(photo, home / "me.jpg")


def _prepare_argv(argv: list[str]) -> list[str]:
    # The shell would expand ``~``; CliRunner doesn't.
    out = [os.path.expanduser(a) if a.startswith("~") else a for a in argv]
    if "preview" in out and "--no-open" not in out:
        out.append("--no-open")
    return out


@pytest.mark.parametrize(
    "argv", _readme_examples(), ids=lambda a: " ".join(a)[:80]
)
def test_readme_example_exits_zero(
    argv: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    home = tmp_path / "home"
    _seed_workspace(work, home)
    monkeypatch.chdir(work)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("HOLIDAY_CARD_TEMPLATES", raising=False)
    # `create my-card` follows `init my-card` in the README; seed it.
    user_dir = tmp_path / "xdg" / "holiday-card" / "templates" / "generic"
    user_dir.mkdir(parents=True)
    if argv[:1] != ["init"]:
        text = (work / "my-template.yaml").read_text(encoding="utf-8")
        (user_dir / "my-card.yaml").write_text(
            text.replace("id: christmas-classic", "id: my-card", 1), encoding="utf-8"
        )

    result = CliRunner().invoke(app, _prepare_argv(argv))

    assert result.exit_code == 0, (
        f"README example failed: holiday-card {shlex.join(argv)}\n{result.output}"
    )
