"""Tests for the live publish path of scripts/pr_publish.py.

``publish_live`` fetches through an injected fake; no test touches the network.
"""

from __future__ import annotations

import pr_plan
import pr_publish
import pytest
from pr_publish_testkit import (
    ACTIVE_AUTO_MERGE,
    COMMENTS_PATH,
    FILES_PATH,
    MARKER,
    NUMBER,
    PR_PATH,
    REPO,
    FakeGitHub,
    actions_of,
    comment_action,
    json_response,
    label_action,
    make_assessment,
    make_context,
    make_review,
    write_calls,
)

# --- Live path ---------------------------------------------------------------


def test_live_dry_run_fetches_once_and_writes_nothing():
    fake = FakeGitHub(["abc123"])

    plan = pr_publish.publish_live(REPO, NUMBER, make_assessment(), make_review(), client=fake)

    assert plan["status"] == "planned"
    assert plan["head_sha"] == "abc123"
    assert fake.pull_fetches == 1
    assert write_calls(fake) == []


def test_live_write_applies_exactly_the_planned_actions():
    fake = FakeGitHub(["abc123", "abc123"])

    payload = pr_publish.publish_live(
        REPO, NUMBER, make_assessment(), make_review(), write=True, client=fake
    )

    assert payload["schema_version"] == 1
    assert payload["plan"]["status"] == "planned"
    assert payload["ok"] is True
    assert [result["kind"] for result in payload["results"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]
    assert fake.pull_fetches == 2
    assert [call["method"] for call in write_calls(fake)] == [
        "POST",
        "POST",
        "POST",
        "POST",
        "POST",
    ]
    assert write_calls(fake)[0]["path"] == f"/repos/{REPO}/labels"
    assert write_calls(fake)[2]["path"] == f"/repos/{REPO}/issues/{NUMBER}/labels"
    assert write_calls(fake)[3]["path"] == COMMENTS_PATH
    assert write_calls(fake)[4]["path"] == f"/repos/{REPO}/pulls/{NUMBER}/requested_reviewers"


def test_a_changed_head_sha_between_the_fetches_aborts_every_write():
    fake = FakeGitHub(["abc123", "def456"])

    payload = pr_publish.publish_live(
        REPO, NUMBER, make_assessment(), make_review(), write=True, client=fake
    )

    assert payload["status"] == "aborted"
    assert payload["abort_reason"] == "head_sha_changed"
    assert payload["actions"] == []
    assert payload["head_sha"] == "def456"
    assert fake.pull_fetches == 2
    assert write_calls(fake) == []


def test_a_stale_assessment_aborts_before_the_second_fetch():
    fake = FakeGitHub(["def456"])

    payload = pr_publish.publish_live(
        REPO,
        NUMBER,
        make_assessment(head_sha="abc123"),
        make_review(head_sha="abc123"),
        write=True,
        client=fake,
    )

    assert payload["status"] == "aborted"
    assert payload["abort_reason"] == "head_sha_changed"
    assert fake.pull_fetches == 1
    assert write_calls(fake) == []


@pytest.mark.parametrize(
    ("changed_path", "replacement", "expected_risk", "expected_comment_id"),
    [
        (PR_PATH, {"labels": [{"name": "risk:high"}]}, "low", None),
        (
            FILES_PATH,
            [
                {
                    "filename": ".github/workflows/check.yml",
                    "status": "modified",
                    "additions": 1,
                    "deletions": 0,
                    "patch": "@@",
                }
            ],
            "high",
            None,
        ),
        (COMMENTS_PATH, [{"id": 77, "body": f"{MARKER}\nprevious review"}], "low", 77),
    ],
)
def test_live_write_replans_using_the_final_context(
    changed_path, replacement, expected_risk, expected_comment_id
):
    class ChangedContext(FakeGitHub):
        def get(self, path, params=None, accept=None):
            response = super().get(path, params, accept)
            if self.pull_fetches == 2 and path == changed_path and accept is None:
                if path == PR_PATH:
                    return json_response({**response.json(), **replacement})
                return json_response(replacement)
            return response

    fake = ChangedContext(["abc123", "abc123"])
    payload = pr_publish.publish_live(
        REPO, NUMBER, make_assessment(), make_review(), write=True, client=fake
    )

    plan = payload["plan"]
    assert plan["decision"]["risk"] == expected_risk
    assert comment_action(plan)["comment_id"] == expected_comment_id
    if changed_path == PR_PATH:
        assert "risk:high" in label_action(plan)["remove"]


def test_a_pull_request_closed_between_fetches_aborts_every_write():
    class ClosedPull(FakeGitHub):
        def get(self, path, params=None, accept=None):
            response = super().get(path, params, accept)
            if self.pull_fetches == 2 and path == PR_PATH and accept is None:
                return json_response({**response.json(), "state": "closed"})
            return response

    fake = ClosedPull(["abc123", "abc123"])
    plan = pr_publish.publish_live(
        REPO, NUMBER, make_assessment(), make_review(), write=True, client=fake
    )

    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "pull_request_closed"
    assert plan["actions"] == []
    assert write_calls(fake) == []


def test_an_already_closed_pull_request_produces_no_actions():
    plan = pr_plan.plan_publish(make_context(state="closed"), make_assessment(), make_review())

    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "pull_request_closed"
    assert plan["actions"] == []


def test_a_failed_write_is_reported_in_the_results():
    fake = FakeGitHub(["abc123", "abc123"])
    fake.fail_paths.add(f"/repos/{REPO}/labels")

    payload = pr_publish.publish_live(
        REPO, NUMBER, make_assessment(), make_review(), write=True, client=fake
    )

    assert payload["ok"] is False
    assert [result["ok"] for result in payload["results"]] == [False, True, True]


# --- Auto-merge on the live path ----------------------------------------------

BOT_LABELS = ["risk:low", "review:pass", "auto-merge:bot"]


def test_live_plan_enables_auto_merge_on_the_fetched_node_id(monkeypatch):
    monkeypatch.setenv("PR_AUTO_MERGE", "true")
    fake = FakeGitHub(["abc123"])

    plan = pr_publish.publish_live(REPO, NUMBER, make_assessment(), make_review(), client=fake)

    assert actions_of(plan, "enable_auto_merge") == [
        {
            "kind": "enable_auto_merge",
            "pull_request_id": "PR_kwDOtest42",
            "method": "merge",
            "expected_head_oid": "abc123",
        }
    ]


@pytest.mark.parametrize(("mergeable", "expected"), [(None, "kept"), (False, "disabled")])
def test_live_mergeability_still_being_computed_never_disables(monkeypatch, mergeable, expected):
    monkeypatch.setenv("PR_AUTO_MERGE", "true")
    fake = FakeGitHub(["abc123"], labels=BOT_LABELS)
    fake.pull_overrides = {"mergeable": mergeable, "auto_merge": ACTIVE_AUTO_MERGE}

    plan = pr_publish.publish_live(REPO, NUMBER, make_assessment(), make_review(), client=fake)

    assert plan["decision"]["auto_merge"] == expected
