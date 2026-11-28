"""Guardrails for the PR issue-link check: factory-pr-issue-links.yml and its caller."""

import re
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
CALLER = WORKFLOWS / "pr-issue-links.yml"
REUSABLE = WORKFLOWS / "factory-pr-issue-links.yml"
SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_caller_runs_on_pull_request_events_and_calls_the_reusable_workflow():
    caller = _load(CALLER)
    # PyYAML reads the bare `on` key as boolean True.
    types = ["opened", "edited", "synchronize", "reopened", "ready_for_review"]
    assert caller[True] == {"pull_request": {"types": types}}
    assert caller["permissions"] == {}
    (job,) = caller["jobs"].values()
    assert job["uses"] == f"./.github/workflows/{REUSABLE.name}"
    assert job["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert "secrets" not in job


def test_the_reusable_workflow_is_read_only_and_takes_no_secret():
    workflow = _load(REUSABLE)
    assert set(workflow[True]) == {"workflow_call"}
    assert "secrets" not in workflow[True]["workflow_call"]
    assert workflow["permissions"] == {}
    (job,) = workflow["jobs"].values()
    assert job["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert job["timeout-minutes"] == 5


def test_it_checks_out_nothing_and_runs_the_factory_script_with_event_values_in_env():
    (job,) = _load(REUSABLE)["jobs"].values()
    assert not any("actions/checkout@" in step.get("uses", "") for step in job["steps"])
    for step in job["steps"]:
        if "uses" in step:
            assert SHA_PIN.match(step["uses"]), step["uses"]
    check = job["steps"][-1]
    assert "${{" not in check["run"]
    assert check["env"]["PR_NUMBER"] == "${{ github.event.pull_request.number }}"
    assert check["env"]["PR_HEAD"] == "${{ github.event.pull_request.head.sha }}"
    assert "check_pr_issue_links.py" in check["run"]
