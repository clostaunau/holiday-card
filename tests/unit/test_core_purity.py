"""Core never imports ReportLab or the renderers (spec §P13 / §4, issue #75).

The compiler measures text through an injected ``TextMeasurer``; the
ReportLab implementation lives in ``renderers/reportlab_measurer.py`` and is
registered lazily by the package ``__init__``. ``generators.py`` is the one
composition root allowed a *function-local* ``holiday_card.renderers``
import (until #78 moves orchestration out of core).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "holiday_card" / "core"
CORE_MODULES = sorted(CORE_DIR.glob("*.py"))
# The composition root: may import renderers inside a function body only.
_COMPOSITION_ROOT = "generators.py"


def _imports(tree: ast.AST) -> list[tuple[ast.AST, str, bool]]:
    """Every (node, module, is_function_local) import in ``tree``."""
    found: list[tuple[ast.AST, str, bool]] = []

    def visit(node: ast.AST, in_function: bool) -> None:
        for child in ast.iter_child_nodes(node):
            local = in_function or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            if isinstance(child, ast.Import):
                found.extend((child, alias.name, in_function) for alias in child.names)
            elif isinstance(child, ast.ImportFrom) and child.module and child.level == 0:
                found.append((child, child.module, in_function))
                # `from holiday_card import renderers` spells the package as a name.
                if child.module == "holiday_card":
                    found.extend(
                        (child, f"holiday_card.{alias.name}", in_function)
                        for alias in child.names
                    )
            visit(child, local)

    visit(tree, False)
    return found


def test_core_modules_are_found() -> None:
    assert len(CORE_MODULES) > 20
    assert any(p.name == "compiler.py" for p in CORE_MODULES)


@pytest.mark.parametrize("path", CORE_MODULES, ids=lambda p: p.name)
def test_core_module_does_not_import_reportlab(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = [
        f"{path.name}:{node.lineno} imports {module}"  # type: ignore[attr-defined]
        for node, module, _local in _imports(tree)
        if module == "reportlab" or module.startswith("reportlab.")
    ]
    assert bad == []


@pytest.mark.parametrize("path", CORE_MODULES, ids=lambda p: p.name)
def test_core_module_does_not_import_renderers(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = [
        f"{path.name}:{node.lineno} imports {module}"  # type: ignore[attr-defined]
        for node, module, local in _imports(tree)
        if (module == "holiday_card.renderers" or module.startswith("holiday_card.renderers."))
        and not (path.name == _COMPOSITION_ROOT and local)
    ]
    assert bad == []


def test_ast_scan_sees_function_local_imports() -> None:
    # Guards the scanner itself: a nested import must not slip past it.
    tree = ast.parse(
        "def f():\n"
        "    if True:\n"
        "        from reportlab.pdfgen import canvas\n"
        "        from holiday_card import renderers\n"
    )
    modules = {(m, local) for _n, m, local in _imports(tree)}
    assert ("reportlab.pdfgen", True) in modules
    assert ("holiday_card.renderers", True) in modules


def _loaded_after(statement: str) -> list[str]:
    code = (
        f"{statement}\n"
        "import sys\n"
        "print('\\n'.join(sorted(m for m in sys.modules\n"
        "    if m.split('.')[0] == 'reportlab' or m.startswith('holiday_card.renderers'))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return result.stdout.split()


def test_importing_the_compiler_does_not_load_reportlab() -> None:
    assert _loaded_after("import holiday_card.core.compiler") == []


def test_importing_every_core_module_does_not_load_reportlab_or_renderers() -> None:
    statement = "\n".join(f"import holiday_card.core.{p.stem}" for p in CORE_MODULES)
    assert _loaded_after(statement) == []


def test_importing_the_package_does_not_load_reportlab() -> None:
    assert _loaded_after("import holiday_card") == []
