"""Packaging metadata and release-workflow guards (expert-panel spec §P15, D1, D2, issue #86).

These read ``pyproject.toml`` and ``.github/workflows/release.yml`` directly, so
an edit that re-duplicates the version, bloats the sdist, drops a project URL,
or hands the publish job a long-lived token fails here instead of on PyPI.
"""

from __future__ import annotations

import importlib.metadata
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.requirements import Requirement

import holiday_card

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_release_version import (  # noqa: E402  (sys.path manipulation)
    extract_release_notes,
    main,
    tag_matches_version,
)


@pytest.fixture(scope="module")
def pyproject() -> dict[str, Any]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


@pytest.fixture(scope="module")
def project(pyproject: dict[str, Any]) -> dict[str, Any]:
    return pyproject["project"]  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def release() -> dict[str, Any]:
    data = yaml.safe_load(RELEASE_YML.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


# --- version ----------------------------------------------------------------


def test_version_is_dynamic_and_not_literal(project: dict[str, Any]) -> None:
    assert "version" in project["dynamic"]
    assert "version" not in project


def test_hatch_reads_the_version_from_the_package(pyproject: dict[str, Any]) -> None:
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/holiday_card/__init__.py"


def test_installed_metadata_version_matches_dunder_version() -> None:
    assert importlib.metadata.version("holiday-card") == holiday_card.__version__


# --- metadata ---------------------------------------------------------------


def test_classifiers_cover_every_tested_python(project: dict[str, Any]) -> None:
    classifiers = project["classifiers"]
    for minor in ("3.11", "3.12", "3.13"):
        assert f"Programming Language :: Python :: {minor}" in classifiers


def test_no_license_classifier_alongside_pep639_license(project: dict[str, Any]) -> None:
    assert project["license"] == "MIT"
    assert [c for c in project["classifiers"] if c.startswith("License ::")] == []


def test_license_files_name_every_bundled_license(project: dict[str, Any]) -> None:
    files = project["license-files"]
    assert "LICENSE" in files
    assert "src/holiday_card/data/fonts/LICENSE" in files
    assert "src/holiday_card/data/fonts/curated/*-LICENSE.txt" in files
    assert "src/holiday_card/data/icc/NOTICE" in files


def test_authors_is_not_a_placeholder(project: dict[str, Any]) -> None:
    names = [author["name"] for author in project["authors"]]
    assert names and "Holiday Card Team" not in names


def test_project_urls_point_at_the_repo(project: dict[str, Any]) -> None:
    urls = project["urls"]
    assert urls["Source"] == "https://github.com/clostaunau/holiday-card"
    assert urls["Issues"] == "https://github.com/clostaunau/holiday-card/issues"


def test_openai_extra_has_an_upper_bound(project: dict[str, Any]) -> None:
    (openai,) = [
        Requirement(r) for r in project["optional-dependencies"]["ai"] if r.startswith("openai")
    ]
    assert any(spec.operator == "<" for spec in openai.specifier)


# --- sdist ------------------------------------------------------------------


def test_sdist_include_list_excludes_repo_clutter(pyproject: dict[str, Any]) -> None:
    include = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    roots = {entry.strip("/").split("/")[0] for entry in include}
    assert roots.isdisjoint({"data", ".claude", ".specify", ".devcontainer", "specs", "output"})
    assert {"src", "tests", "LICENSE", "README.md", "uv.lock", "pyproject.toml"} <= roots


def test_sdist_include_entries_are_anchored_at_the_repo_root(pyproject: dict[str, Any]) -> None:
    # Hatch reads these as gitignore patterns: an unanchored "README.md" also
    # matches .claude/**/README.md and drags the whole tree back in.
    include = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    assert [entry for entry in include if not entry.startswith("/")] == []


# --- release.yml ------------------------------------------------------------


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    on = workflow.get("on", workflow.get(True))
    assert isinstance(on, dict)
    return on


def test_release_triggers_on_version_tags_and_its_own_prs(release: dict[str, Any]) -> None:
    triggers = _triggers(release)
    assert triggers["push"]["tags"] == ["v[0-9]+.[0-9]+.[0-9]+"]
    assert ".github/workflows/release.yml" in triggers["pull_request"]["paths"]


def test_release_is_read_only_at_the_top(release: dict[str, Any]) -> None:
    assert release["permissions"] == {"contents": "read"}


def test_publish_uses_oidc_in_the_pypi_environment(release: dict[str, Any]) -> None:
    publish = release["jobs"]["publish"]
    assert publish["permissions"] == {"id-token": "write"}
    environment = publish["environment"]
    assert (environment["name"] if isinstance(environment, dict) else environment) == "pypi"
    assert "build" in publish["needs"]
    assert "startsWith(github.ref, 'refs/tags/v')" in publish["if"]
    uses = [step.get("uses", "") for step in publish["steps"]]
    assert any(u.startswith("pypa/gh-action-pypi-publish@") for u in uses)


def test_no_release_step_passes_a_password(release: dict[str, Any]) -> None:
    for job in release["jobs"].values():
        for step in job.get("steps", []):
            assert "password" not in (step.get("with") or {})


def test_github_release_job_is_tag_only_and_may_write_contents(release: dict[str, Any]) -> None:
    job = release["jobs"]["github-release"]
    assert job["permissions"] == {"contents": "write"}
    assert "publish" in job["needs"]
    assert "startsWith(github.ref, 'refs/tags/v')" in job["if"]
    script = "\n".join(step.get("run", "") for step in job["steps"])
    assert "gh release create" in script
    assert "--notes-file" in script


def test_build_job_checks_the_tag_and_runs_twine_strict(release: dict[str, Any]) -> None:
    script = "\n".join(step.get("run", "") for step in release["jobs"]["build"]["steps"])
    assert "check_release_version.py" in script
    assert re.search(r"uvx twine==\d+\.\d+\.\d+ check --strict dist/\*", script)
    assert "holiday-card create christmas-classic" in script


# --- scripts/check_release_version.py ---------------------------------------


@pytest.mark.parametrize(
    ("tag", "version", "ok"),
    [
        ("v1.3.0", "1.3.0", True),
        ("v1.3.1", "1.3.0", False),
        ("1.3.0", "1.3.0", False),
        ("v1.3.0", "1.3.0rc1", False),
        ("refs/tags/v1.3.0", "1.3.0", False),
    ],
)
def test_tag_matches_version(tag: str, version: str, ok: bool) -> None:
    assert tag_matches_version(tag, version) is ok


def test_check_exits_nonzero_on_mismatch(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "v1.3.1", "1.3.0"]) != 0
    assert "v1.3.1" in capsys.readouterr().err


