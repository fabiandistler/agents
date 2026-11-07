"""Structure tests for the PR review workflow (.github/workflows/pr-review.yml).

The workflow is the trust boundary of the pipeline: it decides which credential
each stage holds and guarantees that the pull request head is never checked out
or executed. Each safety property is asserted on its own, so removing one names
itself in the failing test instead of hiding behind a generic YAML comparison.
This module holds the triggers, the permissions and the run-wide invariants;
the per-job tests live in test_pr_workflow_assess_review.py and
test_pr_workflow_publish.py.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import pytest
from pr_workflow_testkit import (
    HOLD_CONDITION,
    JOB_NAMES,
    LABEL_EVENT,
    PIPELINE_CLIS,
    REPO_ROOT,
    REVIEW_EVENTS,
    downloaded_names,
    job_named,
    jobs_of,
    load_workflow_text,
    normalize,
    parse_workflow,
    run_containing,
    runs_of,
    steps_of,
    triggers_of,
    upload_steps,
    uploaded_names,
)


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return load_workflow_text()


@pytest.fixture(scope="module")
def workflow(workflow_text: str) -> dict[Any, Any]:
    return parse_workflow(workflow_text)


def test_pull_request_target_carries_the_review_events(workflow: dict[Any, Any]) -> None:
    target = triggers_of(workflow).get("pull_request_target")
    assert isinstance(target, dict), "the workflow must trigger on pull_request_target"
    declared = target.get("types")
    expected = [*REVIEW_EVENTS, LABEL_EVENT]
    assert sorted(declared or []) == sorted(expected), (
        f"pull_request_target must list exactly {expected}; found {declared}"
    )


def test_workflow_does_not_trigger_on_pull_request(workflow: dict[Any, Any]) -> None:
    assert "pull_request" not in triggers_of(workflow), (
        "pull_request runs the workflow from the head commit; only pull_request_target is allowed"
    )


def test_workflow_dispatch_takes_a_pull_request_and_a_dry_run_flag(
    workflow: dict[Any, Any],
) -> None:
    dispatch = triggers_of(workflow).get("workflow_dispatch")
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


def test_the_pipeline_has_exactly_its_four_jobs(workflow: dict[Any, Any]) -> None:
    assert set(jobs_of(workflow)) == JOB_NAMES, (
        f"the pipeline is {sorted(JOB_NAMES)}; found {sorted(jobs_of(workflow))}"
    )


GUARDED_WRITE = re.compile(
    r'if \[ "\$WRITE" = "true" \]; then\n(?P<write>.*?)\n\s*else\n(?P<dry>.*?)\n\s*fi\n',
    re.DOTALL,
)


def test_the_write_flag_appears_once_in_the_guarded_publish_branch(
    workflow: dict[Any, Any], workflow_text: str
) -> None:
    assert workflow_text.count("--write") == 2, (
        "the write flag belongs to exactly two invocations: the guarded publish step "
        "and the hold, which never runs on a manual run"
    )
    for name, job in jobs_of(workflow).items():
        for step in steps_of(job):
            if "--write" in str(step.get("run", "")):
                assert name in {"publish", "hold"}, f"job {name!r} must not write"
    assert normalize(job_named(workflow, "hold").get("if")) == HOLD_CONDITION, (
        "the hold writes unguarded, so it must never run on workflow_dispatch"
    )

    command = run_containing(job_named(workflow, "publish"), "scripts/pr_publish.py")
    match = GUARDED_WRITE.search(command)
    assert match is not None, "the publish step needs a WRITE-guarded branch and a dry-run branch"

    write_branch = match.group("write")
    assert "--write" in write_branch
    assert "--live" in write_branch, "the write path re-fetches the pull request"
    assert '--pr "$PR"' in write_branch
    assert "github.repository" in write_branch
    assert "--assessment assessment.json" in write_branch
    assert "--review review.json" in write_branch

    dry_branch = match.group("dry")
    assert "--write" not in dry_branch
    # A manual dry run plans like the write path: from a fresh fetch, so the
    # head SHA re-check and the current policy run, not the assess-time context.
    assert "--live" in dry_branch, "the dry run re-fetches the pull request"
    assert '--pr "$PR"' in dry_branch
    assert "--context" not in dry_branch, "the dry run must not plan from assess-time data"
    assert "--assessment assessment.json" in dry_branch
    assert "--review review.json" in dry_branch


def test_concurrency_is_keyed_by_pull_request(workflow: dict[Any, Any]) -> None:
    concurrency = workflow.get("concurrency")
    assert isinstance(concurrency, dict), "the workflow needs a concurrency group"
    group = normalize(concurrency.get("group") or "")
    assert group.startswith("pr-review-"), f"the group must be namespaced; found {group!r}"
    assert "github.event.pull_request.number" in group, "the group must key on the pull request"
    assert "inputs.pr" in group, "a manual run must key on its input as well"
    assert concurrency.get("cancel-in-progress") is True, "a superseded run must be cancelled"


def test_a_label_event_never_cancels_a_review_run(workflow: dict[Any, Any]) -> None:
    # A label run must not cancel the run reviewing the head, and a later label
    # must not cancel a do-not-merge hold: label runs get a group per label.
    group = normalize(workflow["concurrency"]["group"])
    suffix = "github.event.action == 'labeled' && format('-label-{0}', github.event.label.name)"
    assert suffix in group, f"label events need their own group per label; found {group!r}"


def test_every_run_step_calls_a_cli_that_exists(workflow: dict[Any, Any]) -> None:
    referenced: set[str] = set()
    for job in jobs_of(workflow).values():
        for command in runs_of(job):
            referenced.update(re.findall(r"scripts/[\w./-]+\.py", command))

    assert referenced, "the workflow runs no repository CLI"
    missing = sorted(path for path in referenced if not (REPO_ROOT / path).is_file())
    assert not missing, f"run steps reference CLIs that do not exist: {missing}"

    unexpected = sorted({Path(path).name for path in referenced} - PIPELINE_CLIS)
    assert not unexpected, f"the pipeline runs a CLI outside its three stages: {unexpected}"


def test_every_uploaded_artifact_is_downloaded_by_publish(workflow: dict[Any, Any]) -> None:
    uploaded: set[str] = set()
    for name in jobs_of(workflow):
        uploaded.update(uploaded_names(job_named(workflow, name)))
    downloaded = downloaded_names(job_named(workflow, "publish"))

    assert uploaded, "the pipeline hands nothing to publish"
    assert uploaded <= downloaded, (
        f"publish never downloads the artifacts {sorted(uploaded - downloaded)}"
    )


def test_publish_downloads_only_artifacts_that_are_uploaded(workflow: dict[Any, Any]) -> None:
    uploaded: set[str] = set()
    for name in jobs_of(workflow):
        uploaded.update(uploaded_names(job_named(workflow, name)))
    downloaded = downloaded_names(job_named(workflow, "publish"))

    assert downloaded <= uploaded, (
        f"publish downloads artifacts nobody uploads: {sorted(downloaded - uploaded)}"
    )


def test_uploads_fail_when_the_file_is_missing(workflow: dict[Any, Any]) -> None:
    for name in jobs_of(workflow):
        for step in upload_steps(job_named(workflow, name)):
            artifact = (step.get("with") or {}).get("name")
            assert (step.get("with") or {}).get("if-no-files-found") == "error", (
                f"artifact {artifact!r} would silently upload nothing; set if-no-files-found: error"
            )


def test_every_action_is_pinned_to_a_commit_sha(
    workflow: dict[Any, Any], workflow_text: str
) -> None:
    # A tag can be moved to new code; a full commit SHA cannot. A moved tag
    # would run unreviewed third-party code next to the write token and the
    # model key.
    for name, job in jobs_of(workflow).items():
        for step in steps_of(job):
            uses = step.get("uses")
            if uses is None:
                continue
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", str(uses)), (
                f"job {name!r} uses {uses!r}; pin every action to a full commit SHA"
            )

    # YAML drops comments, so the version comment is checked on the raw text.
    uses_lines = [
        line for line in workflow_text.splitlines() if re.match(r"\s*(?:-\s+)?uses:", line)
    ]
    assert uses_lines, "the workflow uses no actions; the pinning check would be vacuous"
    untagged = [
        line.strip()
        for line in uses_lines
        if not re.search(r"@[0-9a-f]{40} # v\d+(?:\.\d+)*$", line)
    ]
    assert not untagged, (
        f"every pinned action needs its tag as a trailing `# vX.Y.Z` comment; found {untagged}"
    )


HEAD_MARKERS = (
    "github.event.pull_request.head.sha",
    "github.event.pull_request.head.ref",
    "refs/pull/",
    "gh pr checkout",
)


def head_checkouts(workflow: dict[Any, Any], workflow_text: str) -> list[str]:
    """Name every way the workflow would check out the pull request head."""
    found: list[str] = []
    for name, job in jobs_of(workflow).items():
        for step in steps_of(job):
            if "actions/checkout@" not in str(step.get("uses", "")):
                continue
            # Without these keys the checkout is the base commit of this repository;
            # `repository:` could point at the fork that holds the head.
            for key in ("ref", "repository"):
                if key in (step.get("with") or {}):
                    found.append(f"job {name!r} checks out with {key}:")
    found.extend(f"references {marker}" for marker in HEAD_MARKERS if marker in workflow_text)
    return found


def test_no_job_checks_out_the_pull_request_head(
    workflow: dict[Any, Any], workflow_text: str
) -> None:
    assert head_checkouts(workflow, workflow_text) == [], (
        "the workflow runs from the base commit: the pull request head is never checked out"
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("ref", "${{ github.event.pull_request.head.sha }}"),
        ("repository", "${{ github.event.pull_request.head.repo.full_name }}"),
    ],
)
def test_the_head_checkout_check_catches_a_head_checkout(
    workflow: dict[Any, Any], workflow_text: str, key: str, value: str
) -> None:
    tampered = copy.deepcopy(workflow)
    checkout = next(
        step
        for step in steps_of(job_named(tampered, "publish"))
        if "actions/checkout@" in str(step.get("uses", ""))
    )
    checkout.setdefault("with", {})[key] = value

    assert f"job 'publish' checks out with {key}:" in head_checkouts(tampered, workflow_text)
