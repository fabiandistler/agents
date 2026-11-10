"""Tests for the three stages of issue_triage.py against a fake GitHub client."""

from __future__ import annotations

import json
from pathlib import Path

import issue_triage
import pr_cli
import pytest
from issue_triage_policy import COMMENT_MARKER
from pr_github_client import FetchError, Response

REPO = "fabiandistler/agents"
NUMBER = 735
ISSUE_PATH = f"/repos/{REPO}/issues/{NUMBER}"
TOKEN = "oauth-token-for-tests"  # noqa: S105 -- a fake value
ANSWER = json.dumps(
    {
        "category": "bug",
        "state": "needs-info",
        "summary": "The steps are missing.",
        "questions": ["Which check fails?"],
    }
)


def api_issue(labels: tuple[str, ...] = ("needs-triage",), **overrides: object) -> dict:
    payload = {
        "number": NUMBER,
        "state": "open",
        "title": "loop.sh writes an empty block reason",
        "body": "It breaks.",
        "user": {"login": "reporter", "type": "User"},
        "author_association": "OWNER",
        "labels": [{"name": label} for label in labels],
    }
    payload.update(overrides)
    return payload


class FakeClient:
    """Serves one issue and its comments; records every write."""

    def __init__(self, issue: dict | None, comments: list[dict] | None = None, fail_writes=False):
        self.issue = issue
        self.comments = comments or []
        self.fail_writes = fail_writes
        self.writes: list[tuple[str, str, dict]] = []

    def get(self, path, params=None, accept=None):
        if path == ISSUE_PATH:
            return Response(200, json.dumps(self.issue).encode())
        if path == f"{ISSUE_PATH}/comments":
            page = (params or {}).get("page", 1)
            items = self.comments if page == 1 else []
            return Response(200, json.dumps(items).encode())
        raise FetchError(f"unexpected GET {path}", status=404)

    def _write(self, method: str, path: str, payload: dict | None):
        if self.fail_writes:
            raise FetchError(f"GitHub API returned 403 for {path}", status=403)
        self.writes.append((method, path, payload or {}))
        return Response(200, b"{}")

    def post(self, path, payload=None):
        return self._write("POST", path, payload)

    def delete(self, path, payload=None):
        return self._write("DELETE", path, payload)


def assessed(client: FakeClient, trigger: str = "opened") -> dict:
    return issue_triage.fetch_context(client, REPO, NUMBER, trigger)


def test_assess_collects_the_issue_and_decides(tmp_path: Path, capsys):
    bot = {"user": {"login": "github-actions[bot]"}, "body": f"{COMMENT_MARKER}\nold"}
    client = FakeClient(api_issue(labels=("needs-triage", "bug")), [bot])
    output = tmp_path / "context.json"
    argv = ["assess", "--repo", REPO, "--issue", str(NUMBER), "--trigger", "opened"]
    code = issue_triage.main([*argv, "--output", str(output)], client=client)
    assert code == pr_cli.EXIT_OK
    context = json.loads(output.read_text(encoding="utf-8"))
    assert context["eligible"] is True
    assert context["states"] == ["needs-triage"]
    assert context["other_labels"] == ["bug"]
    assert context["bot_triages"] == 1
    assert context["author"] == "reporter"
    assert json.loads(capsys.readouterr().out) == {
        "number": NUMBER,
        "eligible": True,
        "skip_reason": None,
    }


def test_assess_skips_an_outside_author():
    context = assessed(FakeClient(api_issue(author_association="NONE")))
    assert context["eligible"] is False
    assert "write access" in context["skip_reason"]


def test_triage_parses_a_valid_answer(tmp_path: Path):
    context = assessed(FakeClient(api_issue()))
    result = issue_triage.triage(context, tmp_path, transport=lambda _r: ANSWER, token=TOKEN)
    assert result["status"] == "ok"
    assert result["state"] == "needs-info"


