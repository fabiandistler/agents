"""Structure tests for the hold job of the PR review workflow.

GitHub keeps auto-merge on when someone with write access pushes. The hold
disables the bot's auto-merge on every push, before the new head is reviewed,
and any auto-merge as soon as do-not-merge is added. It needs no review, so a
label event never calls the model.
"""

from __future__ import annotations

from typing import Any

import pytest
from pr_workflow_testkit import (
    AUTO_MERGE_SCOPES,
    HOLD_CONDITION,
    MODEL_KEY,
    job_env,
    job_named,
    load_workflow_text,
    needs_of,
    normalize,
    parse_workflow,
    run_containing,
)


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return load_workflow_text()


@pytest.fixture(scope="module")
def workflow(workflow_text: str) -> dict[Any, Any]:
    return parse_workflow(workflow_text)


def test_the_hold_runs_on_a_push_and_on_do_not_merge_only(workflow: dict[Any, Any]) -> None:
    assert normalize(job_named(workflow, "hold").get("if")) == HOLD_CONDITION


def test_the_hold_waits_for_nothing(workflow: dict[Any, Any]) -> None:
    assert needs_of(job_named(workflow, "hold")) == set(), (
        "the hold must act at once, before the review of the new head"
    )


def test_the_hold_has_the_scopes_to_disable_and_unlabel(workflow: dict[Any, Any]) -> None:
    assert job_named(workflow, "hold").get("permissions") == AUTO_MERGE_SCOPES


def test_the_hold_runs_the_review_free_publisher(workflow: dict[Any, Any]) -> None:
    command = run_containing(job_named(workflow, "hold"), "scripts/pr_publish.py")
    command = normalize(command.replace("\\\n", " "))
    assert command == (
        'python3 "$RUNNER_TEMP/factory/scripts/pr_publish.py" --hold --live '
        '--repo "${{ github.repository }}" '
        '--pr "$PR" --write'
    )


def test_the_hold_holds_the_workflow_token_and_nothing_else(workflow: dict[Any, Any]) -> None:
    env = job_env(workflow, "hold")
    assert env.get("GITHUB_TOKEN") == "${{ secrets.GITHUB_TOKEN }}"
    assert normalize(env.get("PR")) == "${{ github.event.pull_request.number }}"
    assert MODEL_KEY not in env, "the hold decides without a review; it never holds the model key"
    assert "PR_AUTO_MERGE" not in env, "the hold never enables auto-merge"


def test_the_hold_honours_the_skip_prefixes(workflow: dict[Any, Any]) -> None:
    env = job_env(workflow, "hold")
    assert env.get("PR_SKIP_HEAD_PREFIXES") == "${{ inputs.skip_head_prefixes }}"
