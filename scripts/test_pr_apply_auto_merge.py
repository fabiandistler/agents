"""Tests for the auto-merge writes of scripts/pr_apply.py.

GitHub has no REST endpoint for auto-merge, so both actions resolve to one
GraphQL mutation each. Every test injects ``FakeClient``; none touches the
network.
"""

from __future__ import annotations

import json

import pr_apply
import pr_github
import pytest
from pr_apply_testkit import FakeClient, make_plan, only_result

HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
NODE_ID = "PR_kwDOtest42"
ENABLE = {
    "kind": "enable_auto_merge",
    "pull_request_id": NODE_ID,
    "method": "merge",
    "expected_head_oid": HEAD_SHA,
}
DISABLE = {"kind": "disable_auto_merge", "pull_request_id": NODE_ID}


def plan_with(action: dict) -> dict:
    return make_plan([action], head_sha=HEAD_SHA)


def graphql_response(payload: dict) -> pr_github.Response:
    return pr_github.Response(status=200, body=json.dumps(payload).encode("utf-8"))


def test_enable_sends_the_merge_commit_mutation_pinned_to_the_reviewed_head():
    client = FakeClient()

    result = only_result(pr_apply.apply_plan(plan_with(ENABLE), client))

    assert result["ok"] is True
    assert result["detail"]
    [call] = client.calls
    assert (call["method"], call["path"]) == ("POST", "/graphql")
    assert "enablePullRequestAutoMerge(input:" in call["payload"]["query"]
    assert call["payload"]["variables"] == {
        "pullRequestId": NODE_ID,
        "mergeMethod": "MERGE",
        "expectedHeadOid": HEAD_SHA,
    }


def test_disable_sends_the_disable_mutation_for_the_pull_request():
    client = FakeClient()

    result = only_result(pr_apply.apply_plan(plan_with(DISABLE), client))

    assert result["ok"] is True
    [call] = client.calls
    assert (call["method"], call["path"]) == ("POST", "/graphql")
    assert "disablePullRequestAutoMerge(input:" in call["payload"]["query"]
    assert call["payload"]["variables"] == {"pullRequestId": NODE_ID}


def test_a_graphql_error_fails_the_action_with_its_message():
    # GraphQL reports a refused mutation with HTTP 200 and an errors list.
    message = "Pull request Auto merge is not allowed for this repository"
    client = FakeClient(
        lambda *_: graphql_response({"data": None, "errors": [{"message": message}]})
    )

    result = only_result(pr_apply.apply_plan(plan_with(ENABLE), client))

    assert result["ok"] is False
    assert message in result["detail"]


def test_an_unreadable_graphql_response_fails_the_action():
    client = FakeClient(lambda *_: pr_github.Response(status=200, body=b"<html>"))

    result = only_result(pr_apply.apply_plan(plan_with(DISABLE), client))

    assert result["ok"] is False


def test_an_http_error_fails_the_action():
    client = FakeClient(lambda *_: pr_github.FetchError("bad gateway", status=502))

    result = only_result(pr_apply.apply_plan(plan_with(ENABLE), client))

    assert result["ok"] is False
    assert "502" in result["detail"]


@pytest.mark.parametrize(
    "action",
    [
        {**ENABLE, "method": "squash"},
        {**ENABLE, "method": "rebase"},
        {key: value for key, value in ENABLE.items() if key != "method"},
        {**ENABLE, "pull_request_id": ""},
        {key: value for key, value in ENABLE.items() if key != "pull_request_id"},
        {**ENABLE, "expected_head_oid": "fedcba9876543210fedcba9876543210fedcba98"},
        {key: value for key, value in ENABLE.items() if key != "expected_head_oid"},
        {**DISABLE, "pull_request_id": None},
    ],
    ids=[
        "squash",
        "rebase",
        "no method",
        "empty node id",
        "no node id",
        "head other than the plan's",
        "no expected head",
        "disable without node id",
    ],
)
def test_a_malformed_auto_merge_action_is_rejected_before_any_call(action):
    client = FakeClient()

    with pytest.raises(pr_apply.PlanError):
        pr_apply.apply_plan(
            make_plan([{"kind": "set_labels", "add": [], "remove": []}, action], head_sha=HEAD_SHA),
            client,
        )

    assert client.calls == []


def test_the_dry_run_shows_the_mutation_without_a_call():
    operations = pr_apply.resolve_operations(plan_with(ENABLE))

    assert [(operation.method, operation.path) for operation in operations] == [
        ("POST", "/graphql")
    ]
    assert operations[0].as_json()["payload"]["variables"]["mergeMethod"] == "MERGE"