def test_triage_without_token_or_with_a_failed_call_is_unavailable(tmp_path, monkeypatch):
    context = assessed(FakeClient(api_issue()))
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    assert issue_triage.triage(context, tmp_path)["status"] == "unavailable"

    def failing(_request):
        raise issue_triage.ProviderError("the claude CLI timed out")

    assert issue_triage.triage(context, tmp_path, failing, TOKEN)["status"] == "unavailable"


def test_triage_of_an_off_format_answer_is_invalid(tmp_path: Path):
    context = assessed(FakeClient(api_issue()))
    result = issue_triage.triage(context, tmp_path, lambda _r: "I think it's fine", TOKEN)
    assert result == {"schema_version": 1, "number": NUMBER, "status": "invalid"}


def test_triage_refuses_an_ineligible_context(tmp_path: Path):
    context = assessed(FakeClient(api_issue(state="closed")))
    with pytest.raises(pr_cli.InputError, match="not eligible"):
        issue_triage.triage(context, tmp_path, lambda _r: ANSWER, TOKEN)


def write_inputs(tmp_path: Path, context: dict, result: dict) -> list[str]:
    (tmp_path / "context.json").write_text(json.dumps(context), encoding="utf-8")
    (tmp_path / "triage.json").write_text(json.dumps(result), encoding="utf-8")
    return [
        "publish",
        "--repo",
        REPO,
        "--context",
        str(tmp_path / "context.json"),
        "--triage",
        str(tmp_path / "triage.json"),
    ]


def triaged(client: FakeClient, tmp_path: Path, answer: str = ANSWER) -> tuple[dict, dict]:
    context = assessed(client)
    return context, issue_triage.triage(context, tmp_path, lambda _r: answer, TOKEN)


def test_publish_without_write_only_plans(tmp_path: Path, capsys):
    client = FakeClient(api_issue())
    argv = write_inputs(tmp_path, *triaged(client, tmp_path))
    assert issue_triage.main(argv, client=client) == pr_cli.EXIT_OK
    planned = json.loads(capsys.readouterr().out)
    assert planned["written"] is False
    assert planned["add"] == ["needs-info"]
    assert planned["remove"] == ["needs-triage"]
    assert client.writes == []


