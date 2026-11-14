"""Guardrails for the model-free triage label and its caller.

factory-triage-label.yml (ADR-0018) adds `needs-triage` to a new issue unless
it already carries a state label. Its guard names the state labels itself, so
these tests keep it in sync with the vocabulary in
docs/agents/triage-labels.md and pin the narrow permission set.
triage-label.yml is a thin caller.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "factory-triage-label.yml"
CALLER = REPO_ROOT / ".github" / "workflows" / "triage-label.yml"
LABELS_DOC = REPO_ROOT / "docs" / "agents" / "triage-labels.md"

# The five canonical state roles of the triage skill.
STATE_ROLES = ("needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _label_job() -> dict:
    jobs = _workflow()["jobs"]
    assert list(jobs) == ["label"], "triage-label workflow should have one job"
    return jobs["label"]


def _state_labels() -> dict[str, str]:
    """Map canonical state role to tracker label from the doc's table."""
    rows = re.findall(
        r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|",
        LABELS_DOC.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    mapping: dict[str, str] = {}
    for role, label in rows:  # the role table comes first; later tables do not override it
        mapping.setdefault(role, label)
    missing = [role for role in STATE_ROLES if role not in mapping]
    assert not missing, f"triage-labels.md lost state roles: {missing}"
    return {role: mapping[role] for role in STATE_ROLES}


def _caller() -> dict:
    return yaml.safe_load(CALLER.read_text(encoding="utf-8"))


def _caller_job() -> dict:
    jobs = _caller()["jobs"]
    assert list(jobs) == ["label"], "the caller should have one job"
    return jobs["label"]


def test_runs_only_on_opened_issues_with_issue_write_only():
    workflow = _workflow()
    # PyYAML reads the bare `on` key as boolean True.
    assert workflow[True] == {"workflow_call": None}, "no inputs"
    assert workflow["permissions"] == {}, "top-level permissions must stay empty"
    assert _label_job()["permissions"] == {"issues": "write"}
    caller = _caller()
    assert caller[True] == {"issues": {"types": ["opened"]}}
    assert caller["permissions"] == {}, "the caller's top-level permissions stay empty"


def test_caller_is_thin_and_grants_exactly_the_label_scope():
    job = _caller_job()
    uses = job["uses"]
    assert uses == "./.github/workflows/factory-triage-label.yml" or re.fullmatch(
        r"[\w.-]+/[\w.-]+/\.github/workflows/factory-triage-label\.yml@[0-9a-f]{40}", uses
    ), uses
    assert job["permissions"] == {"issues": "write"}
    # The guard lives in the called job only; the caller passes nothing.
    assert set(job) == {"uses", "permissions"}


def test_uses_no_actions_and_no_secrets():
    for path in (WORKFLOW, CALLER):
        assert "secrets" not in path.read_text(encoding="utf-8"), f"{path.name}: no secret"
    steps = _label_job()["steps"]
    assert all("uses" not in step for step in steps), "no action, not even checkout"


def test_guard_skips_every_state_label_from_the_vocabulary():
    guard = _label_job()["if"]
    for label in _state_labels().values():
        assert f"contains(github.event.issue.labels.*.name, '{label}')" in guard, (
            f"guard does not skip issues that already carry {label!r}"
        )


def test_adds_needs_triage_label_through_rest():
    run = "\n".join(step.get("run", "") for step in _label_job()["steps"])
    needs_triage = _state_labels()["needs-triage"]
    assert "gh api --method POST" in run and "/labels" in run, "label via the REST endpoint"
    assert f"labels[]={needs_triage}" in run
    assert "gh issue" not in run, "gh issue porcelain is GraphQL-backed"


def test_rechecks_fresh_labels_before_adding():
    run = "\n".join(step.get("run", "") for step in _label_job()["steps"])
    for label in _state_labels().values():
        assert f'"{label}"' in run, f"the fresh check does not look for {label!r}"
    assert run.index('repos/$GITHUB_REPOSITORY/issues/$NUMBER"') < run.index("--method POST")
