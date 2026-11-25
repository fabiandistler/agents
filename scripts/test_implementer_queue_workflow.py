"""Guardrails for the implementer queue's workflows (#801, #909).

implementer-queue.yml calls the reusable factory-implementer-queue.yml. Its
model-free `start-next` job runs scripts/implementer_queue.py; its model-free
`report-failure` job dispatches the caller's Fix task after a failed queue run
that the implementer's follow-up job dispatched with GITHUB_TOKEN, which starts
no workflow_run (#909). The tests pin an empty top-level permission set,
`actions: write` on those two jobs only, SHA-pinned actions, the agreed
triggers, and dispatch targets that are the implementer and the Fix task.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import implementer_follow_up
import implementer_setup
import pr_cli
import pytest
from agent_run_workflow_testkit import (
    EXPRESSION,
    FACTORY_IMPLEMENTER,
    IMPLEMENTER,
    WORKFLOWS,
    agent_job,
    named_step,
    single_job,
    step_with_id,
    workflow,
)
from test_implementer_follow_up import FakeClient

QUEUE = WORKFLOWS / "implementer-queue.yml"
FACTORY_QUEUE = WORKFLOWS / "factory-implementer-queue.yml"
QUEUE_WORKFLOWS = (QUEUE, FACTORY_QUEUE)
FIX_TASK = WORKFLOWS / "fix-task.yml"

STARTER = "start-next"
REPORT_FAILURE = "report-failure"

STARTER_SCOPES = {
    "actions": "write",
    "contents": "read",
    "issues": "read",
    "pull-requests": "read",
}


def factory_job(name: str) -> dict:
    return workflow(FACTORY_QUEUE)["jobs"][name]


def starter_step(job: dict) -> dict:
    steps = [step for step in job["steps"] if "implementer_queue.py" in step.get("run", "")]
    assert len(steps) == 1, "exactly one step runs the queue script"
    return steps[0]


def test_permissions_are_empty_by_default_and_each_job_asks_for_exactly_its_scopes():
    for path in QUEUE_WORKFLOWS:
        document = workflow(path)
        assert document["permissions"] == {}, f"{path.name}: top-level permissions must stay empty"
    # The caller's cap; the report job's actions: write fits under it.
    assert single_job(QUEUE)["permissions"] == STARTER_SCOPES
    jobs = workflow(FACTORY_QUEUE)["jobs"]
    assert {name: job["permissions"] for name, job in jobs.items()} == {
        STARTER: STARTER_SCOPES,
        REPORT_FAILURE: {"actions": "write"},
    }, "the report job only dispatches the Fix task"


def test_the_implementers_model_job_keeps_actions_read_only():
    # Only its model-free follow-up job dispatches (#863).
    assert agent_job(FACTORY_IMPLEMENTER)["permissions"]["actions"] == "read"


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
    assert set(triggers) == {"workflow_run", "issues", "schedule", "workflow_dispatch", "push"}
    assert triggers["workflow_run"] == {
        "workflows": [workflow(IMPLEMENTER)["name"]],
        "types": ["completed"],
    }
    assert triggers["issues"] == {"types": ["closed"]}, "a closed issue may free a blocked one"
    assert triggers["schedule"], "the fallback when a workflow_run chain stops"
    assert triggers["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True
    # The caller's own merge or change starts the queue once, so a merge that
    # closes no issue does not wait for a schedule slot GitHub may drop (#961).
    assert triggers["push"] == {
        "branches": ["main"],
        "paths": [f".github/workflows/{QUEUE.name}"],
    }
    assert set(workflow(FACTORY_QUEUE)[True]) == {"workflow_call"}


def test_a_push_of_the_caller_starts_a_real_queue_run():
    # The merge is the maintainer's go-ahead, so a push run dispatches.
    push = {
        "github.event_name": "push",
        "github.event.workflow_run.conclusion": "",
        "inputs.dry_run": "",
    }
    job = single_job(QUEUE)
    assert evaluate(job["if"], "||", push), "the start-next guard admits a push run"
    (dry_run,) = EXPRESSION.findall(job["with"]["dry_run"])
    assert not evaluate(dry_run, "&&", push)
    dispatch = {**push, "github.event_name": "workflow_dispatch", "inputs.dry_run": "true"}
    assert evaluate(dry_run, "&&", dispatch), "a manual run stays dry by default"


def test_a_skipped_implementer_run_starts_no_queue_job():
    guard = single_job(QUEUE)["if"]
    assert "github.event.workflow_run.conclusion != 'skipped'" in guard


def test_the_queue_dispatches_the_implementer_which_accepts_a_dispatch():
    assert single_job(QUEUE)["with"]["workflow_file"] == IMPLEMENTER.name
    assert IMPLEMENTER.name == implementer_setup.IMPLEMENTER_WORKFLOW
    inputs = workflow(IMPLEMENTER)[True]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"issue"}, "the queue sends only inputs.issue"
    assert single_job(IMPLEMENTER)["uses"] == f"./.github/workflows/{FACTORY_IMPLEMENTER.name}"
    guard = agent_job(FACTORY_IMPLEMENTER)["if"]
    assert "github.event_name == 'workflow_dispatch'" in guard, "a bot's dispatch must run"
    # The action admits the job token's dispatch only through allowed_bots:
    # test_factory_implementer_workflow.py pins it (#858).


def test_starters_never_run_side_by_side():
    concurrency = factory_job(STARTER)["concurrency"]
    assert concurrency == {"group": "implementer-queue", "cancel-in-progress": False}


def test_the_starter_passes_values_through_env_and_uses_the_job_token():
    step = starter_step(factory_job(STARTER))
    assert not EXPRESSION.search(step["run"]), "inputs reach the shell through env only"
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"  # noqa: S105 -- an expression.
    assert "--job-name implement" in step["run"]
    assert "--workflow-file" in step["run"]


# --- The failure report (#909) ----------------------------------------------
#
# A queue run the implementer's follow-up job dispatched with GITHUB_TOKEN
# starts no workflow_run workflow (#858), so fix-task.yml's workflow_run list
# never sees it fail. The report job runs inside that run and dispatches the
# caller's Fix task with the run's own id. Every other queue run reaches the
# Fix task through workflow_run; a dispatch for it as well could file twice.

BOT = "github-actions[bot]"
PERSON = "maintainer"
CLAUSE = re.compile(r"(?P<context>[\w.-]+) (?P<operator>==|!=) '(?P<value>[^']*)'")


def evaluate(expression: str, operator: str, context: dict[str, str]) -> bool:
    """Evaluate string comparisons joined by one ``operator`` (`&&` or `||`).

    A clause that is a bare context name reads it as a boolean; any other shape
    fails here instead of being misread.
    """
    values = []
    for clause in (part.strip() for part in expression.split(operator)):
        match = CLAUSE.fullmatch(clause)
        if match:
            equal = context[match["context"]] == match["value"]
            values.append(equal == (match["operator"] == "=="))
        else:
            assert re.fullmatch(r"[\w.-]+", clause), f"unexpected clause: {clause!r}"
            values.append(context[clause] == "true")
    return all(values) if operator == "&&" else any(values)


def report_failure_clauses() -> list[str]:
    return [clause.strip() for clause in factory_job(REPORT_FAILURE)["if"].split("&&")]


def report_runs(context: dict[str, str]) -> bool:
    """Evaluate the report job's `if:` for one queue run.

    The guard is pinned below to `always()` and string comparisons joined by
    `&&`; any other shape fails here instead of being misread.
    """
    first, *comparisons = report_failure_clauses()
    assert first == "always()", "a failed starter must not skip the report job"
    return evaluate(" && ".join(comparisons), "&&", context)


def queue_run(**overrides: str) -> dict[str, str]:
    """A failed queue run the follow-up job dispatched, with ``overrides`` applied."""
    context = {
        "needs.start-next.result": "failure",
        "github.event_name": "workflow_dispatch",
        "github.actor": BOT,
        "github.triggering_actor": BOT,
        "inputs.fix_task_workflow": FIX_TASK.name,
    }
    assert set(overrides) <= set(context), "override only the fields the guard reads"
    context.update(overrides)
    return context


def test_the_failure_report_is_off_unless_the_caller_names_its_fix_task():
    inputs = workflow(FACTORY_QUEUE)[True]["workflow_call"]["inputs"]
    assert inputs["fix_task_workflow"]["type"] == "string"
    assert inputs["fix_task_workflow"]["default"] == ""


def test_the_failure_report_runs_after_the_starter_whatever_its_result():
    jobs = workflow(FACTORY_QUEUE)["jobs"]
    assert list(jobs) == [STARTER, REPORT_FAILURE], "the starter stays first"
    assert factory_job(REPORT_FAILURE)["needs"] == STARTER


def test_the_failure_report_guard_names_each_condition_once():
    assert report_failure_clauses() == [
        "always()",
        "needs.start-next.result == 'failure'",
        "github.event_name == 'workflow_dispatch'",
        # Not github.actor: a person's re-run keeps the bot as actor (#909).
        f"github.triggering_actor == '{BOT}'",
        "inputs.fix_task_workflow != ''",
    ]


def test_a_failed_run_the_follow_up_job_dispatched_reaches_the_fix_task():
    assert report_runs(queue_run())


@pytest.mark.parametrize(
    "context",
    [
        # Runs that reach fix-task.yml through workflow_run: filing them here too
        # could file twice. The bot as actor isolates the event clause.
        pytest.param(queue_run(**{"github.event_name": "workflow_run"}), id="workflow_run"),
        pytest.param(queue_run(**{"github.event_name": "schedule"}), id="schedule"),
        pytest.param(queue_run(**{"github.event_name": "issues"}), id="issues"),
        pytest.param(
            queue_run(**{"github.actor": PERSON, "github.triggering_actor": PERSON}),
            id="a-persons-workflow_dispatch",
        ),
        # A person's re-run of a dispatched run: GitHub keeps the bot as actor.
        pytest.param(queue_run(**{"github.triggering_actor": PERSON}), id="a-persons-re-run"),
        pytest.param(queue_run(**{"needs.start-next.result": "success"}), id="start-next-success"),
        pytest.param(queue_run(**{"needs.start-next.result": "skipped"}), id="start-next-skipped"),
        pytest.param(
            queue_run(**{"needs.start-next.result": "cancelled"}), id="start-next-cancelled"
        ),
        pytest.param(queue_run(**{"inputs.fix_task_workflow": ""}), id="no-fix-task-named"),
    ],
)
def test_the_failure_report_does_not_run(context):
    assert not report_runs(context)


def test_the_failure_report_writes_only_actions_and_waits_behind_no_starter():
    job = factory_job(REPORT_FAILURE)
    assert job["permissions"] == {"actions": "write"}
    # In the `implementer-queue` group it would wait behind the next starter.
    assert "concurrency" not in job
    assert job["timeout-minutes"] <= 5


def test_the_failure_report_is_model_free_and_sets_up_as_the_starter_does():
    report, starter = factory_job(REPORT_FAILURE), factory_job(STARTER)
    assert step_with_id(report, "factory") == step_with_id(starter, "factory")
    uses = [step for step in report["steps"] if "uses" in step]
    assert uses == [step for step in starter["steps"] if "uses" in step], "setup-python only"
    assert not any("actions/checkout@" in step["uses"] for step in uses)


def report_step() -> dict:
    return named_step(factory_job(REPORT_FAILURE), "Start the Fix task")


def test_the_failure_report_takes_values_through_env_and_uses_the_job_token():
    step = report_step()
    assert not EXPRESSION.search(step["run"]), "values reach the shell through env only"
    assert step["env"] == {
        "GITHUB_TOKEN": "${{ github.token }}",
        "FACTORY_DIR": "${{ steps.factory.outputs.dir }}",
        "REPO": "${{ github.repository }}",
        "RUN_ID": "${{ github.run_id }}",
        "DEFAULT_BRANCH": "${{ github.event.repository.default_branch }}",
        "START_NEXT_RESULT": "${{ needs.start-next.result }}",
        "FIX_TASK_WORKFLOW": "${{ inputs.fix_task_workflow }}",
    }
    assert '"$FACTORY_DIR/scripts/implementer_follow_up.py"' in step["run"]


def report_command_line(tmp_path: Path) -> list[str]:
    """Run the report step with a stand-in python3 and return the arguments it got."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_file = tmp_path / "argv"
    shim = bin_dir / "python3"
    shim.write_text('#!/bin/sh\nprintf \'%s\\0\' "$@" > "$ARGV_FILE"\n', encoding="utf-8")
    shim.chmod(0o755)
    subprocess.run(  # noqa: S603 -- runs the workflow's own report step.
        ["bash", "-e", "-c", report_step()["run"]],  # noqa: S607 -- bash from PATH.
        env={
            "ARGV_FILE": str(argv_file),
            "FACTORY_DIR": "/factory",
            "REPO": "owner/repo",
            "RUN_ID": "4242",
            "DEFAULT_BRANCH": "main",
            "START_NEXT_RESULT": "failure",
            "FIX_TASK_WORKFLOW": FIX_TASK.name,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp_path),
        },
        check=True,
    )
    script, *arguments = argv_file.read_text(encoding="utf-8").split("\0")[:-1]
    assert script == "/factory/scripts/implementer_follow_up.py"
    return arguments


def test_the_failure_report_dispatches_only_the_fix_task_with_this_run_id(tmp_path, monkeypatch):
    # The queue's own dispatch stays off: a failed run must not start the next one.
    client = FakeClient()
    monkeypatch.setattr(implementer_follow_up, "GitHubClient", lambda token: client)
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    assert implementer_follow_up.main(report_command_line(tmp_path)) == pr_cli.EXIT_OK
    assert client.posts == [
        (
            f"/repos/owner/repo/actions/workflows/{FIX_TASK.name}/dispatches",
            {"ref": "main", "inputs": {"run_id": "4242", "dry_run": "false"}},
        )
    ]


def test_the_caller_names_its_fix_task_which_watches_every_other_queue_run():
    caller = single_job(QUEUE)
    assert caller["with"]["fix_task_workflow"] == FIX_TASK.name
    assert caller["permissions"]["actions"] == "write", "the cap allows the report's dispatch"
    fix_task = workflow(FIX_TASK)[True]
    assert set(fix_task["workflow_dispatch"]["inputs"]) == {"run_id", "dry_run"}
    # The runs the report job leaves alone reach the Fix task this way (#908).
    assert workflow(QUEUE)["name"] in fix_task["workflow_run"]["workflows"]