def test_publish_write_posts_the_comment_before_moving_the_label(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = FakeClient(api_issue())
    argv = write_inputs(tmp_path, *triaged(client, tmp_path))
    assert issue_triage.main([*argv, "--write"], client=client) == pr_cli.EXIT_OK
    assert [(method, path) for method, path, _ in client.writes] == [
        ("POST", f"{ISSUE_PATH}/comments"),
        ("DELETE", f"{ISSUE_PATH}/labels/needs-triage"),
        ("POST", f"{ISSUE_PATH}/labels"),
    ]
    assert client.writes[0][2]["body"].startswith(COMMENT_MARKER)
    assert client.writes[2][2] == {"labels": ["needs-info"]}


def test_publish_writes_nothing_when_the_maintainer_moved_the_issue_meanwhile(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    context, result = triaged(FakeClient(api_issue()), tmp_path)
    moved = FakeClient(api_issue(labels=("ready-for-agent",)))
    argv = write_inputs(tmp_path, context, result)
    assert issue_triage.main([*argv, "--write"], client=moved) == pr_cli.EXIT_OK
    assert moved.writes == []


@pytest.mark.parametrize("status", ["unavailable", "invalid"])
def test_publish_writes_nothing_for_a_failed_triage(tmp_path, monkeypatch, status):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = FakeClient(api_issue())
    context = assessed(client)
    result = {"schema_version": 1, "number": NUMBER, "status": status}
    argv = write_inputs(tmp_path, context, result)
    assert issue_triage.main([*argv, "--write"], client=client) == pr_cli.EXIT_OK
    assert client.writes == []


def test_publish_refuses_an_artifact_for_another_issue(tmp_path: Path):
    client = FakeClient(api_issue())
    context, result = triaged(client, tmp_path)
    argv = write_inputs(tmp_path, context, {**result, "number": NUMBER + 1})
    assert issue_triage.main(argv, client=client) == pr_cli.EXIT_BAD_INPUT


def test_write_outside_actions_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    client = FakeClient(api_issue())
    argv = write_inputs(tmp_path, *triaged(client, tmp_path))
    assert issue_triage.main([*argv, "--write"], client=client) == pr_cli.EXIT_OUTSIDE_ACTIONS
    assert client.writes == []


def test_a_failed_write_is_an_action_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = FakeClient(api_issue(), fail_writes=True)
    argv = write_inputs(tmp_path, *triaged(client, tmp_path))
    assert issue_triage.main([*argv, "--write"], client=client) == pr_cli.EXIT_ACTION_FAILED


def test_a_failed_fetch_is_a_fetch_failure(tmp_path: Path):
    client = FakeClient(api_issue())
    client.issue = None  # the issue GET then returns JSON null
    argv = ["assess", "--repo", REPO, "--issue", str(NUMBER), "--trigger", "opened"]
    output = str(tmp_path / "c.json")
    assert issue_triage.main([*argv, "--output", output], client=client) == (
        pr_cli.EXIT_FETCH_FAILED
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["label"],
        ["assess", "--repo", REPO, "--issue", "1", "--trigger", "push", "--output", "c"],
        ["assess", "--repo", REPO, "--issue", "0", "--trigger", "opened", "--output", "c"],
        ["assess", "--repo", "not-a-repo", "--issue", "1", "--trigger", "opened", "--output", "c"],
        ["triage", "--context", "c.json"],
    ],
)
def test_bad_arguments_are_usage_errors(argv: list[str]):
    assert issue_triage.main(argv) == pr_cli.EXIT_USAGE


def test_help_lists_every_stage(capsys):
    assert issue_triage.main(["--help"]) == pr_cli.EXIT_OK
    out = capsys.readouterr().out
    assert all(stage in out for stage in ("assess", "triage", "publish"))


def needs_info_client(**overrides: object) -> FakeClient:
    return FakeClient(api_issue(labels=("needs-info",), **overrides))


def test_a_reply_without_a_triage_run_moves_needs_info_back_without_comment(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = needs_info_client(author_association="NONE")
    context = assessed(client, "reply")
    assert (context["eligible"], context["requeue"]) == (False, True)
    (tmp_path / "context.json").write_text(json.dumps(context), encoding="utf-8")
    argv = ["publish", "--repo", REPO, "--context", str(tmp_path / "context.json"), "--write"]
    assert issue_triage.main(argv, client=client) == pr_cli.EXIT_OK
    assert [(method, path) for method, path, _ in client.writes] == [
        ("DELETE", f"{ISSUE_PATH}/labels/needs-info"),
        ("POST", f"{ISSUE_PATH}/labels"),
    ]
    assert client.writes[1][2] == {"labels": ["needs-triage"]}


def test_a_reply_with_a_failed_triage_still_requeues(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = needs_info_client()
    context = assessed(client, "reply")
    result = {"schema_version": 1, "number": NUMBER, "status": "unavailable"}
    argv = write_inputs(tmp_path, context, result)
    assert issue_triage.main([*argv, "--write"], client=client) == pr_cli.EXIT_OK
    assert client.writes[-1][2] == {"labels": ["needs-triage"]}
    assert all(not path.endswith("/comments") for _, path, _ in client.writes)


def test_a_reply_the_model_still_finds_unclear_keeps_needs_info_and_comments(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = needs_info_client()
    context = assessed(client, "reply")
    result = issue_triage.triage(context, tmp_path, lambda _r: ANSWER, TOKEN)
    argv = write_inputs(tmp_path, context, result)
    assert issue_triage.main([*argv, "--write"], client=client) == pr_cli.EXIT_OK
    assert [(method, path) for method, path, _ in client.writes] == [
        ("POST", f"{ISSUE_PATH}/comments")
    ]
