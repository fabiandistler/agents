"""Shared loaders and accessors for the PR review workflow structure tests.

The tests in test_pr_workflow*.py read .github/workflows/pr-review.yml through
these helpers, so each safety property can be asserted on its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "pr-review.yml"

REVIEW_EVENTS = ["opened", "synchronize", "reopened", "ready_for_review"]
# Adding a label starts a run too, but only the hold acts on it (do-not-merge).
LABEL_EVENT = "labeled"
JOB_NAMES = {"hold", "assess", "review", "publish"}

# The hold runs on a push and when do-not-merge is added, never on a manual run.
HOLD_CONDITION = (
    "github.event.action == 'synchronize' || "
    "(github.event.action == 'labeled' && github.event.label.name == 'do-not-merge')"
)
# Enabling and disabling auto-merge needs contents and pull-requests write;
# label changes go through the issues API.
AUTO_MERGE_SCOPES = {"contents": "write", "pull-requests": "write", "issues": "write"}
# Publish also sets the pr-review/verdict commit status; no other job may.
PUBLISH_SCOPES = {**AUTO_MERGE_SCOPES, "statuses": "write"}
PIPELINE_CLIS = {"pr_github.py", "pr_risk.py", "pr_review.py", "pr_publish.py"}
MODEL_KEY = "CLAUDE_CODE_OAUTH_TOKEN"
# The review step hands the token to this package, so its version stays exact.
CLAUDE_PACKAGE = "@anthropic-ai/claude-code"

CONTEXT_ARTIFACT = "pr-context"
ASSESSMENT_ARTIFACT = "pr-assessment"
REVIEW_ARTIFACT = "pr-review"

# The skip rule for draft and fork pull requests, whitespace-normalized.
# A manual run carries no pull request event, so the same-repository check comes
# from the fetched context through the assess output.
REVIEW_SKIP_CONDITION = (
    "needs.assess.outputs.same_repo == 'true' && "
    "(github.event_name == 'workflow_dispatch' || (github.event.pull_request.draft == false && "
    "github.event.pull_request.head.repo.full_name == github.repository))"
)


def normalize(expression: Any) -> str:
    return " ".join(str(expression).split())


def triggers_of(workflow: dict[Any, Any]) -> dict[Any, Any]:
    # YAML 1.1 reads the bare key `on` as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), "the workflow has no trigger block"
    return triggers


def jobs_of(workflow: dict[Any, Any]) -> dict[str, Any]:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict), "the workflow has no jobs block"
    return jobs


def job_named(workflow: dict[Any, Any], name: str) -> dict[str, Any]:
    jobs = jobs_of(workflow)
    assert name in jobs, f"the workflow has no job {name!r}; found {sorted(jobs)}"
    return jobs[name]


def steps_of(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps")
    assert isinstance(steps, list) and steps, "a job in the pipeline has no steps"
    return steps


def runs_of(job: dict[str, Any]) -> list[str]:
    return [str(step["run"]) for step in steps_of(job) if "run" in step]


def run_containing(job: dict[str, Any], needle: str) -> str:
    for command in runs_of(job):
        if needle in command:
            return command
    raise AssertionError(f"no run step contains {needle!r}; the job runs: {runs_of(job)}")


def step_running(job: dict[str, Any], needle: str) -> dict[str, Any]:
    for step in steps_of(job):
        if needle in str(step.get("run", "")):
            return step
    raise AssertionError(f"no step runs {needle!r}")


def step_using(job: dict[str, Any], needle: str) -> dict[str, Any]:
    for step in steps_of(job):
        if needle in str(step.get("uses", "")):
            return step
    raise AssertionError(f"no step uses {needle!r}")


def job_env(workflow: dict[Any, Any], name: str) -> dict[str, Any]:
    """Every environment entry the job sees, from the workflow, job and steps."""
    collected: dict[str, Any] = dict(workflow.get("env") or {})
    job = job_named(workflow, name)
    collected.update(job.get("env") or {})
    for step in steps_of(job):
        collected.update(step.get("env") or {})
    return collected


def jobs_holding(workflow: dict[Any, Any], key: str) -> set[str]:
    return {name for name in jobs_of(workflow) if key in job_env(workflow, name)}


def upload_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for step in steps_of(job) if "actions/upload-artifact@" in str(step.get("uses"))]


def uploaded_names(job: dict[str, Any]) -> set[str]:
    return {str((step.get("with") or {}).get("name")) for step in upload_steps(job)}


def uploaded_paths(job: dict[str, Any]) -> set[str]:
    return {str((step.get("with") or {}).get("path")) for step in upload_steps(job)}


def download_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for step in steps_of(job) if "actions/download-artifact@" in str(step.get("uses"))]


def downloaded_names(job: dict[str, Any]) -> set[str]:
    return {str((step.get("with") or {}).get("name")) for step in download_steps(job)}


def download_step(job: dict[str, Any], name: str) -> dict[str, Any]:
    for step in download_steps(job):
        if (step.get("with") or {}).get("name") == name:
            return step
    raise AssertionError(f"no step downloads the artifact {name!r}")


def needs_of(job: dict[str, Any]) -> set[str]:
    needs = job.get("needs")
    if isinstance(needs, str):
        return {needs}
    return set(needs or [])


def load_workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def parse_workflow(workflow_text: str) -> dict[Any, Any]:
    parsed = yaml.safe_load(workflow_text)
    assert isinstance(parsed, dict), f"{WORKFLOW_PATH} is not a YAML mapping"
    return parsed
