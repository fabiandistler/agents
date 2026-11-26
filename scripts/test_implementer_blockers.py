"""The implementer claim's blocked gate: "Blocked by" lines and native dependencies."""

from __future__ import annotations

import implementer_claim
import pr_github_client
import pytest
from test_implementer_claim import (
    BRANCH,
    COMMENTS,
    DEPENDENCIES,
    ISSUE_PATH,
    REPO,
    FakeGitHub,
    claim,
    http_error,
)
from test_implementer_intake_gates import OWNED_ISSUE, assert_waits_before_any_branch, blocker

# Gate 1: blocked.


@pytest.mark.parametrize(
    "issue",
    [
        blocker(state="open", state_reason=None),
        blocker(state_reason="not_planned"),
        blocker(state_reason="duplicate"),
        blocker(state_reason=None),
        blocker(pull_request={"url": "x"}),
        blocker(repository_url="https://api.github.com/repos/other/repo"),
    ],
    ids=["open", "not-planned", "duplicate", "closed-no-reason", "pull-request", "transferred"],
)
def test_a_declared_blocker_that_is_not_done_stops_the_run(issue):
    fake = FakeGitHub(issue_body="Blocked by: #3", blocker_issues={3: issue})
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.BLOCKED
    assert outcome.branch == BRANCH
    assert outcome.blockers == (3,)
    assert "Blocked by #3." in assert_waits_before_any_branch(fake)


def test_a_blocker_closed_as_not_planned_is_named_as_still_blocking():
    fake = FakeGitHub(
        issue_body="Blocked by: #3", blocker_issues={3: blocker(state_reason="not_planned")}
    )
    claim(fake)
    assert "closed as not planned still blocks" in fake.writes[0][2]["body"].replace("\n", " ")


@pytest.mark.parametrize("status", [404, 410], ids=["missing", "deleted"])
def test_a_blocker_that_cannot_be_read_blocks(status):
    path = f"/repos/{REPO}/issues/3"
    fake = FakeGitHub(issue_body="Blocked by: #3", errors={("GET", path): http_error(status, path)})
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.BLOCKED
    assert outcome.blockers == (3,)


def test_a_completed_blocker_lets_the_claim_proceed():
    fake = FakeGitHub(issue_body="Blocked by: #3", blocker_issues={3: blocker()})
    assert claim(fake).outcome == implementer_claim.CLAIMED


def test_none_means_no_blockers_and_no_issue_is_read():
    fake = FakeGitHub(issue_body="## Blocked by\n\nNone (can start immediately)\n")
    assert claim(fake).outcome == implementer_claim.CLAIMED


def test_several_blockers_are_named_sorted():
    fake = FakeGitHub(
        issue_body="Blocked by: #9, #3",
        blocker_issues={3: blocker(state="open", state_reason=None), 9: blocker(state="open")},
    )
    outcome = claim(fake)
    assert outcome.blockers == (3, 9)
    assert "#3, #9" in fake.writes[0][2]["body"]


@pytest.mark.parametrize(
    "ticket_text",
    ["## Blocked by\n\nAdd the parser\n", "Blocked by: other/repo#3", "## Blocked by\n"],
    ids=["title-only", "cross-repo", "empty-section"],
)
def test_an_unresolvable_entry_fails_closed(ticket_text):
    fake = FakeGitHub(issue_body=ticket_text)
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.BLOCKED
    assert outcome.blockers == ()
    assert outcome.unresolved_blockers == 1
    comment = assert_waits_before_any_branch(fake)
    assert "1 " in comment
    assert "`#<n>`" in comment


@pytest.mark.parametrize(
    ("edge", "blockers", "unresolved"),
    [
        (blocker(number=4, state="open", state_reason=None), (4,), 0),
        (blocker(number=4, state_reason="not_planned"), (4,), 0),
        (
            blocker(
                number=4,
                state="open",
                state_reason=None,
                repository_url="https://api.github.com/repos/other/repo",
            ),
            (),
            1,
        ),
    ],
    ids=["open", "not-planned", "cross-repo"],
)
def test_native_edges_block_like_declared_ones(edge, blockers, unresolved):
    fake = FakeGitHub(native_blockers=[edge])
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.BLOCKED
    assert outcome.blockers == blockers
    assert outcome.unresolved_blockers == unresolved


def test_a_completed_native_edge_passes():
    fake = FakeGitHub(native_blockers=[blocker(number=4)])
    assert claim(fake).outcome == implementer_claim.CLAIMED


@pytest.mark.parametrize(
    "route",
    [
        ("GET", ISSUE_PATH),
        ("GET", COMMENTS),
        ("GET", DEPENDENCIES),
        ("GET", f"/repos/{REPO}/issues/3"),
    ],
    ids=["issue", "comments", "dependencies", "blocker"],
)
def test_api_errors_reading_blockers_propagate_without_writes(route):
    fake = FakeGitHub(
        issue_body="Blocked by: #3",
        blocker_issues={3: blocker()},
        errors={route: http_error(500, route[1])},
    )
    with pytest.raises(pr_github_client.FetchError):
        claim(fake)
    assert fake.writes == []


@pytest.mark.parametrize(
    ("issue", "comments", "edges"),
    [
        ({"body": 7}, [], []),
        ({"title": "no body"}, [], []),
        ({"body": ""}, [{"body": None}], []),
        (OWNED_ISSUE, [], [{"state": 1}]),
        (OWNED_ISSUE, [], [blocker(state="open", number="four")]),
        (OWNED_ISSUE, [], [{"state": "open"}]),
    ],
    ids=[
        "body-not-text",
        "issue-without-body",
        "comment-without-body",
        "edge-without-state",
        "edge-without-number",
        "edge-without-repository",
    ],
)
def test_malformed_ticket_payloads_are_api_errors(issue, comments, edges):
    fake = FakeGitHub(
        canned_payloads={ISSUE_PATH: issue},
        issue_comments=comments,
        native_blockers=edges,
    )
    with pytest.raises(pr_github_client.FetchError):
        claim(fake)
    assert fake.writes == []


def test_a_malformed_blocker_is_an_api_error():
    path = f"/repos/{REPO}/issues/3"
    fake = FakeGitHub(issue_body="Blocked by: #3", canned_payloads={path: {"number": 3}})
    with pytest.raises(pr_github_client.FetchError):
        claim(fake)
    assert fake.writes == []
