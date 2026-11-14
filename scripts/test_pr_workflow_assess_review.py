"""Structure tests for the assess and review jobs of the PR review workflow."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pr_workflow_testkit import (
    CLAUDE_PACKAGE,
    CONTEXT_ARTIFACT,
    MODEL_KEY,
    REVIEW_SKIP_CONDITION,
    downloaded_names,
    job_env,
    job_named,
    jobs_holding,
    load_workflow_text,
    needs_of,
    normalize,
    parse_workflow,
    run_containing,
    step_running,
    step_using,
    steps_of,
    uploaded_paths,
)


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return load_workflow_text()


@pytest.fixture(scope="module")
def workflow(workflow_text: str) -> dict[Any, Any]:
    return parse_workflow(workflow_text)


def test_assess_and_review_hold_no_write_scope(workflow: dict[Any, Any]) -> None:
    for name in ("assess", "review"):
        permissions = job_named(workflow, name).get("permissions") or {}
        writes = sorted(scope for scope, level in permissions.items() if level == "write")
        assert not writes, f"{name} must not be able to write; it holds write on {writes}"


def test_assess_holds_the_read_scopes_it_needs(workflow: dict[Any, Any]) -> None:
    permissions = job_named(workflow, "assess").get("permissions") or {}
    required = {"contents": "read", "pull-requests": "read", "issues": "read"}
    # Exactly these: check results are no gate (decision A), so no checks scope.
    assert permissions == required, (
        "assess reads the pull request, its comments and the base files; "
        f"it needs exactly {required} (found {permissions})"
    )


def test_assess_sets_up_python_312(workflow: dict[Any, Any]) -> None:
    step = step_using(job_named(workflow, "assess"), "actions/setup-python@")
    version = (step.get("with") or {}).get("python-version")
    assert str(version) == "3.12", f"assess must run on Python 3.12; found {version!r}"


def test_assess_fetches_the_context_with_a_token(workflow: dict[Any, Any]) -> None:
    job = job_named(workflow, "assess")
    command = run_containing(job, "scripts/pr_github.py")
    assert "--pr" in command, "the context fetch needs the pull request number"
    assert "--repo" in command, "the context fetch needs the repository"
    assert "--output context.json" in command, "the context must be written to context.json"
    assert '--pr "$PR"' in command, "the pull request number comes from env"
    assert "github.repository" in command, "the repository comes from the event, not from a ref"

    step = step_running(job, "scripts/pr_github.py")
    env = step.get("env") or {}
    assert env.get("GITHUB_TOKEN") == "${{ secrets.GITHUB_TOKEN }}", (
        "the context fetch reads the pull request through the workflow token"
    )
    assert env.get("PR") == "${{ github.event.pull_request.number || inputs.pr }}", (
        "a manual run passes the pull request number as an input"
    )


def test_assess_uploads_the_context(workflow: dict[Any, Any]) -> None:
    paths = uploaded_paths(job_named(workflow, "assess"))
    assert "context.json" in paths, f"assess must upload context.json; it uploads {sorted(paths)}"


def test_assess_classifies_the_risk(workflow: dict[Any, Any]) -> None:
    command = run_containing(job_named(workflow, "assess"), "scripts/pr_risk.py")
    assert "--context context.json" in command, "the risk policy reads the fetched context"
    assert "--output assessment.json" in command, "the assessment must be written to a file"


def test_assess_uploads_the_assessment(workflow: dict[Any, Any]) -> None:
    paths = uploaded_paths(job_named(workflow, "assess"))
    assert "assessment.json" in paths, (
        f"assess must upload assessment.json; it uploads {sorted(paths)}"
    )


def test_review_runs_after_the_assessment(workflow: dict[Any, Any]) -> None:
    assert needs_of(job_named(workflow, "review")) == {"assess"}, "review must need the assess job"


def test_review_holds_contents_read_for_the_base_checkout(workflow: dict[Any, Any]) -> None:
    permissions = job_named(workflow, "review").get("permissions") or {}
    assert permissions.get("contents") == "read", (
        f"review checks out the base to run the scripts; found {permissions}"
    )


def test_only_the_review_job_holds_the_model_key(
    workflow: dict[Any, Any], workflow_text: str
) -> None:
    holders = jobs_holding(workflow, MODEL_KEY)
    assert holders == {"review"}, (
        f"only review may hold {MODEL_KEY}; it is set in {sorted(holders) or 'no job'}"
    )
    assert job_env(workflow, "review")[MODEL_KEY] == "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"
    assert workflow_text.count("secrets.CLAUDE_CODE_OAUTH_TOKEN") == 1, (
        "the model secret must appear exactly once, in the review job"
    )


def test_review_model_comes_from_a_repository_variable(workflow: dict[Any, Any]) -> None:
    env = job_env(workflow, "review")
    assert env.get("PR_REVIEW_MODEL") == "${{ vars.PR_REVIEW_MODEL }}", (
        "the review model must be swappable without a code change"
    )


def test_review_skips_drafts_and_forks(workflow: dict[Any, Any]) -> None:
    condition = job_named(workflow, "review").get("if")
    assert condition is not None, "review needs a job-level condition to skip drafts and forks"
    assert normalize(condition) == REVIEW_SKIP_CONDITION, (
        "review must run only on a same-repository pull request, and on a pull request "
        f"event only when it is not a draft; found {normalize(condition)!r}"
    )


def test_assess_exposes_whether_the_head_is_in_this_repository(
    workflow: dict[Any, Any],
) -> None:
    job = job_named(workflow, "assess")
    outputs = job.get("outputs") or {}
    assert outputs.get("same_repo") == "${{ steps.origin.outputs.same_repo }}", (
        "assess must expose the same-repository check as the job output `same_repo`"
    )
    assert any(step.get("id") == "origin" for step in steps_of(job)), (
        "assess needs a step with id `origin` that derives `same_repo` from the context"
    )


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        ({"fork": False}, "true"),
        ({"fork": True}, "false"),
        ({}, "false"),
        ({"fork": "false"}, "false"),
    ],
)
def test_same_repo_output_follows_the_context_fork_flag(
    workflow: dict[Any, Any], tmp_path: Path, context: dict[str, Any], expected: str
) -> None:
    step = next(
        step for step in steps_of(job_named(workflow, "assess")) if step.get("id") == "origin"
    )
    (tmp_path / "context.json").write_text(json.dumps(context), encoding="utf-8")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")

    subprocess.run(  # noqa: S603
        ["bash", "-c", str(step["run"])],  # noqa: S607
        cwd=tmp_path,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
        check=True,
    )

    assert output.read_text(encoding="utf-8").splitlines() == [f"same_repo={expected}"]


def test_review_downloads_the_context(workflow: dict[Any, Any]) -> None:
    names = downloaded_names(job_named(workflow, "review"))
    assert CONTEXT_ARTIFACT in names, (
        f"review must download the context artifact; it downloads {sorted(names)}"
    )


def test_review_runs_the_review_cli(workflow: dict[Any, Any]) -> None:
    command = run_containing(job_named(workflow, "review"), "scripts/pr_review.py")
    assert "--context context.json" in command, "the review reads the downloaded context"
    assert "review.json" in command, "the review artifact must be written to review.json"


def test_review_installs_an_exact_claude_code_version(workflow: dict[Any, Any]) -> None:
    command = run_containing(job_named(workflow, "review"), CLAUDE_PACKAGE)
    assert re.search(re.escape(CLAUDE_PACKAGE) + r"@\d+\.\d+\.\d+(\s|$)", command), (
        f"the CLI that receives the token must be pinned to an exact version: {command!r}"
    )


def test_the_token_reaches_only_the_review_step(workflow: dict[Any, Any]) -> None:
    holders = [
        step.get("name")
        for step in steps_of(job_named(workflow, "review"))
        if MODEL_KEY in (step.get("env") or {})
    ]
    assert holders == ["Review the diff"], (
        f"only the review step may see {MODEL_KEY}, not the install step; found {holders}"
    )


def test_review_uploads_the_review(workflow: dict[Any, Any]) -> None:
    paths = uploaded_paths(job_named(workflow, "review"))
    assert "review.json" in paths, f"review must upload review.json; it uploads {sorted(paths)}"


def test_a_label_event_starts_no_assessment_and_no_review(workflow: dict[Any, Any]) -> None:
    # Review and publish need the assessment, so skipping it skips the model call.
    condition = normalize(job_named(workflow, "assess").get("if"))
    assert condition == "github.event.action != 'labeled'", (
        f"a label event must not re-run the review; found {condition!r}"
    )
