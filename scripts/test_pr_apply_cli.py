"""Tests for the command line of scripts/pr_apply.py."""

from __future__ import annotations

import json

import pr_apply
import pr_github_client
import pytest
from pr_apply_testkit import (
    BOT,
    ISSUE_COMMENTS_PATH,
    LABELS_PATH,
    NUMBER,
    REPO,
    FakeClient,
    make_plan,
    run_cli,
    write_plan,
)

# --- CLI ---------------------------------------------------------------------


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
            raise pr_github_client.FetchError("server error", status=500)
        return pr_github_client.Response(status=200)

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
    plan = make_plan([{"kind": "merge"}])
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
