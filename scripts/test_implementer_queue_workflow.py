"""Guardrails for the implementer queue's workflows (#801).

implementer-queue.yml calls the reusable factory-implementer-queue.yml, whose
one model-free job runs scripts/implementer_queue.py. The tests pin an empty
top-level permission set, `actions: write` on the starter job only, SHA-pinned actions,
the agreed triggers, and a dispatch target that is the implementer.
"""

from __future__ import annotations

import implementer_setup
from agent_run_workflow_testkit import (
    EXPRESSION,
    FACTORY_IMPLEMENTER,
    IMPLEMENTER,
    WORKFLOWS,
    single_job,
    workflow,
)

QUEUE = WORKFLOWS / "implementer-queue.yml"
FACTORY_QUEUE = WORKFLOWS / "factory-implementer-queue.yml"
QUEUE_WORKFLOWS = (QUEUE, FACTORY_QUEUE)

STARTER_SCOPES = {
    "actions": "write",
    "contents": "read",
    "issues": "read",
    "pull-requests": "read",
}


def starter_step(job: dict) -> dict:
    steps = [step for step in job["steps"] if "implementer_queue.py" in step.get("run", "")]
    assert len(steps) == 1, "exactly one step runs the queue script"
    return steps[0]


def test_permissions_are_empty_by_default_and_only_the_starter_job_writes_actions():
    for path in QUEUE_WORKFLOWS:
        document = workflow(path)
        assert document["permissions"] == {}, f"{path.name}: top-level permissions must stay empty"
        assert single_job(path)["permissions"] == STARTER_SCOPES, path.name


def test_the_implementer_keeps_actions_read_only():
    assert single_job(IMPLEMENTER)["permissions"]["actions"] == "read"


def test_every_action_is_sha_pinned_and_no_model_runs():
    for path in QUEUE_WORKFLOWS:
        for job in workflow(path)["jobs"].values():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                assert "claude-code-action" not in uses, "the queue is model-free"
                if uses:
                    ref = uses.split("@", 1)[1]
                    assert len(ref) == 40, f"{path.name}: {uses} is not pinned to a commit SHA"
                    assert all(char in "0123456789abcdef" for char in ref)


def test_the_queue_starts_when_capacity_may_have_freed_up():
    triggers = workflow(QUEUE)[True]  # PyYAML reads the bare `on` key as boolean True.
    assert set(triggers) == {"workflow_run", "issues", "schedule", "workflow_dispatch"}
    assert triggers["workflow_run"] == {
        "workflows": [workflow(IMPLEMENTER)["name"]],
        "types": ["completed"],
    }
    assert triggers["issues"] == {"types": ["closed"]}, "a closed issue may free a blocked one"
    assert triggers["schedule"], "the fallback when a workflow_run chain stops"
    assert triggers["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True
    assert set(workflow(FACTORY_QUEUE)[True]) == {"workflow_call"}


def test_a_skipped_implementer_run_starts_no_queue_job():
    guard = single_job(QUEUE)["if"]
    assert "github.event.workflow_run.conclusion != 'skipped'" in guard


def test_the_queue_dispatches_the_implementer_which_accepts_a_dispatch():
    assert single_job(QUEUE)["with"]["workflow_file"] == IMPLEMENTER.name
    assert IMPLEMENTER.name == implementer_setup.IMPLEMENTER_WORKFLOW
    inputs = workflow(IMPLEMENTER)[True]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"issue"}, "the queue sends only inputs.issue"
    assert single_job(IMPLEMENTER)["uses"] == f"./.github/workflows/{FACTORY_IMPLEMENTER.name}"
    guard = single_job(FACTORY_IMPLEMENTER)["if"]
    assert "github.event_name == 'workflow_dispatch'" in guard, "a bot's dispatch must run"


def test_starters_never_run_side_by_side():
    concurrency = single_job(FACTORY_QUEUE)["concurrency"]
    assert concurrency == {"group": "implementer-queue", "cancel-in-progress": False}


def test_the_starter_passes_values_through_env_and_uses_the_job_token():
    step = starter_step(single_job(FACTORY_QUEUE))
    assert not EXPRESSION.search(step["run"]), "inputs reach the shell through env only"
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"  # noqa: S105 -- an expression.
    assert "--job-name implement" in step["run"]
    assert "--workflow-file" in step["run"]
