"""Tests for factory_failure.py: fetching a failed run and applying its plan."""

import json

import factory_failure
import factory_failure_policy as policy
import pr_cli
import pr_github_client
import pytest
from pr_github_fake import json_response

REPO = "fabiandistler/agents"
RUN_ID = 111
JOB_ID = 222
RUN_PATH = f"/repos/{REPO}/actions/runs/{RUN_ID}"
JOBS_PATH = f"{RUN_PATH}/attempts/1/jobs"
ANNOTATIONS_PATH = f"/repos/{REPO}/check-runs/{JOB_ID}/annotations"
ISSUES_PATH = f"/repos/{REPO}/issues"
LABELS_PATH = f"/repos/{REPO}/labels"


def api_run(**overrides) -> dict:
    run = {
        "path": ".github/workflows/implementer.yml",
        "name": "implementer",
        "html_url": f"https://github.com/{REPO}/actions/runs/{RUN_ID}",
        "run_attempt": 1,
        "display_title": "Add a thing",
        "conclusion": "failure",
    }
    return {**run, **overrides}


JOBS = {
    "total_count": 1,
    "jobs": [
        {
            "id": JOB_ID,
            "name": "implement",
            "conclusion": "failure",
            "steps": [
                {"name": "Run Claude", "conclusion": "success"},
                {"name": "Report the run", "conclusion": "failure"},
            ],
        }
    ],
}
ANNOTATIONS = [
    {"annotation_level": "failure", "message": "RUN FAILED: claim (HTTP 500)"},
    {"annotation_level": "failure", "message": "Process completed with exit code 1."},
]
MARKER = policy.signature(
    ".github/workflows/implementer.yml", "implement", "Report the run", ANNOTATIONS[0]["message"]
)["marker"]


def api_issue(number: int, state: str = "open", body: str = MARKER, **extra) -> dict:
    return {
        "number": number,
        "state": state,
        "user": {"login": policy.AUTHOR},
        "body": body,
        "labels": [{"name": policy.LABEL}],
        **extra,
    }


class FakeClient:
    """Routes the GETs the Fix task makes; records every write."""

    def __init__(self, run=None, issues=(), comments=None, single=None, label_status=201):
        self.routes = {
            RUN_PATH: run or api_run(),
            JOBS_PATH: JOBS,
            ANNOTATIONS_PATH: ANNOTATIONS,
            ISSUES_PATH: list(issues),
        }
        for number, entries in (comments or {}).items():
            self.routes[f"{ISSUES_PATH}/{number}/comments"] = entries
        for number, issue in (single or {}).items():
            self.routes[f"{ISSUES_PATH}/{number}"] = issue
        self.label_status = label_status
        self.gets: list[tuple[str, dict]] = []
        self.writes: list[tuple[str, str, dict]] = []

    def get(self, path, params=None, accept=None):
        self.gets.append((path, dict(params or {})))
        if path not in self.routes:
            raise AssertionError(f"unexpected GET {path}")
        return json_response(self.routes[path])

    def post(self, path, payload=None):
        self.writes.append(("POST", path, dict(payload or {})))
        if path == LABELS_PATH and self.label_status == 422:
            raise pr_github_client.FetchError("exists", status=422)
        return json_response({}, status=201)


def run_main(client, *extra) -> int:
    argv = ["--repo", REPO, "--run-id", str(RUN_ID), *extra]
    return factory_failure.main(argv, client=client, today="2026-11-13")


def test_a_dry_run_prints_the_plan_and_writes_nothing(capsys):
    client = FakeClient()
    assert factory_failure.main(["--repo", REPO, "--run-id", str(RUN_ID)], client=client) == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["written"] is False
    assert planned["action"]["kind"] == "create_issue"
    assert planned["signature"]["marker"] == MARKER
    assert client.writes == []