def test_check_exits_zero_on_match() -> None:
    assert main(["check", "v1.3.0", "1.3.0"]) == 0


NOTES = """# Release Notes

## v1.4.0 — "Next" — 2026-10-01

New things.

### Detail

More.

## v1.3.0 — "Old" — 2026-06-02

Old things.
"""


def test_extract_release_notes_returns_only_the_matching_section() -> None:
    body = extract_release_notes(NOTES, "v1.4.0")
    assert body.startswith("New things.")
    assert "### Detail" in body
    assert "Old things" not in body
    assert "v1.3.0" not in body


def test_extract_release_notes_last_section_runs_to_eof() -> None:
    assert extract_release_notes(NOTES, "v1.3.0").strip() == "Old things."


def test_extract_release_notes_does_not_prefix_match() -> None:
    with pytest.raises(LookupError):
        extract_release_notes(NOTES, "v1.4")


def test_notes_subcommand_fails_for_a_missing_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    notes = tmp_path / "RELEASE_NOTES.md"
    notes.write_text(NOTES, encoding="utf-8")
    assert main(["notes", "v9.9.9", str(notes)]) != 0
    assert "v9.9.9" in capsys.readouterr().err


def test_notes_subcommand_prints_the_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    notes = tmp_path / "RELEASE_NOTES.md"
    notes.write_text(NOTES, encoding="utf-8")
    assert main(["notes", "v1.3.0", str(notes)]) == 0
    assert capsys.readouterr().out.strip() == "Old things."


def test_shipped_release_notes_have_a_section_for_the_current_version() -> None:
    text = (REPO_ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert extract_release_notes(text, f"v{holiday_card.__version__}").strip()


def test_build_backend_supports_pep639_license_files(pyproject: dict[str, Any]) -> None:
    # SPDX `license = "MIT"` + `license-files` globs need hatchling >= 1.27.
    (hatchling,) = [
        Requirement(r) for r in pyproject["build-system"]["requires"] if r.startswith("hatchling")
    ]
    assert hatchling.specifier.contains("1.27.0")
    assert not hatchling.specifier.contains("1.26.3")
