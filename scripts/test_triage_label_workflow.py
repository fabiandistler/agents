"""Guardrails for the model-free triage-label workflow.

The workflow adds `needs-triage` to a new issue unless it already carries a
state label. Its guard names the state labels itself, so these tests keep it
in sync with the vocabulary in docs/agents/triage-labels.md and pin the
narrow permission set.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "triage-label.yml"
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
    mapping = dict(rows)
    missing = [role for role in STATE_ROLES if role not in mapping]
    assert not missing, f"triage-labels.md lost state roles: {missing}"
    return {role: mapping[role] for role in STATE_ROLES}


def test_runs_only_on_opened_issues_with_issue_write_only():
    workflow = _workflow()
    # PyYAML reads the bare `on` key as boolean True.
    assert workflow[True] == {"issues": {"types": ["opened"]}}
    assert workflow["permissions"] == {}, "top-level permissions must stay empty"
    assert _label_job()["permissions"] == {"issues": "write"}


def test_uses_no_actions_and_no_secrets():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text, "the workflow needs no secret"
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
