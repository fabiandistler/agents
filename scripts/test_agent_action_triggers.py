"""No workflow starts claude-code-action from a comment or a review (ADR-0019).

The action gives the model a Claude GitHub App token that can write contents,
issues and pull requests, whatever the job's `permissions` say. On a comment
or review trigger the model reads the whole thread, and anyone can write to a
thread of this public repository. Its issue and PR bodies reach the model even
when the comments are filtered by actor. `claude.yml`, the `@claude` mention
assistant, did exactly that and was removed (#857).

Comment-driven runs that need a model use a tool-less `claude -p` call
(`factory-issue-triage.yml`, ADR-0013) or a model-free gate that starts the
action from a trusted contract (the factory tasks, ADR-0014 and ADR-0018).
The check follows local reusable workflows (`uses: ./.github/workflows/...`),
so a caller inherits the action of the workflow it calls.
"""

from __future__ import annotations

import re
from pathlib import Path

from agent_run_workflow_testkit import ACTION, WORKFLOWS, workflow
from pr_workflow_testkit import triggers_of

WORKFLOW_FILES = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
LOCAL_REUSABLE = re.compile(r"^\./\.github/workflows/(?P<name>[\w.-]+\.ya?ml)$")
THREAD_EVENTS = {
    "issue_comment",
    "pull_request_review_comment",
    "pull_request_review",
    "discussion_comment",
}


def _uses(jobs: dict) -> list[str]:
    refs = []
    for job in jobs.values():
        if "uses" in job:
            refs.append(job["uses"])
        refs.extend(step["uses"] for step in job.get("steps", []) if "uses" in step)
    return refs


def _runs_the_action(path: Path) -> bool:
    for ref in _uses(workflow(path)["jobs"]):
        if ref.startswith(ACTION):
            return True
        local = LOCAL_REUSABLE.match(ref)
        if local and _runs_the_action(WORKFLOWS / local["name"]):
            return True
    return False


def test_the_check_sees_the_action() -> None:
    # Guards against a parser change that would make the main test pass vacuously.
    users = [path.name for path in WORKFLOW_FILES if _runs_the_action(path)]
    assert "factory-implementer.yml" in users
    assert "implementer.yml" in users, "a caller inherits the action of its reusable workflow"


def test_no_comment_or_review_event_starts_the_action() -> None:
    offenders = {}
    for path in WORKFLOW_FILES:
        thread_events = triggers_of(workflow(path)).keys() & THREAD_EVENTS
        if thread_events and _runs_the_action(path):
            offenders[path.name] = sorted(thread_events)
    assert offenders == {}
