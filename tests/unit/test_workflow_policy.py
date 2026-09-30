"""CI supply-chain policy guards (expert-panel spec §P15, decision D2, issue #85).

These parse every ``.github/workflows/*.yml`` (plus ``dependabot.yml`` and the
pre-commit config) so that an edit which re-introduces a tag-pinned action, an
unscoped token, an expression spliced into a shell script, or an unguarded
fork-PR comment fails in CI instead of in a security review.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
WORKFLOW_FILES = sorted(WORKFLOWS_DIR.glob("*.yml"))
SHA_PIN = re.compile(r"@[0-9a-f]{40}$")
FORK_GUARD = "github.event.pull_request.head.repo.full_name == github.repository"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} is not a YAML mapping"
    return data


def _steps(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (job_id, step) for job_id, job in workflow["jobs"].items() for step in job.get("steps", [])
    ]


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    # PyYAML (YAML 1.1) parses the bare key ``on`` as the boolean True.
    on = workflow.get("on", workflow.get(True))
    assert isinstance(on, dict)
    return on


@pytest.fixture(scope="module")
def workflows() -> dict[str, dict[str, Any]]:
    return {path.name: _load(path) for path in WORKFLOW_FILES}


def test_the_expected_workflows_are_scanned(workflows: dict[str, dict[str, Any]]) -> None:
    assert {"ci.yml", "latest-deps.yml", "microsite.yml", "render-cards.yml"} <= set(workflows)


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_full_commit_sha(path: Path) -> None:
    unpinned = [
        f"{job}: {step['uses']}"
        for job, step in _steps(_load(path))
        if "uses" in step and not step["uses"].startswith("./") and not SHA_PIN.search(step["uses"])
    ]
    assert unpinned == []


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_every_sha_pin_carries_a_version_comment(path: Path) -> None:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if re.search(r"uses: [^./][^ ]*@[0-9a-f]{40}", line)
    ]
    assert lines, f"{path.name} uses no actions"
    assert [line for line in lines if not re.search(r"@[0-9a-f]{40} # v\d", line)] == []


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_every_workflow_scopes_its_token(path: Path) -> None:
    workflow = _load(path)
    permissions = workflow.get("permissions")
    assert isinstance(permissions, dict), f"{path.name} has no top-level permissions mapping"
    grants = [permissions] + [
        job["permissions"] for job in workflow["jobs"].values() if "permissions" in job
    ]
    assert "write-all" not in grants


@pytest.mark.parametrize("name", ["ci.yml", "latest-deps.yml"])
def test_ci_workflows_are_read_only_at_the_top(
    workflows: dict[str, dict[str, Any]], name: str
) -> None:
    assert workflows[name]["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_no_expression_is_interpolated_into_a_run_script(path: Path) -> None:
    offenders = [
        f"{job}: {step.get('name', step['run'][:40])}"
        for job, step in _steps(_load(path))
        if "run" in step and "${{" in step["run"]
    ]
    assert offenders == []


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_every_checkout_drops_its_credentials(path: Path) -> None:
    checkouts = [
        (job, step)
        for job, step in _steps(_load(path))
        if step.get("uses", "").startswith("actions/checkout@")
    ]
    offenders = [
        job
        for job, step in checkouts
        if (step.get("with") or {}).get("persist-credentials") is not False
    ]
    assert offenders == []


def test_render_cards_keeps_the_pull_request_trigger(workflows: dict[str, dict[str, Any]]) -> None:
    triggers = _triggers(workflows["render-cards.yml"])
    assert "pull_request" in triggers
    assert "pull_request_target" not in triggers


def test_render_cards_comment_steps_are_skipped_on_fork_prs(
    workflows: dict[str, dict[str, Any]],
) -> None:
    comment_steps = [
        step
        for _, step in _steps(workflows["render-cards.yml"])
        if "peter-evans/" in step.get("uses", "")
    ]
    assert len(comment_steps) == 2
    assert all(FORK_GUARD in step.get("if", "") for step in comment_steps)


def test_render_cards_writes_the_preview_list_to_the_job_summary_on_fork_prs(
    workflows: dict[str, dict[str, Any]],
) -> None:
    fork_forms = FORK_GUARD.replace("==", "!=")
    summary_steps = [
        step
        for _, step in _steps(workflows["render-cards.yml"])
        if fork_forms in step.get("if", "") and "GITHUB_STEP_SUMMARY" in step.get("run", "")
    ]
    assert len(summary_steps) == 1
    assert "comment-body.md" in summary_steps[0]["run"]


def test_ci_has_a_pinned_strict_pip_audit_of_the_lock(workflows: dict[str, dict[str, Any]]) -> None:
    audit = workflows["ci.yml"]["jobs"]["audit"]
    script = "\n".join(step.get("run", "") for step in audit["steps"])
    assert "uv export --frozen --all-extras --no-emit-project --format requirements-txt" in script
    assert re.search(r"uvx pip-audit==\d+\.\d+\.\d+ ", script)
    for flag in ("--disable-pip", "--require-hashes", "--strict"):
        assert flag in script


def test_latest_deps_audits_the_lock_weekly(workflows: dict[str, dict[str, Any]]) -> None:
    workflow = workflows["latest-deps.yml"]
    assert "schedule" in _triggers(workflow)
    scripts = "\n".join(step.get("run", "") for _, step in _steps(workflow))
    assert re.search(r"uvx pip-audit==\d+\.\d+\.\d+ ", scripts)


def test_every_pip_audit_ignore_is_justified() -> None:
    for path in WORKFLOW_FILES:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "--ignore-vuln" in line:
                assert "#" in line, f"{path.name}: unjustified suppression: {line.strip()}"


def test_dependabot_watches_actions_and_the_uv_lock() -> None:
    config = _load(REPO_ROOT / ".github" / "dependabot.yml")
    assert config["version"] == 2
    by_ecosystem = {entry["package-ecosystem"]: entry for entry in config["updates"]}
    assert {"github-actions", "uv"} <= set(by_ecosystem)
    for entry in by_ecosystem.values():
        assert entry["directory"] == "/"
        assert entry["schedule"]["interval"] == "weekly"
        assert entry.get("groups"), f"{entry['package-ecosystem']} updates are not grouped"
    uv_groups = by_ecosystem["uv"]["groups"].values()
    assert any(set(group.get("update-types", [])) == {"minor", "patch"} for group in uv_groups)


def test_large_file_hook_exempts_only_bundled_fonts_and_icc() -> None:
    config = _load(REPO_ROOT / ".pre-commit-config.yaml")
    hooks = [hook for repo in config["repos"] for hook in repo["hooks"]]
    (large,) = [hook for hook in hooks if hook["id"] == "check-added-large-files"]
    assert large["args"] == ["--maxkb=500"]
    exclude = re.compile(large["exclude"])
    assert exclude.search("src/holiday_card/data/icc/GRACoL2013_CRPC6.icc")
    assert exclude.search("src/holiday_card/data/fonts/curated/CormorantGaramond-Regular.ttf")
    assert not exclude.search("src/holiday_card/data/templates/christmas/classic.yaml")
    assert not exclude.search("tests/visual/fixtures/reference_cards/png/big.png")


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_no_workflow_refreshes_the_openrouter_allowlist(path: Path) -> None:
    # The refresh script hits the live catalogue; it is dev-only (#148).
    assert "refresh_openrouter_models" not in path.read_text()
