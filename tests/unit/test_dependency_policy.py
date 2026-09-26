"""Dependency-policy guards (expert-panel spec §P2, decision D2).

These read the repo's packaging/config files directly so that a future
edit which loosens a security floor, drops the lockfile, or re-pins
pre-commit's own tool versions fails loudly in CI.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pyproject() -> dict[str, Any]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _all_dependency_strings(pyproject: dict[str, Any]) -> list[str]:
    project = pyproject["project"]
    deps: list[str] = list(project["dependencies"])
    for extra in project.get("optional-dependencies", {}).values():
        deps.extend(extra)
    return deps


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_pillow_floor_includes_cve_2024_28219_fix(pyproject: dict[str, Any]) -> None:
    pillow = [d for d in pyproject["project"]["dependencies"] if d.lower().startswith("pillow")]
    assert len(pillow) == 1, pillow
    match = re.fullmatch(r"pillow>=([\d.]+)", pillow[0].replace(" ", ""), flags=re.IGNORECASE)
    assert match, f"Pillow must declare a >= floor, got {pillow[0]!r}"
    assert _version_tuple(match.group(1)) >= (10, 3, 0)


def test_no_dependency_uses_removed_typer_all_extra(pyproject: dict[str, Any]) -> None:
    offenders = [d for d in _all_dependency_strings(pyproject) if "typer[all]" in d]
    assert offenders == []


def test_uv_lock_is_committed() -> None:
    assert (REPO_ROOT / "uv.lock").is_file()


def test_uv_constrains_numpy_below_2_5(pyproject: dict[str, Any]) -> None:
    constraints = pyproject.get("tool", {}).get("uv", {}).get("constraint-dependencies", [])
    normalized = [c.replace(" ", "").lower() for c in constraints]
    assert "numpy<2.5" in normalized, constraints


def test_pre_commit_does_not_pin_its_own_ruff_or_mypy() -> None:
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text())
    repos = [r["repo"] for r in config["repos"]]
    assert not any("astral-sh/ruff-pre-commit" in r for r in repos), repos
    assert not any("mirrors-mypy" in r for r in repos), repos
