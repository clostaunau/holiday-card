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


# --------------------------------------------------------------------------- urllib.request (#149)

_URLLIB_OWNER = "src/holiday_card/core/ai_openrouter.py"
_HTTP_CLIENTS = ("openai", "httpx", "httpx2", "requests")


def urllib_request_imports(source: str) -> list[int]:
    """Lines importing ``urllib.request``: ``import urllib.request``,
    ``from urllib.request import …`` and ``from urllib import request``."""
    lines = []
    for node, module, _local in imports(ast.parse(source)):
        if module == "urllib.request" or module.startswith("urllib.request."):
            lines.append(node.lineno)  # type: ignore[attr-defined]
        elif (
            module == "urllib"
            and isinstance(node, ast.ImportFrom)
            and any(alias.name == "request" for alias in node.names)
        ):
            lines.append(node.lineno)
    return lines


@pytest.mark.parametrize(
    "source",
    [
        "import urllib.request\n",
        "from urllib.request import urlopen\n",
        "from urllib import request\n",
        "from urllib import parse, request as r\n",
        "def f():\n    import urllib.request as u\n",
        "__import__('urllib.request')\n",
    ],
)
def test_scanner_sees_every_urllib_request_spelling(source: str) -> None:
    assert urllib_request_imports(source) != []


@pytest.mark.parametrize(
    "source",
    ["from urllib.parse import urlsplit\n", "import urllib.parse\n", "from urllib import parse\n"],
)
def test_urllib_parse_is_not_urllib_request(source: str) -> None:
    assert urllib_request_imports(source) == []


def test_only_ai_openrouter_imports_urllib_request() -> None:
    importers = sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for p in SCANNED
        if urllib_request_imports(p.read_text(encoding="utf-8"))
    )
    # The dev-only catalogue refresher (#148; never run in CI) is the one script exception.
    assert importers == ["scripts/refresh_openrouter_models.py", _URLLIB_OWNER]


def test_ai_openrouter_imports_no_third_party_http_client() -> None:
    tree = ast.parse((REPO_ROOT / _URLLIB_OWNER).read_text(encoding="utf-8"))
    roots = {module.split(".")[0] for _n, module, _l in imports(tree)}
    assert not roots & set(_HTTP_CLIENTS)


def test_importing_the_cli_loads_neither_urllib_request_nor_the_client() -> None:
    code = (
        "import sys, holiday_card.cli.commands\n"
        "print('urllib.request' in sys.modules, 'holiday_card.core.ai_openrouter' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120
    )
    assert result.stdout.split() == ["False", "False"]