def test_the_issue_search_asks_for_the_bots_labelled_issues(capsys):
    client = FakeClient()
    factory_failure.main(["--repo", REPO, "--run-id", str(RUN_ID)], client=client)
    params = next(params for path, params in client.gets if path == ISSUES_PATH)
    assert params["labels"] == policy.LABEL
    assert params["state"] == "all"
    assert params["creator"] == policy.AUTHOR


@pytest.mark.parametrize("label_status", [201, 422])
def test_write_creates_the_label_idempotently_then_the_issue(monkeypatch, capsys, label_status):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = FakeClient(label_status=label_status)
    assert run_main(client, "--write") == pr_cli.EXIT_OK
    assert [(method, path) for method, path, _ in client.writes] == [
        ("POST", LABELS_PATH),
        ("POST", ISSUES_PATH),
    ]
    assert client.writes[0][2]["name"] == policy.LABEL
    issue = client.writes[1][2]
    assert issue["labels"] == ["factory-failure", "bug", "needs-triage"]
    assert MARKER in issue["body"]
    assert json.loads(capsys.readouterr().out)["written"] is True


def test_write_re_reads_before_writing(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = FakeClient()
    run_main(client, "--write")
    assert [path for path, _ in client.gets].count(ISSUES_PATH) == 2


def test_write_comments_on_the_open_match(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = FakeClient(issues=[api_issue(5)], comments={5: []})
    assert run_main(client, "--write") == pr_cli.EXIT_OK
    assert [(method, path) for method, path, _ in client.writes] == [
        ("POST", f"{ISSUES_PATH}/5/comments")
    ]


def test_a_recorded_run_writes_nothing(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    record = {"user": {"login": policy.AUTHOR}, "body": f"<!-- factory-failure-run:{RUN_ID}/1 -->"}
    client = FakeClient(issues=[api_issue(5)], comments={5: [record]})
    assert run_main(client, "--write") == pr_cli.EXIT_OK
    assert client.writes == []


def test_pull_requests_in_the_issue_list_are_ignored(capsys):
    pull = api_issue(9, pull_request={"url": "x"})
    client = FakeClient(issues=[pull])
    factory_failure.main(["--repo", REPO, "--run-id", str(RUN_ID)], client=client)
    assert json.loads(capsys.readouterr().out)["action"]["kind"] == "create_issue"


def test_a_fix_related_run_comments_on_its_issue(capsys):
    run = api_run(display_title="implementer: issue #7")
    client = FakeClient(run=run, single={7: api_issue(7, body="other")}, comments={7: []})
    factory_failure.main(["--repo", REPO, "--run-id", str(RUN_ID)], client=client)
    action = json.loads(capsys.readouterr().out)["action"]
    assert action == {**action, "kind": "comment", "number": 7}


def test_a_successful_run_fetches_nothing_more(capsys):
    client = FakeClient(run=api_run(conclusion="success"))
    factory_failure.main(["--repo", REPO, "--run-id", str(RUN_ID)], client=client)
    assert [path for path, _ in client.gets] == [RUN_PATH]
    assert json.loads(capsys.readouterr().out)["action"] is None


def test_write_outside_actions_is_refused(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    client = FakeClient()
    assert run_main(client, "--write") == pr_cli.EXIT_OUTSIDE_ACTIONS
    assert client.gets == [] and client.writes == []


@pytest.mark.parametrize(
    "argv",
    [
        ["--repo", REPO],
        ["--run-id", "1"],
        ["--repo", "bad", "--run-id", "1"],
        ["--repo", REPO, "--run-id", "x"],
        ["--repo", REPO, "--run-id", "0"],
    ],
)
def test_bad_arguments_are_usage_errors(argv, capsys):
    assert factory_failure.main(argv, client=FakeClient()) == pr_cli.EXIT_USAGE


def test_help_exits_zero(capsys):
    assert factory_failure.main(["--help"]) == pr_cli.EXIT_OK
    assert "usage: factory_failure.py" in capsys.readouterr().out


def test_a_missing_token_exits_five(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert factory_failure.main(["--repo", REPO, "--run-id", "1"]) == pr_cli.EXIT_MISSING_TOKEN
