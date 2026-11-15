"""Tests for implementer_follow_up.py: the dispatches after a queue-dispatched run (#863)."""

from __future__ import annotations

import json

import implementer_follow_up
import pr_cli
import pr_github_client
import pytest
from pr_github_fake import json_response

REPO = "owner/repo"
RUN_ID = 4242
QUEUE = "implementer-queue.yml"
FIX_TASK = "fix-task.yml"
QUEUE_PATH = f"/repos/{REPO}/actions/workflows/{QUEUE}/dispatches"
FIX_TASK_PATH = f"/repos/{REPO}/actions/workflows/{FIX_TASK}/dispatches"
QUEUE_DISPATCH = (QUEUE_PATH, {"ref": "main", "inputs": {"dry_run": "false"}})
FIX_TASK_DISPATCH = (
    FIX_TASK_PATH,
    {"ref": "main", "inputs": {"run_id": str(RUN_ID), "dry_run": "false"}},
)


class FakeClient:
    """Records every POST; fails the ones whose path is in ``failing``."""

    def __init__(self, failing: tuple[str, ...] = ()) -> None:
        self.failing = failing
        self.posts: list[tuple[str, dict | None]] = []

    def post(self, path, payload=None):
        self.posts.append((path, payload))
        if path in self.failing:
            raise pr_github_client.FetchError(f"POST {path} returned HTTP 404", status=404)
        return json_response({}, status=204)


def run(client, result="success", queue=QUEUE, fix_task=FIX_TASK):
    dispatches = implementer_follow_up.plan(
        run_id=RUN_ID,
        implement_result=result,
        queue_workflow=queue,
        fix_task_workflow=fix_task,
    )
    return implementer_follow_up.send(client, REPO, "main", dispatches)


def test_a_successful_run_starts_only_the_queue():
    client = FakeClient()
    outcome = run(client)
    assert client.posts == [QUEUE_DISPATCH]
    assert outcome.dispatched == [QUEUE]
    assert outcome.failed == []


@pytest.mark.parametrize("result", ["failure", "cancelled"])
def test_a_run_that_did_not_succeed_starts_the_fix_task_then_the_queue(result):
    # The Fix task's policy decides what is filed (FAILED_CONCLUSIONS in
    # factory_failure_policy.py); it plans nothing for a cancelled run.
    client = FakeClient()
    outcome = run(client, result=result)
    assert client.posts == [FIX_TASK_DISPATCH, QUEUE_DISPATCH]
    assert outcome.dispatched == [FIX_TASK, QUEUE]


def test_a_workflow_left_unnamed_is_not_dispatched():
    client = FakeClient()
    outcome = run(client, result="failure", queue=None, fix_task=None)
    assert client.posts == []
    assert outcome.dispatched == []


def test_a_failed_dispatch_does_not_stop_the_other():
    client = FakeClient(failing=(FIX_TASK_PATH,))
    outcome = run(client, result="failure")
    assert client.posts == [FIX_TASK_DISPATCH, QUEUE_DISPATCH]
    assert outcome.dispatched == [QUEUE]
    assert outcome.failed == [
        implementer_follow_up.Failure(FIX_TASK, f"POST {FIX_TASK_PATH} returned HTTP 404")
    ]


ARGV = [
    "--repo",
    REPO,
    "--run-id",
    str(RUN_ID),
    "--ref",
    "main",
    "--implement-result",
    "failure",
    "--queue-workflow",
    QUEUE,
    "--fix-task-workflow",
    FIX_TASK,
]


def test_main_prints_the_dispatches_and_exits_zero(monkeypatch, capsys):
    client = FakeClient()
    monkeypatch.setattr(implementer_follow_up, "GitHubClient", lambda token: client)
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    assert implementer_follow_up.main(ARGV) == pr_cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == {
        "dispatched": [FIX_TASK, QUEUE],
        "failed": [],
        "dry_run": False,
    }
    assert client.posts == [FIX_TASK_DISPATCH, QUEUE_DISPATCH]


def test_main_exits_one_when_a_dispatch_failed(monkeypatch, capsys):
    client = FakeClient(failing=(QUEUE_PATH,))
    monkeypatch.setattr(implementer_follow_up, "GitHubClient", lambda token: client)
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    assert implementer_follow_up.main(ARGV) == pr_cli.EXIT_ACTION_FAILED
    printed = json.loads(capsys.readouterr().out)
    assert printed["dispatched"] == [FIX_TASK]
    assert [entry["workflow"] for entry in printed["failed"]] == [QUEUE]


def test_an_empty_workflow_argument_names_none(monkeypatch, capsys):
    # The reusable workflow passes its inputs as they are; "" is its default.
    client = FakeClient()
    monkeypatch.setattr(implementer_follow_up, "GitHubClient", lambda token: client)
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    argv = [*ARGV[:-4], "--queue-workflow", "", "--fix-task-workflow", ""]
    assert implementer_follow_up.main(argv) == pr_cli.EXIT_OK
    assert client.posts == []


def test_main_without_a_token_exits_five_on_stderr(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert implementer_follow_up.main(ARGV) == pr_cli.EXIT_MISSING_TOKEN
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "GITHUB_TOKEN is not set" in printed.err


def test_a_dry_run_prints_the_plan_and_needs_no_token(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(implementer_follow_up, "GitHubClient", pytest.fail)
    assert implementer_follow_up.main([*ARGV, "--dry-run"]) == pr_cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == {
        "dispatched": [FIX_TASK, QUEUE],
        "failed": [],
        "dry_run": True,
    }


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--queue-workflow", "../evil.yml"),
        ("--queue-workflow", "queue.yml -f x=y"),
        ("--fix-task-workflow", "fix-task"),
        ("--run-id", "12; true"),
        ("--run-id", "0"),
        ("--repo", "not-a-repo"),
        ("--implement-result", "neutral"),
    ],
)
def test_bad_arguments_are_usage_errors(flag, value, capsys):
    argv = list(ARGV)
    argv[argv.index(flag) + 1] = value
    with pytest.raises(SystemExit) as stopped:
        implementer_follow_up.main(argv)
    assert stopped.value.code == 2


@pytest.mark.parametrize("name", ["implementer-queue.yml", "fix-task.yaml", "a_b.c-d.yml"])
def test_file_names_follow_the_queues_pattern(name, monkeypatch, capsys):
    monkeypatch.setattr(implementer_follow_up, "GitHubClient", lambda token: FakeClient())
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    argv = list(ARGV)
    argv[argv.index("--queue-workflow") + 1] = name
    assert implementer_follow_up.main(argv) == pr_cli.EXIT_OK


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as stopped:
        implementer_follow_up.main(["--help"])
    assert stopped.value.code == 0
    text = capsys.readouterr().out
    assert "--implement-result" in text
    assert pr_cli.exit_help(0, 1, 2, 5) in text
