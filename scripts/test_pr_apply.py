"""Tests for the model-free plan writer (scripts/pr_apply.py).

The public seam is ``apply_plan(plan, client)`` plus the CLI. Every test injects
a fake client; none performs a network call. The fake records the method, path
and payload of every call so the tests assert the exact HTTP conversation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pr_apply
import pr_github
import pytest

REPO = "fabiandistler/agents"
NUMBER = 42
LABELS_PATH = f"/repos/{REPO}/labels"
ISSUE_LABELS_PATH = f"/repos/{REPO}/issues/{NUMBER}/labels"
ISSUE_COMMENTS_PATH = f"/repos/{REPO}/issues/{NUMBER}/comments"
REVIEWERS_PATH = f"/repos/{REPO}/pulls/{NUMBER}/requested_reviewers"
ASSIGNEES_PATH = f"/repos/{REPO}/issues/{NUMBER}/assignees"
BOT = "fabiandistler"

SCRIPT = Path(__file__).resolve().parent / "pr_apply.py"


class FakeClient:
    """A routed fake for the write surface, recording every call."""

    def __init__(self, handler=None) -> None:
        self.calls: list[dict] = []
        self.handler = handler

    def _call(self, method: str, path: str, payload: dict | None) -> pr_github.Response:
        self.calls.append({"method": method, "path": path, "payload": payload})
        if self.handler is not None:
            outcome = self.handler(method, path, payload)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return pr_github.Response(status=200, body=b"{}")

    def post(self, path: str, payload: dict | None = None) -> pr_github.Response:
        return self._call("POST", path, payload)

    def patch(self, path: str, payload: dict | None = None) -> pr_github.Response:
        return self._call("PATCH", path, payload)

    def delete(self, path: str, payload: dict | None = None) -> pr_github.Response:
        return self._call("DELETE", path, payload)


def make_plan(actions: list[dict] | None = None, **overrides: object) -> dict:
    plan = {
        "schema_version": 1,
        "repo": REPO,
        "number": NUMBER,
        "head_sha": "abc123",
        "status": "planned",
        "abort_reason": None,
        "actions": [] if actions is None else actions,
        "decision": {
            "risk": "low",
            "review_status": "ok",
            "verdict": "pass",
            "auto_merge": "off",
        },
    }
    plan.update(overrides)
    return plan


def calls_of(client: FakeClient, method: str) -> list[dict]:
    return [call for call in client.calls if call["method"] == method]


def paths(client: FakeClient) -> list[tuple[str, str]]:
    return [(call["method"], call["path"]) for call in client.calls]


def only_result(results: list[dict]) -> dict:
    assert len(results) == 1
    return results[0]


# --- set_labels --------------------------------------------------------------


def test_set_labels_creates_each_label_then_adds_and_removes():
    client = FakeClient()
    plan = make_plan(
        [{"kind": "set_labels", "add": ["risk:low", "review:pass"], "remove": ["risk:high"]}]
    )

    result = only_result(pr_apply.apply_plan(plan, client))

    assert result["kind"] == "set_labels"
    assert result["ok"] is True
    assert isinstance(result["detail"], str) and result["detail"]
    assert paths(client) == [
        ("POST", LABELS_PATH),
        ("POST", LABELS_PATH),
        ("POST", ISSUE_LABELS_PATH),
        ("DELETE", f"{ISSUE_LABELS_PATH}/risk%3Ahigh"),
    ]
    created = calls_of(client, "POST")
    assert [call["payload"]["name"] for call in created[:2]] == ["risk:low", "review:pass"]
    for call in created[:2]:
        assert re.fullmatch(r"[0-9a-f]{6}", call["payload"]["color"])
        assert call["payload"]["description"]
    assert created[2]["payload"] == {"labels": ["risk:low", "review:pass"]}


def test_every_label_in_the_vocabulary_has_a_creation_entry():
    labels = [
        "risk:low",
        "risk:medium",
        "risk:high",
        "review:pass",
        "review:concerns",
        "review:block",
        "review:unavailable",
        "needs-review",
        "do-not-merge",
        "auto-merge:bot",
    ]
    client = FakeClient()

    result = only_result(
        pr_apply.apply_plan(
            make_plan([{"kind": "set_labels", "add": labels, "remove": []}]), client
        )
    )

    assert result["ok"] is True
    created = calls_of(client, "POST")
    assert [call["payload"]["name"] for call in created[:-1]] == labels


def test_an_existing_label_is_not_an_error():
    def handler(method, path, payload):
        if method == "POST" and path == LABELS_PATH:
            raise pr_github.FetchError("label already exists", status=422)
        return pr_github.Response(status=201)

    client = FakeClient(handler)

    result = only_result(
        pr_apply.apply_plan(
            make_plan([{"kind": "set_labels", "add": ["risk:low"], "remove": []}]), client
        )
    )

    assert result["ok"] is True
    assert paths(client) == [("POST", LABELS_PATH), ("POST", ISSUE_LABELS_PATH)]


def test_an_existing_label_returned_as_422_is_not_an_error():
    def handler(method, path, payload):
        if method == "POST" and path == LABELS_PATH:
            return pr_github.Response(status=422, body=b'{"errors":[{"code":"already_exists"}]}')
        return pr_github.Response(status=200)

    client = FakeClient(handler)

    result = only_result(
        pr_apply.apply_plan(
            make_plan([{"kind": "set_labels", "add": ["risk:low"], "remove": []}]), client
        )
    )

    assert result["ok"] is True
    assert ("POST", ISSUE_LABELS_PATH) in paths(client)


def test_a_failed_label_creation_stops_the_label_action():
    def handler(method, path, payload):
        if method == "POST" and path == LABELS_PATH:
            raise pr_github.FetchError("server error", status=500)
        return pr_github.Response(status=200)

    client = FakeClient(handler)

    result = only_result(
        pr_apply.apply_plan(
            make_plan([{"kind": "set_labels", "add": ["risk:low"], "remove": ["risk:high"]}]),
            client,
        )
    )

    assert result["ok"] is False
    assert "500" in result["detail"]
    assert paths(client) == [("POST", LABELS_PATH)]


def test_a_missing_stale_label_is_not_an_error():
    def handler(method, path, payload):
        if method == "DELETE":
            raise pr_github.FetchError("label not found", status=404)
        return pr_github.Response(status=200)

    client = FakeClient(handler)

    result = only_result(
        pr_apply.apply_plan(
            make_plan([{"kind": "set_labels", "add": [], "remove": ["risk:high"]}]), client
        )
    )

    assert result["ok"] is True
    assert paths(client) == [("DELETE", f"{ISSUE_LABELS_PATH}/risk%3Ahigh")]


def test_a_missing_stale_label_returned_as_404_is_not_an_error():
    def handler(method, path, payload):
        if method == "DELETE":
            return pr_github.Response(status=404)
        return pr_github.Response(status=200)

    client = FakeClient(handler)

    result = only_result(
        pr_apply.apply_plan(
            make_plan([{"kind": "set_labels", "add": [], "remove": ["risk:high"]}]), client
        )
    )

    assert result["ok"] is True


def test_a_failed_label_removal_fails_the_action():
    def handler(method, path, payload):
        if method == "DELETE":
            raise pr_github.FetchError("server error", status=500)
        return pr_github.Response(status=200)

    client = FakeClient(handler)

    result = only_result(
        pr_apply.apply_plan(
            make_plan([{"kind": "set_labels", "add": [], "remove": ["risk:high"]}]), client
        )
    )

    assert result["ok"] is False
    assert "500" in result["detail"]


def test_an_empty_label_change_makes_no_call():
    client = FakeClient()

    result = only_result(
        pr_apply.apply_plan(make_plan([{"kind": "set_labels", "add": [], "remove": []}]), client)
    )

    assert result["ok"] is True
    assert client.calls == []


# --- upsert_comment ----------------------------------------------------------


def test_existing_comment_is_updated_in_place():
    client = FakeClient()
    plan = make_plan(
        [
            {
                "kind": "upsert_comment",
                "comment_id": 7,
                "marker": "<!-- pr-review-bot -->",
                "body": "new",
            }
        ]
    )

    result = only_result(pr_apply.apply_plan(plan, client))

    assert result["kind"] == "upsert_comment"
    assert result["ok"] is True
    assert paths(client) == [("PATCH", f"/repos/{REPO}/issues/comments/7")]
    assert client.calls[0]["payload"] == {"body": "new"}


def test_a_new_comment_is_posted_to_the_pull_request():
    client = FakeClient()
    plan = make_plan(
        [
            {
                "kind": "upsert_comment",
                "comment_id": None,
                "marker": "<!-- pr-review-bot -->",
                "body": "hello",
            }
        ]
    )

    result = only_result(pr_apply.apply_plan(plan, client))

    assert result["ok"] is True
    assert paths(client) == [("POST", ISSUE_COMMENTS_PATH)]
    assert client.calls[0]["payload"] == {"body": "hello"}


@pytest.mark.parametrize("comment_id", [0, -1, "7", True, 1.5])
def test_an_invalid_comment_id_is_rejected_before_any_call(comment_id):
    client = FakeClient()
    plan = make_plan(
        [{"kind": "upsert_comment", "comment_id": comment_id, "marker": "m", "body": "hello"}]
    )

    with pytest.raises(pr_apply.PlanError):
        pr_apply.apply_plan(plan, client)

    assert client.calls == []


@pytest.mark.parametrize("body", ["", "   ", None, 7])
def test_an_invalid_comment_body_is_rejected_before_any_call(body):
    client = FakeClient()
    plan = make_plan([{"kind": "upsert_comment", "comment_id": None, "marker": "m", "body": body}])

    with pytest.raises(pr_apply.PlanError):
        pr_apply.apply_plan(plan, client)

    assert client.calls == []


# --- Reviewer and assignee ---------------------------------------------------


def test_the_maintainer_is_requested_as_reviewer():
    client = FakeClient()
    plan = make_plan([{"kind": "request_reviewer", "login": BOT}])

    result = only_result(pr_apply.apply_plan(plan, client))

    assert result["ok"] is True
    assert paths(client) == [("POST", REVIEWERS_PATH)]
    assert client.calls[0]["payload"] == {"reviewers": [BOT]}


def test_the_maintainer_is_assigned_when_he_authored_the_pull_request():
    client = FakeClient()
    plan = make_plan([{"kind": "assign", "login": BOT}])

    result = only_result(pr_apply.apply_plan(plan, client))

    assert result["ok"] is True
    assert paths(client) == [("POST", ASSIGNEES_PATH)]
    assert client.calls[0]["payload"] == {"assignees": [BOT]}


@pytest.mark.parametrize("kind", ["request_reviewer", "assign"])
@pytest.mark.parametrize("login", ["octocat", "Fabiandistler", "", None, 7])
def test_anyone_but_the_maintainer_is_rejected_before_any_call(kind, login):
    client = FakeClient()
    plan = make_plan(
        [
            {"kind": "set_labels", "add": ["risk:low"], "remove": []},
            {"kind": kind, "login": login},
        ]
    )

    with pytest.raises(pr_apply.PlanError):
        pr_apply.apply_plan(plan, client)

    assert client.calls == []


# --- Fail closed -------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        {"kind": "approve"},
        {"kind": "request_changes"},
        {"kind": "close"},
        {"kind": "enable_auto_merge", "method": "merge", "delete_branch": True},
        {"kind": "disable_auto_merge"},
        {"kind": "merge"},
        {},
    ],
)
def test_an_unsupported_action_is_rejected_before_any_call(action):
    client = FakeClient()
    plan = make_plan([{"kind": "set_labels", "add": ["risk:low"], "remove": []}, action])

    with pytest.raises(pr_apply.PlanError):
        pr_apply.apply_plan(plan, client)

    assert client.calls == []


def test_an_aborted_plan_applies_nothing():
    client = FakeClient()
    plan = make_plan(
        [{"kind": "set_labels", "add": ["risk:low"], "remove": []}],
        status="aborted",
        abort_reason="head_sha_changed",
    )

    assert pr_apply.apply_plan(plan, client) == []
    assert client.calls == []


def test_every_action_yields_one_result_and_a_failure_does_not_stop_the_next():
    def handler(method, path, payload):
        if method == "POST" and path == LABELS_PATH:
            raise pr_github.FetchError("server error", status=500)
        return pr_github.Response(status=200)

    client = FakeClient(handler)
    plan = make_plan(
        [
            {"kind": "set_labels", "add": ["risk:low"], "remove": []},
            {"kind": "upsert_comment", "comment_id": None, "marker": "m", "body": "hello"},
            {"kind": "request_reviewer", "login": BOT},
        ]
    )

    results = pr_apply.apply_plan(plan, client)

    assert [result["kind"] for result in results] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]
    assert [result["ok"] for result in results] == [False, True, True]
    assert ("POST", ISSUE_COMMENTS_PATH) in paths(client)
    assert ("POST", REVIEWERS_PATH) in paths(client)


# --- Plan validation ---------------------------------------------------------


@pytest.mark.parametrize(
    "plan",
    [
        [],
        "plan",
        {"schema_version": 2, "repo": REPO, "number": NUMBER, "status": "planned", "actions": []},
        {
            "schema_version": 1,
            "repo": "not-a-repo",
            "number": NUMBER,
            "status": "planned",
            "actions": [],
        },
        {"schema_version": 1, "repo": REPO, "number": 0, "status": "planned", "actions": []},
        {"schema_version": 1, "repo": REPO, "number": True, "status": "planned", "actions": []},
        {"schema_version": 1, "repo": REPO, "number": NUMBER, "status": "weird", "actions": []},
        {"schema_version": 1, "repo": REPO, "number": NUMBER, "status": "planned", "actions": {}},
        {
            "schema_version": 1,
            "repo": REPO,
            "number": NUMBER,
            "status": "planned",
            "actions": ["x"],
        },
        {"schema_version": 1, "repo": REPO, "number": NUMBER, "status": "planned"},
    ],
)
def test_a_malformed_plan_is_rejected_before_any_call(plan):
    client = FakeClient()

    with pytest.raises(pr_apply.PlanError):
        pr_apply.apply_plan(plan, client)

    assert client.calls == []


@pytest.mark.parametrize(
    "action",
    [
        {"kind": "set_labels", "add": "risk:low", "remove": []},
        {"kind": "set_labels", "add": [""], "remove": []},
        {"kind": "set_labels", "add": ["risk:critical"], "remove": []},
        {"kind": "set_labels", "add": ["risk:low"], "remove": ["risk:low"]},
        {"kind": "set_labels", "add": ["risk:low"]},
    ],
)
def test_a_malformed_label_action_is_rejected_before_any_call(action):
    client = FakeClient()

    with pytest.raises(pr_apply.PlanError):
        pr_apply.apply_plan(make_plan([action]), client)

    assert client.calls == []


# --- CLI ---------------------------------------------------------------------


def write_plan(tmp_path: Path, plan: dict, name: str = "plan.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def run_cli(*args: str, **env: str) -> subprocess.CompletedProcess:
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GITHUB_ACTIONS", "GITHUB_TOKEN"}
    }
    clean_env.update(env)
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )


def test_cli_dry_run_prints_the_resolved_operations_without_a_call(tmp_path):
    plan = make_plan(
        [
            {"kind": "set_labels", "add": ["risk:low"], "remove": ["risk:high"]},
            {"kind": "upsert_comment", "comment_id": None, "marker": "m", "body": "hello"},
            {"kind": "request_reviewer", "login": BOT},
        ]
    )

    run = run_cli("--plan", str(write_plan(tmp_path, plan)))

    assert run.returncode == 0, run.stderr
    assert run.stderr == ""
    payload = json.loads(run.stdout)
    assert payload["write"] is False
    assert payload["status"] == "planned"
    assert payload["repo"] == REPO
    assert payload["number"] == NUMBER
    assert [operation["method"] for operation in payload["operations"]] == [
        "POST",
        "POST",
        "DELETE",
        "POST",
        "POST",
    ]
    assert payload["operations"][0]["path"] == LABELS_PATH
    assert payload["operations"][3]["path"] == ISSUE_COMMENTS_PATH


def test_cli_dry_run_of_an_aborted_plan_prints_no_operations(tmp_path):
    plan = make_plan(
        [{"kind": "set_labels", "add": ["risk:low"], "remove": []}],
        status="aborted",
        abort_reason="head_sha_changed",
    )

    run = run_cli("--plan", str(write_plan(tmp_path, plan)))

    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert payload["status"] == "aborted"
    assert payload["operations"] == []


def test_cli_write_outside_github_actions_exits_five(tmp_path):
    run = run_cli("--plan", str(write_plan(tmp_path, make_plan())), "--write")

    assert run.returncode == 5
    assert run.stdout == ""
    assert "GitHub Actions" in run.stderr


def test_cli_write_without_a_token_exits_five(tmp_path):
    run = run_cli(
        "--plan", str(write_plan(tmp_path, make_plan())), "--write", GITHUB_ACTIONS="true"
    )

    assert run.returncode == 5
    assert run.stdout == ""


def test_cli_write_applies_the_plan_and_exits_zero(tmp_path, monkeypatch):
    client = FakeClient()
    plan = make_plan([{"kind": "set_labels", "add": ["risk:low"], "remove": []}])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_apply.main(["--plan", str(write_plan(tmp_path, plan)), "--write"], client=client)

    assert code == 0
    assert len(client.calls) == 2


def test_cli_write_lists_every_result_and_exits_one_on_failure(tmp_path, monkeypatch, capsys):
    def handler(method, path, payload):
        if method == "POST" and path == LABELS_PATH:
            raise pr_github.FetchError("server error", status=500)
        return pr_github.Response(status=200)

    client = FakeClient(handler)
    plan = make_plan(
        [
            {"kind": "set_labels", "add": ["risk:low"], "remove": []},
            {"kind": "request_reviewer", "login": BOT},
        ]
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_apply.main(["--plan", str(write_plan(tmp_path, plan)), "--write"], client=client)

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert [result["kind"] for result in payload["results"]] == ["set_labels", "request_reviewer"]
    assert [result["ok"] for result in payload["results"]] == [False, True]


def test_cli_write_rejects_an_unsupported_action_before_a_call(tmp_path, monkeypatch):
    client = FakeClient()
    plan = make_plan([{"kind": "enable_auto_merge", "method": "merge", "delete_branch": True}])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_apply.main(["--plan", str(write_plan(tmp_path, plan)), "--write"], client=client)

    assert code == 3
    assert client.calls == []


def test_cli_missing_plan_file_exits_three(tmp_path):
    run = run_cli("--plan", str(tmp_path / "missing.json"))

    assert run.returncode == 3
    assert "--plan" in run.stderr


def test_cli_invalid_json_exits_three(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")

    run = run_cli("--plan", str(path))

    assert run.returncode == 3


def test_cli_unsupported_action_exits_three(tmp_path):
    plan = make_plan([{"kind": "approve"}])

    run = run_cli("--plan", str(write_plan(tmp_path, plan)))

    assert run.returncode == 3
    assert "unsupported action" in run.stderr


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--write"],
        ["--plan"],
        ["--plan", "p.json", "--unknown"],
        ["--plan=p.json", "--write=yes"],
    ],
)
def test_cli_usage_errors_exit_two(arguments):
    run = run_cli(*arguments)

    assert run.returncode == 2
    assert run.stdout == ""
    assert "usage:" in run.stderr


def test_cli_help_is_short_and_documents_exit_codes():
    run = run_cli("--help")

    assert run.returncode == 0
    assert run.stderr == ""
    assert len(run.stdout.splitlines()) < 25
    assert "usage:" in run.stdout
    assert "exit:" in run.stdout
    assert run.stdout.count("python3 scripts/pr_apply.py") == 2
