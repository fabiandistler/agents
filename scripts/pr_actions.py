"""Resolve a publish plan into the GitHub REST operations it means.

Each plan action maps to a fixed set of HTTP requests here; ``pr_apply.py``
sends them. A plan that names an unsupported action, an unknown label, or
anyone but the maintainer is rejected while resolving, before the first call,
so an unexpected plan can never half-apply.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass

import pr_github_client
from pr_labels import LABELS

SCHEMA_VERSION = 1

# The only login a plan may request as reviewer or assign.
MAINTAINER_LOGIN = "fabiandistler"

# GitHub has no REST endpoint for auto-merge; both writes are GraphQL mutations.
# The merge method is fixed to a merge commit. Branch deletion after the merge
# comes from the repository setting `delete_branch_on_merge`: the enable
# mutation has no field for it.
GRAPHQL_PATH = "/graphql"
MERGE_METHODS = {"merge": "MERGE"}
ENABLE_AUTO_MERGE = """
mutation($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod!, $expectedHeadOid: GitObjectID!) {
  enablePullRequestAutoMerge(input: {
    pullRequestId: $pullRequestId, mergeMethod: $mergeMethod, expectedHeadOid: $expectedHeadOid
  }) { clientMutationId }
}
""".strip()
DISABLE_AUTO_MERGE = """
mutation($pullRequestId: ID!) {
  disablePullRequestAutoMerge(input: {pullRequestId: $pullRequestId}) { clientMutationId }
}
""".strip()
HEAD_SHA_PATTERN = re.compile(r"[0-9a-f]{7,64}")


class PlanError(ValueError):
    """The plan is malformed or names an action the writer must not perform."""


@dataclass(frozen=True)
class Operation:
    """One HTTP request the plan resolves to."""

    kind: str
    method: str
    path: str
    payload: dict[str, object] | None = None
    tolerate: str | None = None

    def as_json(self) -> dict:
        return {
            "kind": self.kind,
            "method": self.method,
            "path": self.path,
            "payload": self.payload,
        }


# --- Plan validation ---------------------------------------------------------


def _validate_plan(plan: object) -> dict:
    if not isinstance(plan, dict):
        raise PlanError("plan is not a JSON object")
    if plan.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise PlanError("plan has an unsupported schema_version")
    repo = plan.get("repo")
    if not isinstance(repo, str) or not pr_github_client.REPO_PATTERN.fullmatch(repo):
        raise PlanError("plan repo must be OWNER/REPO")
    number = plan.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        raise PlanError("plan is missing a positive integer number")
    if plan.get("status") not in ("planned", "aborted"):
        raise PlanError("plan status must be planned or aborted")
    actions = plan.get("actions")
    if not isinstance(actions, list):
        raise PlanError("plan actions must be a list")
    if not all(isinstance(action, dict) for action in actions):
        raise PlanError("every plan action must be a JSON object")
    return plan


def _string_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list):
        raise PlanError(f"{name} must be a list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PlanError(f"{name} must contain non-empty strings")
        items.append(item)
    return items


# --- Action resolution -------------------------------------------------------


def _label_operations(plan: dict, action: dict) -> list[Operation]:
    add = _string_list(action.get("add"), "set_labels add")
    remove = _string_list(action.get("remove"), "set_labels remove")
    unknown = sorted(label for label in add if label not in LABELS)
    if unknown:
        raise PlanError(f"set_labels cannot create an unknown label: {unknown[0]}")
    overlap = sorted(set(add) & set(remove))
    if overlap:
        raise PlanError(f"set_labels both adds and removes {overlap[0]}")

    repo = plan["repo"]
    number = plan["number"]
    operations: list[Operation] = []
    for label in dict.fromkeys(add):
        color, description = LABELS[label]
        operations.append(
            Operation(
                kind="set_labels",
                method="POST",
                path=f"/repos/{repo}/labels",
                payload={"name": label, "color": color, "description": description},
                tolerate="already_exists",
            )
        )
    if add:
        operations.append(
            Operation(
                kind="set_labels",
                method="POST",
                path=f"/repos/{repo}/issues/{number}/labels",
                payload={"labels": list(dict.fromkeys(add))},
            )
        )
    for label in dict.fromkeys(remove):
        quoted = urllib.parse.quote(label, safe="")
        operations.append(
            Operation(
                kind="set_labels",
                method="DELETE",
                path=f"/repos/{repo}/issues/{number}/labels/{quoted}",
                tolerate="missing",
            )
        )
    return operations


def _comment_operations(plan: dict, action: dict) -> list[Operation]:
    body = action.get("body")
    if not isinstance(body, str) or not body.strip():
        raise PlanError("upsert_comment needs a non-empty body")
    comment_id = action.get("comment_id")
    if comment_id is None:
        return [
            Operation(
                kind="upsert_comment",
                method="POST",
                path=f"/repos/{plan['repo']}/issues/{plan['number']}/comments",
                payload={"body": body},
            )
        ]
    if isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0:
        raise PlanError("upsert_comment comment_id must be a positive integer or null")
    return [
        Operation(
            kind="upsert_comment",
            method="PATCH",
            path=f"/repos/{plan['repo']}/issues/comments/{comment_id}",
            payload={"body": body},
        )
    ]


def _maintainer(action: dict) -> str:
    login = action.get("login")
    if login != MAINTAINER_LOGIN:
        raise PlanError(f"{action['kind']} refuses any login other than {MAINTAINER_LOGIN}")
    return MAINTAINER_LOGIN


def _request_reviewer_operations(plan: dict, action: dict) -> list[Operation]:
    return [
        Operation(
            kind="request_reviewer",
            method="POST",
            path=f"/repos/{plan['repo']}/pulls/{plan['number']}/requested_reviewers",
            payload={"reviewers": [_maintainer(action)]},
        )
    ]


def _assign_operations(plan: dict, action: dict) -> list[Operation]:
    return [
        Operation(
            kind="assign",
            method="POST",
            path=f"/repos/{plan['repo']}/issues/{plan['number']}/assignees",
            payload={"assignees": [_maintainer(action)]},
        )
    ]


def _node_id(action: dict) -> str:
    node_id = action.get("pull_request_id")
    if not isinstance(node_id, str) or not node_id:
        raise PlanError(f"{action['kind']} needs the pull request node id")
    return node_id


def _graphql_operation(kind: str, query: str, variables: dict[str, object]) -> list[Operation]:
    return [
        Operation(
            kind=kind,
            method="POST",
            path=GRAPHQL_PATH,
            payload={"query": query, "variables": variables},
        )
    ]


def _enable_auto_merge_operations(plan: dict, action: dict) -> list[Operation]:
    node_id = _node_id(action)
    method = action.get("method")
    if method not in MERGE_METHODS:
        raise PlanError(f"enable_auto_merge accepts only the methods {sorted(MERGE_METHODS)}")
    head = action.get("expected_head_oid")
    if not isinstance(head, str) or not HEAD_SHA_PATTERN.fullmatch(head):
        raise PlanError("enable_auto_merge needs expected_head_oid as a commit SHA")
    if head != plan.get("head_sha"):
        raise PlanError("enable_auto_merge must pin the head commit the plan assessed")
    variables: dict[str, object] = {
        "pullRequestId": node_id,
        "mergeMethod": MERGE_METHODS[method],
        "expectedHeadOid": head,
    }
    return _graphql_operation("enable_auto_merge", ENABLE_AUTO_MERGE, variables)


def _disable_auto_merge_operations(plan: dict, action: dict) -> list[Operation]:
    variables: dict[str, object] = {"pullRequestId": _node_id(action)}
    return _graphql_operation("disable_auto_merge", DISABLE_AUTO_MERGE, variables)


# Every action kind a plan may carry, with the operations it resolves to. A
# kind missing here is refused before the first call.
RESOLVERS: dict[str, Callable[[dict, dict], list[Operation]]] = {
    "set_labels": _label_operations,
    "upsert_comment": _comment_operations,
    "request_reviewer": _request_reviewer_operations,
    "assign": _assign_operations,
    "enable_auto_merge": _enable_auto_merge_operations,
    "disable_auto_merge": _disable_auto_merge_operations,
}


def _resolve_action(plan: dict, action: dict) -> list[Operation]:
    kind = action.get("kind")
    resolver = RESOLVERS.get(kind) if isinstance(kind, str) else None
    if resolver is None:
        raise PlanError(f"unsupported action kind: {kind}")
    return resolver(plan, action)


def resolve_plan(plan: object) -> list[tuple[dict, list[Operation]]]:
    """Validate ``plan`` and pair each action with its operations; an aborted plan has none."""
    validated = _validate_plan(plan)
    if validated["status"] == "aborted":
        return []
    return [(action, _resolve_action(validated, action)) for action in validated["actions"]]
