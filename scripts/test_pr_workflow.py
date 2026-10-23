"""Structure tests for the PR review workflow (.github/workflows/pr-review.yml).

The workflow is the trust boundary of the pipeline: it decides which credential
each stage holds and guarantees that the pull request head is never checked out
or executed. Each safety property is asserted on its own, so removing one names
itself in the failing test instead of hiding behind a generic YAML comparison.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "pr-review.yml"

REVIEW_EVENTS = ["opened", "synchronize", "reopened", "ready_for_review"]
JOB_NAMES = {"assess", "review", "publish"}
PIPELINE_CLIS = {"pr_github.py", "pr_risk.py", "pr_review.py", "pr_publish.py"}
MODEL_KEY = "OPENCODE_API_KEY"

CONTEXT_ARTIFACT = "pr-context"
ASSESSMENT_ARTIFACT = "pr-assessment"
REVIEW_ARTIFACT = "pr-review"

# The skip rule for draft and fork pull requests, whitespace-normalized.
REVIEW_SKIP_CONDITION = (
    "github.event_name == 'workflow_dispatch' || (github.event.pull_request.draft == false && "
    "github.event.pull_request.head.repo.full_name == github.repository)"
)


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow(workflow_text: str) -> dict[Any, Any]:
    parsed = yaml.safe_load(workflow_text)
    assert isinstance(parsed, dict), f"{WORKFLOW_PATH} is not a YAML mapping"
    return parsed


def _normalize(expression: Any) -> str:
    return " ".join(str(expression).split())


def _triggers(workflow: dict[Any, Any]) -> dict[Any, Any]:
    # YAML 1.1 reads the bare key `on` as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), "the workflow has no trigger block"
    return triggers


def _jobs(workflow: dict[Any, Any]) -> dict[str, Any]:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict), "the workflow has no jobs block"
    return jobs


def _job(workflow: dict[Any, Any], name: str) -> dict[str, Any]:
    jobs = _jobs(workflow)
    assert name in jobs, f"the workflow has no job {name!r}; found {sorted(jobs)}"
    return jobs[name]


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps")
    assert isinstance(steps, list) and steps, "a job in the pipeline has no steps"
    return steps


def _runs(job: dict[str, Any]) -> list[str]:
    return [str(step["run"]) for step in _steps(job) if "run" in step]


def _run_containing(job: dict[str, Any], needle: str) -> str:
    for command in _runs(job):
        if needle in command:
            return command
    raise AssertionError(f"no run step contains {needle!r}; the job runs: {_runs(job)}")


def _step_running(job: dict[str, Any], needle: str) -> dict[str, Any]:
    for step in _steps(job):
        if needle in str(step.get("run", "")):
            return step
    raise AssertionError(f"no step runs {needle!r}")


def _step_using(job: dict[str, Any], needle: str) -> dict[str, Any]:
    for step in _steps(job):
        if needle in str(step.get("uses", "")):
            return step
    raise AssertionError(f"no step uses {needle!r}")


def _env(workflow: dict[Any, Any], name: str) -> dict[str, Any]:
    """Every environment entry the job sees, from the workflow, job and steps."""
    collected: dict[str, Any] = dict(workflow.get("env") or {})
    job = _job(workflow, name)
    collected.update(job.get("env") or {})
    for step in _steps(job):
        collected.update(step.get("env") or {})
    return collected


def _jobs_holding(workflow: dict[Any, Any], key: str) -> set[str]:
    return {name for name in _jobs(workflow) if key in _env(workflow, name)}


def _upload_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for step in _steps(job) if "actions/upload-artifact@" in str(step.get("uses"))]


def _uploaded_names(job: dict[str, Any]) -> set[str]:
    return {str((step.get("with") or {}).get("name")) for step in _upload_steps(job)}


def _uploaded_paths(job: dict[str, Any]) -> set[str]:
    return {str((step.get("with") or {}).get("path")) for step in _upload_steps(job)}


def _download_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for step in _steps(job) if "actions/download-artifact@" in str(step.get("uses"))]


def _downloaded_names(job: dict[str, Any]) -> set[str]:
    return {str((step.get("with") or {}).get("name")) for step in _download_steps(job)}


def _download_step(job: dict[str, Any], name: str) -> dict[str, Any]:
    for step in _download_steps(job):
        if (step.get("with") or {}).get("name") == name:
            return step
    raise AssertionError(f"no step downloads the artifact {name!r}")


def _needs(job: dict[str, Any]) -> set[str]:
    needs = job.get("needs")
    if isinstance(needs, str):
        return {needs}
    return set(needs or [])


def test_pull_request_target_carries_the_review_events(workflow: dict[Any, Any]) -> None:
    target = _triggers(workflow).get("pull_request_target")
    assert isinstance(target, dict), "the workflow must trigger on pull_request_target"
    declared = target.get("types")
    assert sorted(declared or []) == sorted(REVIEW_EVENTS), (
        f"pull_request_target must list exactly {REVIEW_EVENTS}; found {declared}"
    )


def test_workflow_does_not_trigger_on_pull_request(workflow: dict[Any, Any]) -> None:
    assert "pull_request" not in _triggers(workflow), (
        "pull_request runs the workflow from the head commit; only pull_request_target is allowed"
    )


def test_workflow_dispatch_takes_a_pull_request_and_a_dry_run_flag(
    workflow: dict[Any, Any],
) -> None:
    dispatch = _triggers(workflow).get("workflow_dispatch")
    assert isinstance(dispatch, dict), "the workflow needs a manual workflow_dispatch trigger"
    inputs = dispatch.get("inputs") or {}

    pr = inputs.get("pr") or {}
    assert pr.get("required") is True, "workflow_dispatch input 'pr' must be required"
    assert pr.get("type") in {"string", "number"}, (
        f"workflow_dispatch input 'pr' must be a string or a number; found {pr.get('type')!r}"
    )

    dry_run = inputs.get("dry_run") or {}
    assert dry_run.get("type") == "boolean", (
        f"workflow_dispatch input 'dry_run' must be a boolean; found {dry_run.get('type')!r}"
    )
    assert dry_run.get("default") is True, "a manual run must default to a dry run"


def test_default_permissions_are_empty(workflow: dict[Any, Any]) -> None:
    assert "permissions" in workflow, "the workflow must declare top-level permissions explicitly"
    assert workflow["permissions"] == {}, (
        "top-level permissions must be empty; every job opts in to its own scope"
    )


def test_the_pipeline_has_exactly_three_jobs(workflow: dict[Any, Any]) -> None:
    assert set(_jobs(workflow)) == JOB_NAMES, (
        f"the pipeline is {sorted(JOB_NAMES)}; found {sorted(_jobs(workflow))}"
    )


def test_assess_and_review_hold_no_write_scope(workflow: dict[Any, Any]) -> None:
    for name in ("assess", "review"):
        permissions = _job(workflow, name).get("permissions") or {}
        writes = sorted(scope for scope, level in permissions.items() if level == "write")
        assert not writes, f"{name} must not be able to write; it holds write on {writes}"


def test_assess_holds_the_read_scopes_it_needs(workflow: dict[Any, Any]) -> None:
    permissions = _job(workflow, "assess").get("permissions") or {}
    required = {"contents": "read", "pull-requests": "read", "issues": "read", "checks": "read"}
    missing = sorted(
        f"{scope}: {level}" for scope, level in required.items() if permissions.get(scope) != level
    )
    assert not missing, (
        "assess reads the pull request, its comments, its check runs and the base files; "
        f"missing {missing} (found {permissions})"
    )


def test_assess_checks_out_the_base_without_a_ref(workflow: dict[Any, Any]) -> None:
    step = _step_using(_job(workflow, "assess"), "actions/checkout@")
    assert "ref" not in (step.get("with") or {}), (
        "the assess checkout must not select a ref: the workflow runs from the base commit"
    )


def test_assess_sets_up_python_312(workflow: dict[Any, Any]) -> None:
    step = _step_using(_job(workflow, "assess"), "actions/setup-python@")
    version = (step.get("with") or {}).get("python-version")
    assert str(version) == "3.12", f"assess must run on Python 3.12; found {version!r}"


def test_assess_fetches_the_context_with_a_token(workflow: dict[Any, Any]) -> None:
    job = _job(workflow, "assess")
    command = _run_containing(job, "scripts/pr_github.py")
    assert "--pr" in command, "the context fetch needs the pull request number"
    assert "--repo" in command, "the context fetch needs the repository"
    assert "--output context.json" in command, "the context must be written to context.json"
    assert "inputs.pr" in command, "a manual run passes the pull request number as an input"
    assert "github.repository" in command, "the repository comes from the event, not from a ref"

    step = _step_running(job, "scripts/pr_github.py")
    assert (step.get("env") or {}).get("GITHUB_TOKEN") == "${{ secrets.GITHUB_TOKEN }}", (
        "the context fetch reads the pull request through the workflow token"
    )


def test_assess_uploads_the_context(workflow: dict[Any, Any]) -> None:
    paths = _uploaded_paths(_job(workflow, "assess"))
    assert "context.json" in paths, f"assess must upload context.json; it uploads {sorted(paths)}"


def test_assess_classifies_the_risk(workflow: dict[Any, Any]) -> None:
    command = _run_containing(_job(workflow, "assess"), "scripts/pr_risk.py")
    assert "--context context.json" in command, "the risk policy reads the fetched context"
    assert "--output assessment.json" in command, "the assessment must be written to a file"


def test_assess_uploads_the_assessment(workflow: dict[Any, Any]) -> None:
    paths = _uploaded_paths(_job(workflow, "assess"))
    assert "assessment.json" in paths, (
        f"assess must upload assessment.json; it uploads {sorted(paths)}"
    )


def test_review_runs_after_the_assessment(workflow: dict[Any, Any]) -> None:
    assert _needs(_job(workflow, "review")) == {"assess"}, "review must need the assess job"


def test_review_holds_contents_read_for_the_base_checkout(workflow: dict[Any, Any]) -> None:
    permissions = _job(workflow, "review").get("permissions") or {}
    assert permissions.get("contents") == "read", (
        f"review checks out the base to run the scripts; found {permissions}"
    )


def test_only_the_review_job_holds_the_model_key(
    workflow: dict[Any, Any], workflow_text: str
) -> None:
    holders = _jobs_holding(workflow, MODEL_KEY)
    assert holders == {"review"}, (
        f"only review may hold {MODEL_KEY}; it is set in {sorted(holders) or 'no job'}"
    )
    assert _env(workflow, "review")[MODEL_KEY] == "${{ secrets.OPENCODE_API_KEY }}"
    assert workflow_text.count("secrets.OPENCODE_API_KEY") == 1, (
        "the model secret must appear exactly once, in the review job"
    )


def test_review_model_comes_from_a_repository_variable(workflow: dict[Any, Any]) -> None:
    env = _env(workflow, "review")
    assert env.get("PR_REVIEW_MODEL") == "${{ vars.PR_REVIEW_MODEL }}", (
        "the review model must be swappable without a code change"
    )


def test_review_skips_drafts_and_forks(workflow: dict[Any, Any]) -> None:
    condition = _job(workflow, "review").get("if")
    assert condition is not None, "review needs a job-level condition to skip drafts and forks"
    assert _normalize(condition) == REVIEW_SKIP_CONDITION, (
        "review must run on manual dispatch and only on a non-draft, same-repository pull "
        f"request; found {_normalize(condition)!r}"
    )


def test_review_downloads_the_context(workflow: dict[Any, Any]) -> None:
    names = _downloaded_names(_job(workflow, "review"))
    assert CONTEXT_ARTIFACT in names, (
        f"review must download the context artifact; it downloads {sorted(names)}"
    )


def test_review_runs_the_review_cli(workflow: dict[Any, Any]) -> None:
    command = _run_containing(_job(workflow, "review"), "scripts/pr_review.py")
    assert "--context context.json" in command, "the review reads the downloaded context"
    assert "review.json" in command, "the review artifact must be written to review.json"


def test_review_uploads_the_review(workflow: dict[Any, Any]) -> None:
    paths = _uploaded_paths(_job(workflow, "review"))
    assert "review.json" in paths, f"review must upload review.json; it uploads {sorted(paths)}"


def test_publish_needs_both_earlier_jobs(workflow: dict[Any, Any]) -> None:
    assert _needs(_job(workflow, "publish")) == {"assess", "review"}, (
        "publish must need the assessment and the review"
    )


def test_publish_runs_even_when_the_review_was_skipped(workflow: dict[Any, Any]) -> None:
    condition = _normalize(_job(workflow, "publish").get("if") or "")
    assert "always()" in condition, "publish must run even when review was skipped"
    assert "needs.assess.result == 'success'" in condition, (
        f"publish must require a successful assessment; found {condition!r}"
    )


def test_publish_has_write_permissions_only(workflow: dict[Any, Any]) -> None:
    permissions = _job(workflow, "publish").get("permissions")
    assert permissions == {"pull-requests": "write", "issues": "write"}, (
        f"publish must hold pull-requests and issues write and nothing else; found {permissions}"
    )
    assert "contents" not in permissions, (
        "publish decides from artifacts; it must not read repository contents"
    )


def test_publish_holds_no_model_key(workflow: dict[Any, Any]) -> None:
    assert MODEL_KEY not in _env(workflow, "publish"), (
        "publish decides from artifacts; it must never hold the model credential"
    )


def test_publish_downloads_the_context_and_the_assessment(workflow: dict[Any, Any]) -> None:
    names = _downloaded_names(_job(workflow, "publish"))
    assert {CONTEXT_ARTIFACT, ASSESSMENT_ARTIFACT} <= names, (
        f"publish must download the context and the assessment; it downloads {sorted(names)}"
    )


def test_publish_downloads_the_review_artifact(workflow: dict[Any, Any]) -> None:
    names = _downloaded_names(_job(workflow, "publish"))
    assert REVIEW_ARTIFACT in names, (
        f"publish must download the review artifact; it downloads {sorted(names)}"
    )


def test_publish_tolerates_a_missing_review_artifact(workflow: dict[Any, Any]) -> None:
    step = _download_step(_job(workflow, "publish"), REVIEW_ARTIFACT)
    assert step.get("continue-on-error") is True, (
        "a skipped review job produces no artifact; downloading it must not fail publish"
    )


def test_publish_reconstructs_a_missing_review(workflow: dict[Any, Any]) -> None:
    command = _run_containing(_job(workflow, "publish"), "scripts/pr_review.py")
    assert "--context context.json" in command, "the reconstruction reads the downloaded context"
    assert "review.json" in command, "the reconstruction writes review.json"
    assert re.search(r"if \[ -[sf] review\.json \]", command), (
        "the reconstruction must run only when the review artifact is absent"
    )


def test_publish_prints_the_plan(workflow: dict[Any, Any]) -> None:
    command = _run_containing(_job(workflow, "publish"), "scripts/pr_publish.py")
    assert "--context context.json" in command
    assert "--assessment assessment.json" in command
    assert "--review review.json" in command
    assert "plan.json" in command, "the plan must be written out and printed"


def test_publish_appends_the_plan_to_the_step_summary(workflow: dict[Any, Any]) -> None:
    command = _run_containing(_job(workflow, "publish"), "scripts/pr_publish.py")
    assert "GITHUB_STEP_SUMMARY" in command, "the plan must be readable on the run summary"


def test_concurrency_is_keyed_by_pull_request(workflow: dict[Any, Any]) -> None:
    concurrency = workflow.get("concurrency")
    assert isinstance(concurrency, dict), "the workflow needs a concurrency group"
    group = _normalize(concurrency.get("group") or "")
    assert group.startswith("pr-review-"), f"the group must be namespaced; found {group!r}"
    assert "github.event.pull_request.number" in group, "the group must key on the pull request"
    assert "inputs.pr" in group, "a manual run must key on its input as well"
    assert concurrency.get("cancel-in-progress") is True, "a superseded run must be cancelled"


def test_every_run_step_calls_a_cli_that_exists(workflow: dict[Any, Any]) -> None:
    referenced: set[str] = set()
    for job in _jobs(workflow).values():
        for command in _runs(job):
            referenced.update(re.findall(r"scripts/[\w./-]+\.py", command))

    assert referenced, "the workflow runs no repository CLI"
    missing = sorted(path for path in referenced if not (REPO_ROOT / path).is_file())
    assert not missing, f"run steps reference CLIs that do not exist: {missing}"

    unexpected = sorted({Path(path).name for path in referenced} - PIPELINE_CLIS)
    assert not unexpected, f"the pipeline runs a CLI outside its three stages: {unexpected}"


def test_every_uploaded_artifact_is_downloaded_by_publish(workflow: dict[Any, Any]) -> None:
    uploaded: set[str] = set()
    for name in _jobs(workflow):
        uploaded.update(_uploaded_names(_job(workflow, name)))
    downloaded = _downloaded_names(_job(workflow, "publish"))

    assert uploaded, "the pipeline hands nothing to publish"
    assert uploaded <= downloaded, (
        f"publish never downloads the artifacts {sorted(uploaded - downloaded)}"
    )


def test_publish_downloads_only_artifacts_that_are_uploaded(workflow: dict[Any, Any]) -> None:
    uploaded: set[str] = set()
    for name in _jobs(workflow):
        uploaded.update(_uploaded_names(_job(workflow, name)))
    downloaded = _downloaded_names(_job(workflow, "publish"))

    assert downloaded <= uploaded, (
        f"publish downloads artifacts nobody uploads: {sorted(downloaded - uploaded)}"
    )


def test_uploads_fail_when_the_file_is_missing(workflow: dict[Any, Any]) -> None:
    for name in _jobs(workflow):
        for step in _upload_steps(_job(workflow, name)):
            artifact = (step.get("with") or {}).get("name")
            assert (step.get("with") or {}).get("if-no-files-found") == "error", (
                f"artifact {artifact!r} would silently upload nothing; set if-no-files-found: error"
            )


def test_every_action_is_pinned_to_a_version(workflow: dict[Any, Any]) -> None:
    for name, job in _jobs(workflow).items():
        for step in _steps(job):
            uses = step.get("uses")
            if uses is None:
                continue
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@v\d+", str(uses)), (
                f"job {name!r} uses {uses!r}; a job that can write must not run a floating action"
            )


def test_no_job_checks_out_the_pull_request_head(
    workflow: dict[Any, Any], workflow_text: str
) -> None:
    for name, job in _jobs(workflow).items():
        for step in _steps(job):
            if "actions/checkout@" in str(step.get("uses", "")):
                assert "ref" not in (step.get("with") or {}), (
                    f"job {name!r} checks out a ref; the workflow runs from the base commit"
                )

    for marker in ("github.event.pull_request.head.sha", "github.event.pull_request.head.ref"):
        assert marker not in workflow_text, (
            f"the workflow references {marker}: the pull request head is never checked out"
        )
    assert "refs/pull/" not in workflow_text, (
        "the workflow must not check out the pull request merge ref"
    )


def test_the_pipeline_never_passes_the_write_flag(
    workflow: dict[Any, Any], workflow_text: str
) -> None:
    for name, job in _jobs(workflow).items():
        for command in _runs(job):
            assert "--write" not in command, (
                f"job {name!r} passes --write; this slice of the pipeline is dry-run only"
            )
    assert "--write" not in workflow_text, "the workflow must not write in this slice"
