"""Structure tests for this repository's PR review caller (.github/workflows/pr-review.yml).

The caller keeps the file name, the triggers and the permission cap that the
event policy (docs/agents/pr-review-event-policy.md), the rework task and the
ruleset's `pr-review/verdict` rely on; the jobs live in factory-pr-review.yml
(ADR-0018). Other repositories copy this shape with a SHA-pinned `uses:`.
"""

from __future__ import annotations

from typing import Any

import pytest
from pr_workflow_testkit import (
    LABEL_EVENT,
    MODEL_KEY,
    REVIEW_EVENTS,
    jobs_of,
    load_caller_text,
    load_workflow_text,
    parse_workflow,
    triggers_of,
)

CALLED = "./.github/workflows/factory-pr-review.yml"
LEVELS = {"none": 0, "read": 1, "write": 2}


@pytest.fixture(scope="module")
def caller_text() -> str:
    return load_caller_text()


@pytest.fixture(scope="module")
def caller(caller_text: str) -> dict[Any, Any]:
    return parse_workflow(caller_text)


@pytest.fixture(scope="module")
def called() -> dict[Any, Any]:
    return parse_workflow(load_workflow_text())


def calling_job(caller: dict[Any, Any]) -> dict[str, Any]:
    jobs = jobs_of(caller)
    assert list(jobs) == ["pr-review"], f"the caller has one job, pr-review; found {list(jobs)}"
    return jobs["pr-review"]


def test_pull_request_target_carries_the_review_events(caller: dict[Any, Any]) -> None:
    target = triggers_of(caller).get("pull_request_target")
    assert isinstance(target, dict), "the caller must trigger on pull_request_target"
    expected = [*REVIEW_EVENTS, LABEL_EVENT]
    assert sorted(target.get("types") or []) == sorted(expected)


def test_the_trigger_carries_the_one_approved_zizmor_ignore(caller_text: str) -> None:
    assert "  pull_request_target: # zizmor: ignore[dangerous-triggers]\n" in caller_text
    assert caller_text.count("zizmor: ignore") == 1


def test_the_caller_does_not_trigger_on_pull_request(caller: dict[Any, Any]) -> None:
    assert "pull_request" not in triggers_of(caller), (
        "pull_request runs the workflow from the head commit; only pull_request_target is allowed"
    )


def test_workflow_dispatch_takes_a_pull_request_and_a_dry_run_flag(
    caller: dict[Any, Any],
) -> None:
    inputs = (triggers_of(caller).get("workflow_dispatch") or {}).get("inputs") or {}
    assert set(inputs) == {"pr", "dry_run"}
    assert inputs["pr"].get("required") is True
    assert inputs["pr"].get("type") in {"string", "number"}
    assert inputs["dry_run"].get("type") == "boolean"
    assert inputs["dry_run"].get("default") is True, "a manual run must default to a dry run"


def test_default_permissions_are_empty(caller: dict[Any, Any]) -> None:
    assert caller.get("permissions") == {}


def test_the_caller_defines_no_concurrency_group(caller: dict[Any, Any]) -> None:
    # The called workflow holds the only group; a group of the same name in the
    # caller would cancel the caller itself.
    assert "concurrency" not in caller
    assert "concurrency" not in calling_job(caller)


def test_the_caller_calls_the_local_reusable_pipeline(caller: dict[Any, Any]) -> None:
    job = calling_job(caller)
    assert job.get("uses") == CALLED
    assert "steps" not in job and "if" not in job


def test_the_cap_is_the_union_of_the_called_jobs_scopes(
    caller: dict[Any, Any], called: dict[Any, Any]
) -> None:
    union: dict[str, str] = {}
    for job in jobs_of(called).values():
        for scope, level in (job.get("permissions") or {}).items():
            if LEVELS[level] > LEVELS[union.get(scope, "none")]:
                union[scope] = level
    assert union == {
        "contents": "write",
        "pull-requests": "write",
        "issues": "write",
        "statuses": "write",
    }
    assert calling_job(caller).get("permissions") == union, (
        "the calling job caps the called jobs: less breaks one, more grants nothing used"
    )


def test_the_model_token_is_passed_by_name(caller: dict[Any, Any], caller_text: str) -> None:
    job = calling_job(caller)
    assert job.get("secrets") == {MODEL_KEY: f"${{{{ secrets.{MODEL_KEY} }}}}"}
    assert "inherit" not in caller_text, "secrets: inherit is documented only within an org"


def test_every_repository_specific_input_stays_at_its_default(caller: dict[Any, Any]) -> None:
    passed = calling_job(caller).get("with") or {}
    assert passed == {
        "pr": "${{ inputs.pr || '' }}",
        "dry_run": "${{ inputs.dry_run != false }}",
    }, "this repository passes only the dispatch inputs; the rest keeps today's behaviour"


def test_every_passed_input_is_declared(caller: dict[Any, Any], called: dict[Any, Any]) -> None:
    declared = set(triggers_of(called)["workflow_call"].get("inputs") or {})
    assert set(calling_job(caller).get("with") or {}) <= declared
