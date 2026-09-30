"""The one AST import walker for the suite's import-policy tests (#75, #143).

Importable from any test as ``ast_imports`` because ``tests/conftest.py``
puts ``tests/`` on ``sys.path`` (like ``rasterize``).
"""

from __future__ import annotations

import ast

# Calls that import the module named by a string-constant first argument.
_DYNAMIC_IMPORTERS = {"import_module", "__import__"}


def _dynamic_import(node: ast.Call) -> str | None:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if name not in _DYNAMIC_IMPORTERS or not node.args:
        return None
    first = node.args[0]
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def imports(tree: ast.AST) -> list[tuple[ast.AST, str, bool]]:
    """Every (node, module, is_function_local) import in ``tree``.

    Covers ``import x``, absolute ``from x import y`` (plus ``from holiday_card
    import renderers`` as ``holiday_card.renderers``) and ``importlib.
    import_module("x")`` / ``__import__("x")`` with a constant name, at any depth.
    """
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
            elif isinstance(child, ast.Call) and (module := _dynamic_import(child)):
                found.append((child, module, in_function))
            visit(child, local)

    visit(tree, False)
    return found
