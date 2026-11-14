"""Structure tests for the publish job of the PR review workflow."""

from __future__ import annotations

import re
from typing import Any

import pytest
from pr_workflow_testkit import (
    ASSESSMENT_ARTIFACT,
    CONTEXT_ARTIFACT,
    MODEL_KEY,
    PUBLISH_SCOPES,
    REVIEW_ARTIFACT,
    download_step,
    downloaded_names,
    job_env,
    job_named,
    jobs_holding,
    jobs_of,
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


def test_publish_needs_the_earlier_jobs_and_the_hold(workflow: dict[Any, Any]) -> None:
    assert needs_of(job_named(workflow, "publish")) == {"assess", "review", "hold"}, (
        "publish must need the assessment and the review, and run after the hold so "
        "its auto-merge decision is the last write"
    )


def test_publish_runs_even_when_the_review_was_skipped(workflow: dict[Any, Any]) -> None:
    condition = normalize(job_named(workflow, "publish").get("if") or "")
    assert "always()" in condition, "publish must run even when review was skipped"
    assert "needs.assess.result == 'success'" in condition, (
        f"publish must require a successful assessment; found {condition!r}"
    )


def test_publish_has_the_scopes_the_write_path_needs(workflow: dict[Any, Any]) -> None:
    permissions = job_named(workflow, "publish").get("permissions")
    assert permissions == PUBLISH_SCOPES, (
        "publish writes labels, comments, reviewer requests, auto-merge "
        f"(contents: write) and the pr-review/verdict status (statuses: write); found {permissions}"
    )


def test_only_publish_may_write_a_commit_status(workflow: dict[Any, Any]) -> None:
    writers = {
        name
        for name, job in jobs_of(workflow).items()
        if "statuses" in (job.get("permissions") or {})
    }
    assert writers == {"publish"}, (
        "the verdict status comes from the publish job alone: an earlier stage that set "
        f"it could turn it green before a verdict exists; found {sorted(writers)}"
    )


def test_publish_links_the_verdict_status_to_its_run(workflow: dict[Any, Any]) -> None:
    env = job_env(workflow, "publish")
    assert normalize(env.get("RUN_URL")) == (
        "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
    ), "the status link must be this run's page, built from trusted context only"
    command = run_containing(job_named(workflow, "publish"), "scripts/pr_publish.py")
    assert command.count('--status-url "$RUN_URL"') == 2, (
        "the write and the dry-run branch must plan the same status"
    )


def test_publish_holds_no_model_key(workflow: dict[Any, Any]) -> None:
    assert MODEL_KEY not in job_env(workflow, "publish"), (
        "publish decides from artifacts; it must never hold the model credential"
    )


def test_publish_downloads_the_context_and_the_assessment(workflow: dict[Any, Any]) -> None:
    names = downloaded_names(job_named(workflow, "publish"))
    assert {CONTEXT_ARTIFACT, ASSESSMENT_ARTIFACT} <= names, (
        f"publish must download the context and the assessment; it downloads {sorted(names)}"
    )


def test_publish_downloads_the_review_artifact(workflow: dict[Any, Any]) -> None:
    names = downloaded_names(job_named(workflow, "publish"))
    assert REVIEW_ARTIFACT in names, (
        f"publish must download the review artifact; it downloads {sorted(names)}"
    )


def test_publish_tolerates_a_missing_review_artifact(workflow: dict[Any, Any]) -> None:
    step = download_step(job_named(workflow, "publish"), REVIEW_ARTIFACT)
    assert step.get("continue-on-error") is True, (
        "a skipped review job produces no artifact; downloading it must not fail publish"
    )


def test_publish_reconstructs_a_missing_review(workflow: dict[Any, Any]) -> None:
    command = run_containing(job_named(workflow, "publish"), "scripts/pr_review.py")
    assert "--context context.json" in command, "the reconstruction reads the downloaded context"
    assert "review.json" in command, "the reconstruction writes review.json"
    assert re.search(r"if \[ -[sf] review\.json \]", command), (
        "the reconstruction must run only when the review artifact is absent"
    )


def test_publish_prints_the_plan(workflow: dict[Any, Any]) -> None:
    command = run_containing(job_named(workflow, "publish"), "scripts/pr_publish.py")
    assert "--live" in command
    assert "--assessment assessment.json" in command
    assert "--review review.json" in command
    assert "plan.json" in command, "the plan must be written out and printed"


def test_publish_holds_the_workflow_token(workflow: dict[Any, Any]) -> None:
    env = job_env(workflow, "publish")
    assert env.get("GITHUB_TOKEN") == "${{ secrets.GITHUB_TOKEN }}", (
        "the write path needs the workflow token; it must not come from anywhere else"
    )


def test_publish_receives_the_pull_request_number(workflow: dict[Any, Any]) -> None:
    env = job_env(workflow, "publish")
    value = normalize(env.get("PR") or "")
    assert "github.event.pull_request.number" in value, (
        f"a pull request event must pass its own number; found {value!r}"
    )
    assert "inputs.pr" in value, f"a manual run must pass its input; found {value!r}"


def test_publish_write_flag_follows_the_dry_run_input(workflow: dict[Any, Any]) -> None:
    env = job_env(workflow, "publish")
    value = normalize(env.get("WRITE") or "")
    expected = "${{ github.event_name != 'workflow_dispatch' || inputs.dry_run == false }}"
    assert value == expected, (
        f"every event writes except a manual run that kept the dry-run default; found {value!r}"
    )


def test_only_publish_reads_the_auto_merge_variable(workflow: dict[Any, Any]) -> None:
    assert job_env(workflow, "publish").get("PR_AUTO_MERGE") == "${{ vars.PR_AUTO_MERGE }}", (
        "publish takes the auto-merge switch from the repository variable"
    )
    assert jobs_holding(workflow, "PR_AUTO_MERGE") == {"publish"}, (
        "only publish may enable auto-merge; the hold only disables"
    )


def test_publish_summarizes_the_decision_and_labels(workflow: dict[Any, Any]) -> None:
    command = run_containing(job_named(workflow, "publish"), "scripts/pr_publish.py")

    # The publisher renders the decision, the confidence and the applied labels
    # itself (pr_summary.py), in the write and in the dry-run branch.
    assert command.count('--summary "$GITHUB_STEP_SUMMARY"') == 2, (
        "both publisher calls must append their summary to the run page"
    )
    assert "python3 -" not in command, "no inline summary script: it would go untested"


def test_publish_renders_the_summary_before_a_failed_status_propagates(
    workflow: dict[Any, Any],
) -> None:
    command = run_containing(job_named(workflow, "publish"), "scripts/pr_publish.py")

    errexit_off = command.find("set +e")
    assert errexit_off != -1, "the publisher must run with errexit off to capture its status"
    status = re.search(r"^status=\$\?$", command, re.MULTILINE)
    assert status is not None, "the publish step must capture the publisher's exit status"
    errexit_on = re.search(r"^set -e$", command, re.MULTILINE)
    assert errexit_on is not None, "errexit must be restored after capturing the status"
    assert errexit_off < status.start() < errexit_on.start(), (
        "only the publisher runs without errexit; the status is captured right after it"
    )

    assert command.index("cat plan.json") > status.start(), (
        "the plan must be printed even when the publisher fails"
    )
    assert command.rstrip().endswith('exit "$status"'), (
        "the captured status must be the step's exit code, set after the summary"
    )
