"""Closing intent must match native links without mistaking examples for intent."""

import json
from types import SimpleNamespace

import check_pr_issue_links as links
import pytest

REPO = "owner/repo"


def test_comma_joined_reference_names_unlinked_issue_and_suggests_full_syntax():
    errors = links.issue_link_errors("Closes #1, #2", REPO, {"owner/repo#1"}, default_base=True)
    assert any("#2" in error and "Unlinked" in error for error in errors)
    assert any("Closes #1, closes #2" in error for error in errors)


@pytest.mark.parametrize(
    "keyword",
    ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"],
)
def test_supported_keywords_case_and_colon(keyword):
    assert (
        links.issue_link_errors(
            f"This {keyword.upper()}: #1, closes Other/Repo#2.",
            REPO,
            {"owner/repo#1", "other/repo#2"},
            default_base=True,
        )
        == []
    )


def test_url_reference_and_repeated_closing_keywords():
    assert (
        links.issue_link_errors(
            "Closes https://github.com/owner/repo/issues/1 and fixes #2",
            REPO,
            {"owner/repo#1", "owner/repo#2"},
            default_base=True,
        )
        == []
    )


def test_list_continuations_with_and_need_own_keywords_even_if_manually_linked():
    errors = links.issue_link_errors(
        "Closes #1, #2 and #3",
        REPO,
        {"owner/repo#1", "owner/repo#2", "owner/repo#3"},
        default_base=True,
    )
    assert len(errors) == 2
    assert "#2" in errors[0] and "#3" in errors[1]


def test_no_issue_requires_explicit_statement_and_cannot_hide_existing_links():
    assert (
        links.issue_link_errors("No issue: documentation only.", REPO, set(), default_base=True)
        == []
    )
    assert links.issue_link_errors("No issue.", REPO, {"owner/repo#1"}, default_base=True)
    assert links.issue_link_errors("Some changes.", REPO, set(), default_base=True)


def test_code_and_html_comment_examples_do_not_create_closing_intent():
    body = "<!-- Closes #10 -->\n```md\nCloses #11\n````\n`closes #12`\n    closes #13\nNo issue."
    assert links.issue_link_errors(body, REPO, set(), default_base=True) == []


def test_nondefault_base_skips_native_comparison_but_keeps_syntax_check():
    assert links.issue_link_errors("Closes #1", REPO, set(), default_base=False) == []
    assert links.issue_link_errors("Closes #1, #2", REPO, set(), default_base=False)


def page(numbers=(), *, more=False, cursor=None, body="Closes #1", head="abc"):
    return {
        "data": {
            "repository": {
                "defaultBranchRef": {"name": "main"},
                "pullRequest": {
                    "body": body,
                    "baseRefName": "main",
                    "headRefOid": head,
                    "closingIssuesReferences": {
                        "nodes": [
                            {"number": n, "repository": {"nameWithOwner": REPO}} for n in numbers
                        ],
                        "pageInfo": {"hasNextPage": more, "endCursor": cursor},
                    },
                },
            }
        }
    }


def test_fetch_paginates_without_losing_links(monkeypatch):
    queries = []
    responses = iter([page([1], more=True, cursor="next"), page([2])])
    monkeypatch.setattr(
        links, "_query", lambda variables: (queries.append(variables), next(responses))[1]
    )
    _, linked = links.read_pull_request(REPO, 1)
    assert linked == {"owner/repo#1", "owner/repo#2"}
    assert [query["cursor"] for query in queries] == [None, "next"]


@pytest.mark.parametrize("second", [page([2], head="changed"), page([2], body="No issue.")])
def test_changing_snapshot_is_an_error(monkeypatch, second):
    responses = iter([page([1], more=True, cursor="next"), second])
    monkeypatch.setattr(links, "_query", lambda _: next(responses))
    with pytest.raises(links.GitHubError, match="changed"):
        links.read_pull_request(REPO, 1)


@pytest.mark.parametrize(
    "payload", [{"data": {"repository": None}}, page([True]), page([], more=True)]
)
def test_invalid_api_shape_and_pagination_fail_closed(monkeypatch, payload):
    monkeypatch.setattr(links, "_query", lambda _: payload)
    with pytest.raises(links.GitHubError):
        links.read_pull_request(REPO, 1)


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(returncode=1, stdout=""),
        SimpleNamespace(returncode=0, stdout="not json"),
        SimpleNamespace(returncode=0, stdout='{"errors": [{"message":"denied"}]}'),
    ],
)
def test_api_failures_are_not_treated_as_empty_link_sets(monkeypatch, response):
    monkeypatch.setattr(links.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(links.subprocess, "run", lambda *args, **kwargs: response)
    with pytest.raises(links.GitHubError):
        links._query({})


def test_cli_reports_policy_failures_and_full_artifact(monkeypatch, tmp_path, capsys):
    snapshot = {
        "body": "Closes #1, #2",
        "baseRefName": "main",
        "defaultBranch": "main",
        "headRefOid": "abc",
    }
    monkeypatch.setattr(links, "read_pull_request", lambda *args: (snapshot, {"owner/repo#1"}))
    output = tmp_path / "links.json"
    assert links.main(["--repo", REPO, "--pr", "1", "--output", str(output)]) == 1
    assert json.loads(output.read_text())["status"] == "fail"
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "fail"
    assert "#2" in captured.err
    assert links.main(["--repo", REPO, "--pr", "1", "--expected-head", "old"]) == 3


def test_help_is_bounded_and_usage_errors_are_distinct(capsys):
    with pytest.raises(SystemExit) as helped:
        links.main(["--help"])
    assert helped.value.code == 0
    assert len(capsys.readouterr().out.splitlines()) <= 25
    with pytest.raises(SystemExit) as invalid:
        links.main(["--repo", "invalid", "--pr", "0"])
    assert invalid.value.code == 2


def test_invalid_native_repository_is_an_api_error(monkeypatch):
    response = page([1])
    response["data"]["repository"]["pullRequest"]["closingIssuesReferences"]["nodes"][0][
        "repository"
    ]["nameWithOwner"] = "invalid"
    monkeypatch.setattr(links, "_query", lambda _: response)
    with pytest.raises(links.GitHubError):
        links.read_pull_request(REPO, 1)


def test_report_write_failure_has_its_own_exit_code(monkeypatch, tmp_path, capsys):
    snapshot = {
        "body": "No issue.",
        "baseRefName": "main",
        "defaultBranch": "main",
        "headRefOid": "abc",
    }
    monkeypatch.setattr(links, "read_pull_request", lambda *args: (snapshot, set()))
    assert links.main(["--repo", REPO, "--pr", "1", "--output", str(tmp_path)]) == 4
    assert "Cannot write" in capsys.readouterr().err
