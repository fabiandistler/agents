"""Tests for ``pr_github.py --linked-issues``: the issues a pull request closes.

Every test injects ``pr_github_fake.FakeClient``; none performs a network call.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pr_github
import pr_github_client
import pytest
from pr_github_fake import (
    ISSUES_PREFIX,
    NUMBER,
    REPO,
    SCRIPT,
    FakeClient,
    api_issue,
    fetch,
    json_response,
    pull_request,
    text_response,
)


def fetch_linked(client: FakeClient) -> dict:
    return pr_github.fetch_context(REPO, NUMBER, client=client, linked_issues=True)


def test_without_the_flag_the_context_has_no_field_and_fetches_no_issue():
    client = FakeClient(pull_request(body="Closes #7"), issues={7: api_issue(7)})

    context = fetch(client)

    assert "linked_issues" not in context
    assert client.issue_calls() == []


def test_a_same_repository_closing_reference_carries_number_title_and_body():
    issue = api_issue(7, title="Add the flag", body="The ticket text.")
    client = FakeClient(pull_request(body="Closes #7"), issues={7: issue})

    context = fetch_linked(client)

    assert context["linked_issues"] == [
        {"number": 7, "status": "ok", "title": "Add the flag", "body": "The ticket text."}
    ]
    # One REST GET through the injected client; no GraphQL endpoint is asked.
    assert [call.path for call in client.issue_calls()] == [f"{ISSUES_PREFIX}7"]
    assert all(call.path.startswith("/repos/") for call in client.calls)


def test_references_to_other_repositories_are_not_fetched():
    body = "Closes other/repo#8\nFixes https://github.com/other/repo/issues/9"
    client = FakeClient(pull_request(body=body))

    context = fetch_linked(client)

    assert context["linked_issues"] == []
    assert client.issue_calls() == []


def test_a_reference_that_names_a_pull_request_is_not_an_issue():
    pull = {**api_issue(10), "pull_request": {"url": "https://api.github.com/x"}}
    client = FakeClient(
        pull_request(body="Closes #10, closes #11"), issues={10: pull, 11: api_issue(11)}
    )

    context = fetch_linked(client)

    assert [issue["number"] for issue in context["linked_issues"]] == [11]


def test_a_pull_request_without_a_closing_reference_gets_an_empty_list():
    client = FakeClient(pull_request(body="Mentions #7 but closes nothing."))

    context = fetch_linked(client)

    assert context["linked_issues"] == []
    assert client.issue_calls() == []


def test_references_are_deduplicated_ascending_and_at_most_three():
    body = "Closes #9, closes #2\nFixes #5\nResolves #2\nCloses #1"
    client = FakeClient(pull_request(body=body), issues={n: api_issue(n) for n in (1, 2, 5, 9)})

    context = fetch_linked(client)

    assert [issue["number"] for issue in context["linked_issues"]] == [1, 2, 5]
    assert [call.path for call in client.issue_calls()] == [
        f"{ISSUES_PREFIX}{n}" for n in (1, 2, 5)
    ]


@pytest.mark.parametrize("association", ["CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "NONE", None])
def test_an_issue_by_an_outside_author_carries_no_text(association):
    issue = api_issue(7, title="OUTSIDE-TITLE", body="OUTSIDE-BODY", association=association)
    client = FakeClient(pull_request(body="Closes #7"), issues={7: issue})

    context = fetch_linked(client)

    assert context["linked_issues"] == [
        {"number": 7, "status": "outside_author", "title": "", "body": ""}
    ]
    assert "OUTSIDE-" not in json.dumps(context)


@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_an_issue_by_a_trusted_author_is_shown(association):
    client = FakeClient(
        pull_request(body="Closes #7"), issues={7: api_issue(7, association=association)}
    )

    assert fetch_linked(client)["linked_issues"][0]["status"] == "ok"


@pytest.mark.parametrize(
    ("response", "status"),
    [
        (None, "404"),
        (pr_github_client.FetchError("GitHub API returned 403", status=403), "403"),
        (pr_github_client.FetchError("GitHub API returned 502", status=502), "502"),
        (text_response("SECRET-ISSUE-TEXT not json"), "none"),
        (json_response(["SECRET-ISSUE-TEXT"]), "200"),
    ],
)
def test_a_failed_issue_fetch_marks_it_unavailable_and_logs_number_and_status(
    response, status, capsys
):
    errors = {}
    issues = {8: api_issue(8)}
    if isinstance(response, Exception):
        errors[f"{ISSUES_PREFIX}7"] = response
    elif response is not None:
        issues[7] = response
    client = FakeClient(pull_request(body="Closes #7, closes #8"), issues=issues, errors=errors)

    context = fetch_linked(client)

    assert context["linked_issues"][0] == {
        "number": 7,
        "status": "unavailable",
        "title": "",
        "body": "",
    }
    assert context["linked_issues"][1]["status"] == "ok"
    err = capsys.readouterr().err
    assert err == f"pr_github.py: linked issue #7 unavailable (HTTP {status})\n"


def test_other_exceptions_from_the_issue_fetch_are_not_caught():
    client = FakeClient(
        pull_request(body="Closes #7"), errors={f"{ISSUES_PREFIX}7": RuntimeError("bug")}
    )

    with pytest.raises(RuntimeError, match="bug"):
        fetch_linked(client)


def test_the_cli_passes_the_flag_and_exits_zero_on_an_unavailable_issue(
    tmp_path, monkeypatch, capsys
):
    client = FakeClient(pull_request(body="Closes #7"))
    monkeypatch.setattr(pr_github, "GitHubClient", lambda token: client)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    output = tmp_path / "context.json"

    code = pr_github.main(
        ["--pr", str(NUMBER), "--repo", REPO, "--linked-issues", "--output", str(output)]
    )

    assert code == 0
    context = json.loads(output.read_text(encoding="utf-8"))
    assert context["linked_issues"][0]["status"] == "unavailable"
    captured = capsys.readouterr()
    assert json.loads(captured.out)["linked_issues"] == 1
    assert captured.err == "pr_github.py: linked issue #7 unavailable (HTTP 404)\n"


def test_the_cli_without_the_flag_writes_no_field(tmp_path, monkeypatch, capsys):
    client = FakeClient(pull_request(body="Closes #7"), issues={7: api_issue(7)})
    monkeypatch.setattr(pr_github, "GitHubClient", lambda token: client)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    output = tmp_path / "context.json"

    assert pr_github.main(["--pr", str(NUMBER), "--repo", REPO, "--output", str(output)]) == 0

    assert "linked_issues" not in json.loads(output.read_text(encoding="utf-8"))
    assert "linked_issues" not in json.loads(capsys.readouterr().out)
    assert client.issue_calls() == []


def test_the_usage_documents_the_flag_and_the_field():
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and script path, no shell
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--linked-issues" in result.stdout
    assert '"linked_issues"' in result.stdout
    assert "outside_author" in result.stdout
