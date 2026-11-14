"""Guardrails for fix-task.yml: the model-free Fix task (ADR-0016)."""

import re
from pathlib import Path

import factory_failure_policy
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "fix-task.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _job() -> dict:
    jobs = _workflow()["jobs"]
    assert len(jobs) == 1, "the Fix task is one job"
    return next(iter(jobs.values()))


def test_permissions_are_empty_by_default_and_three_scopes_in_the_job():
    assert _workflow()["permissions"] == {}
    assert _job()["permissions"] == {"issues": "write", "actions": "read", "checks": "read"}


def test_concurrency_is_per_watched_workflow_and_never_cancels():
    concurrency = _workflow()["concurrency"]
    assert "github.event.workflow_run.name" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is False


def test_it_watches_exactly_the_policy_workflows_and_not_itself():
    on = _workflow()[True]  # YAML 1.1 reads the `on` key as True
    watched = on["workflow_run"]["workflows"]
    names = {
        yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))["name"]
        for path in factory_failure_policy.WATCHED_WORKFLOWS
    }
    assert set(watched) == names
    assert _workflow()["name"] not in watched and "CI" not in watched
    assert on["workflow_run"]["types"] == ["completed"]
    assert on["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True


def test_no_model_and_no_app_token():
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("claude", "anthropic", "CLAUDE_CODE_OAUTH_TOKEN", "id-token", "app-token"):
        assert forbidden.lower() not in text.lower().replace("claude-code", "")
    secrets = set(re.findall(r"secrets\.([A-Z_]+)", text))
    assert secrets == {"GITHUB_TOKEN"}


def test_the_implementer_run_name_matches_the_policy():
    run_name = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/implementer.yml").read_text(encoding="utf-8")
    )["run-name"]
    assert run_name == "implementer: issue #${{ github.event.issue.number || inputs.issue }}"
    assert factory_failure_policy.IMPLEMENTER_RUN_NAME.fullmatch("implementer: issue #783")
