"""Only ``core/ai_openai.py`` may import ``openai``, and only inside a function (#143).

The OpenAI SDK is the optional ``[ai]`` extra. ``cli/commands.py`` imports
``ai_providers`` (and through it ``ai_openai``) at the top level, so a
module-level ``import openai`` anywhere on that path would make the extra a
hard dependency of every CLI start. Held here by an AST scan of ``src/`` and
``scripts/`` plus a subprocess that watches ``sys.meta_path``.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from ast_imports import imports

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNED = sorted(
    [*(REPO_ROOT / "src" / "holiday_card").rglob("*.py"), *(REPO_ROOT / "scripts").glob("*.py")]
)
# The one module allowed to import the SDK, and only function-locally.
_ALLOWED = "src/holiday_card/core/ai_openai.py"


def openai_violations(rel_path: str, source: str) -> list[str]:
    """``path:line imports openai`` for every import of ``openai`` the rule forbids."""
    tree = ast.parse(source)
    return [
        f"{rel_path}:{node.lineno} imports openai"  # type: ignore[attr-defined]
        for node, module, local in imports(tree)
        if (module == "openai" or module.startswith("openai."))
        and not (rel_path == _ALLOWED and local)
    ]


def test_the_scan_covers_src_and_scripts() -> None:
    rel = {p.relative_to(REPO_ROOT).as_posix() for p in SCANNED}
    assert _ALLOWED in rel
    assert "src/holiday_card/cli/commands.py" in rel
    assert any(r.startswith("scripts/") for r in rel)


@pytest.mark.parametrize(
    "path", SCANNED, ids=lambda p: p.relative_to(REPO_ROOT).as_posix()
)
def test_openai_is_imported_only_function_locally_in_ai_openai(path: Path) -> None:
    rel = path.relative_to(REPO_ROOT).as_posix()
    assert openai_violations(rel, path.read_text(encoding="utf-8")) == []


def test_ai_openai_does_import_openai_function_locally() -> None:
    # Keeps the allowlist honest: the scan must actually see the SDK imports.
    tree = ast.parse((REPO_ROOT / _ALLOWED).read_text(encoding="utf-8"))
    found = [local for _n, m, local in imports(tree) if m.split(".")[0] == "openai"]
    assert found and all(found)


def test_scanner_flags_a_top_level_openai_import() -> None:
    assert openai_violations(_ALLOWED, "import os\nimport openai\n") == [
        f"{_ALLOWED}:2 imports openai"
    ]


@pytest.mark.parametrize(
    "source",
    [
        "from openai import OpenAI\n",
        "from openai.types import ImagesResponse\n",
        "import openai.types as t\n",
        "def f():\n    import openai\n",
    ],
)
def test_scanner_flags_openai_outside_ai_openai(source: str) -> None:
    assert openai_violations("src/holiday_card/core/ai_assets.py", source) != []


def test_scanner_flags_import_module_string() -> None:
    source = "import importlib\n\ndef f():\n    importlib.import_module('openai')\n"
    assert openai_violations("scripts/tool.py", source) == ["scripts/tool.py:4 imports openai"]


@pytest.mark.parametrize(
    "source",
    [
        "from importlib import import_module\nimport_module('openai.types')\n",
        "__import__('openai')\n",
    ],
)
def test_scanner_flags_dynamic_import_spellings(source: str) -> None:
    assert openai_violations("src/holiday_card/cli/commands.py", source) != []


def test_scanner_ignores_a_non_constant_import_module_argument() -> None:
    assert openai_violations("x.py", "import importlib\nimportlib.import_module(name)\n") == []


def test_scanner_reports_nested_import_as_function_local() -> None:
    tree = ast.parse("import openai\n\ndef f():\n    if x:\n        import openai\n")
    assert [(m, local) for _n, m, local in imports(tree)] == [
        ("openai", False),
        ("openai", True),
    ]


_WATCH_OPENAI = """\
import sys

class _Recorder:
    seen = []

    @classmethod
    def find_spec(cls, name, path=None, target=None):
        if name == "openai" or name.startswith("openai."):
            cls.seen.append(name)
        return None

sys.meta_path.insert(0, _Recorder)
{statement}
print("\\n".join(_Recorder.seen))
"""


def _openai_lookups_during(statement: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-c", _WATCH_OPENAI.format(statement=statement)],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return result.stdout.split()


def test_the_recorder_sees_an_openai_lookup() -> None:
    # Guards the runtime check: it must see an attempt even when openai is absent.
    assert _openai_lookups_during("import importlib.util\nimportlib.util.find_spec('openai')") == [
        "openai"
    ]


def test_importing_the_cli_never_looks_for_openai() -> None:
    assert _openai_lookups_during("import holiday_card.cli.commands") == []
