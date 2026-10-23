#!/usr/bin/env python3
"""Apply a publish plan through the GitHub REST API.

This is the only module in the pipeline that writes. It takes the plan JSON
produced by ``pr_publish.py``, resolves every action into HTTP operations,
and executes them through an injected ``GitHubClient``. A plan that names an
unsupported action, an unknown label, or anyone but the maintainer is rejected
before the first call, so an unexpected plan can never half-apply.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pr_github

SCHEMA_VERSION = 1

BOT_LOGIN = "fabiandistler"

EXIT_OK = 0
EXIT_ACTION_FAILED = 1
EXIT_USAGE = 2
EXIT_BAD_PLAN = 3
EXIT_OUTSIDE_ACTIONS = 5

ACTION_KINDS = ("set_labels", "upsert_comment", "request_reviewer", "assign")

# The ten labels the pipeline uses. Creating them is idempotent, so a fresh
# repository needs no manual setup before the first publish run.
LABELS = {
    "risk:low": ("0e8a16", "Low risk: documentation or reports, auto-merge eligible"),
    "risk:medium": ("fbca04", "Medium risk: needs a human review"),
    "risk:high": ("b60205", "High risk: never auto-merged"),
    "review:pass": ("0e8a16", "Review verdict: pass"),
    "review:concerns": ("fbca04", "Review verdict: concerns"),
    "review:block": ("b60205", "Review verdict: block"),
    "review:unavailable": ("6a737d", "The review could not be produced"),
    "needs-review": ("d93f0b", "A human should review this pull request"),
    "do-not-merge": ("000000", "Hard stop: never merge this pull request"),
    "auto-merge:bot": ("1d76db", "Auto-merge enabled by the review bot"),
}


class PlanError(ValueError):
    """The plan is malformed or names an action the writer must not perform."""


class ApplyError(RuntimeError):
    """A resolved operation returned an error status."""


class WriteClient(Protocol):
    """The write surface ``apply_plan`` needs; ``GitHubClient`` and fakes implement it."""

    def post(self, path: str, payload: dict[str, object] | None = None) -> pr_github.Response: ...

    def patch(self, path: str, payload: dict[str, object] | None = None) -> pr_github.Response: ...

    def delete(self, path: str, payload: dict[str, object] | None = None) -> pr_github.Response: ...


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
    if not isinstance(repo, str) or not pr_github.REPO_PATTERN.fullmatch(repo):
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


def _reviewer_operations(plan: dict, action: dict) -> list[Operation]:
    kind = action.get("kind")
    login = action.get("login")
    if login != BOT_LOGIN:
        raise PlanError(f"{kind} refuses any login other than {BOT_LOGIN}")
    if kind == "request_reviewer":
        return [
            Operation(
                kind="request_reviewer",
                method="POST",
                path=f"/repos/{plan['repo']}/pulls/{plan['number']}/requested_reviewers",
                payload={"reviewers": [BOT_LOGIN]},
            )
        ]
    return [
        Operation(
            kind="assign",
            method="POST",
            path=f"/repos/{plan['repo']}/issues/{plan['number']}/assignees",
            payload={"assignees": [BOT_LOGIN]},
        )
    ]


def _resolve_action(plan: dict, action: dict) -> list[Operation]:
    kind = action.get("kind")
    if kind == "set_labels":
        return _label_operations(plan, action)
    if kind == "upsert_comment":
        return _comment_operations(plan, action)
    if kind in ("request_reviewer", "assign"):
        return _reviewer_operations(plan, action)
    raise PlanError(f"unsupported action kind: {kind}")


def _resolve_plan(plan: object) -> list[tuple[dict, list[Operation]]]:
    validated = _validate_plan(plan)
    if validated["status"] == "aborted":
        return []
    return [(action, _resolve_action(validated, action)) for action in validated["actions"]]


# --- Execution ---------------------------------------------------------------


def _tolerated(operation: Operation, status: object) -> bool:
    if operation.tolerate == "already_exists" and status == 422:
        return True
    return operation.tolerate == "missing" and status == 404


def _send(client: WriteClient, operation: Operation) -> None:
    try:
        if operation.method == "POST":
            response = client.post(operation.path, operation.payload)
        elif operation.method == "PATCH":
            response = client.patch(operation.path, operation.payload)
        elif operation.method == "DELETE":
            response = client.delete(operation.path, operation.payload)
        else:  # pragma: no cover - the resolver only emits the three methods above
            raise ApplyError(f"unsupported method: {operation.method}")
    except pr_github.FetchError as error:
        if _tolerated(operation, error.status):
            return
        raise
    if _tolerated(operation, response.status):
        return
    if response.status >= 400:
        raise ApplyError(f"{operation.method} {operation.path} returned {response.status}")


def _detail(kind: str, operations: list[Operation]) -> str:
    if kind == "set_labels":
        created = sum(1 for operation in operations if operation.tolerate == "already_exists")
        added = sum(
            1
            for operation in operations
            if operation.method == "POST" and operation.tolerate is None
        )
        removed = sum(1 for operation in operations if operation.method == "DELETE")
        return f"created {created}, added {added}, removed {removed}"
    if kind == "upsert_comment":
        if operations and operations[0].method == "PATCH":
            return f"updated comment {operations[0].path.rsplit('/', 1)[-1]}"
        return "posted a comment"
    if kind == "request_reviewer":
        return f"requested {BOT_LOGIN}"
    if kind == "assign":
        return f"assigned {BOT_LOGIN}"
    return f"{len(operations)} operation(s)"


def _apply_action(client: WriteClient, kind: str, operations: list[Operation]) -> dict:
    try:
        for operation in operations:
            _send(client, operation)
    except pr_github.FetchError as error:
        detail = f"{error} (HTTP {error.status})" if error.status is not None else str(error)
        return {"kind": kind, "ok": False, "detail": detail}
    except ApplyError as error:
        return {"kind": kind, "ok": False, "detail": str(error)}
    return {"kind": kind, "ok": True, "detail": _detail(kind, operations)}


def apply_plan(plan: dict, client: WriteClient) -> list[dict]:
    """Apply every action in ``plan`` and return one result per action."""
    resolved = _resolve_plan(plan)
    return [_apply_action(client, action["kind"], operations) for action, operations in resolved]


def resolve_operations(plan: object) -> list[Operation]:
    """Resolve a plan into HTTP operations without sending anything."""
    return [operation for _, operations in _resolve_plan(plan) for operation in operations]


# --- CLI ---------------------------------------------------------------------

USAGE = """usage: pr_apply.py --plan FILE [--write]

Apply a pr_publish plan through the GitHub REST API. Without --write it prints
the resolved HTTP operations and makes no network call.

  --plan FILE   plan JSON from pr_publish.py
  --write       apply the plan; needs GITHUB_ACTIONS=true and GITHUB_TOKEN
  -h, --help    show this message

examples:
  python3 scripts/pr_apply.py --plan plan.json
  GITHUB_TOKEN=... python3 scripts/pr_apply.py --plan plan.json --write

exit: 0 all actions applied | 1 an action failed | 2 usage |
      3 bad plan or unsupported action | 5 --write outside GitHub Actions
"""


class UsageError(Exception):
    """The command line was not usable."""


def _parse_arguments(argv: list[str]) -> dict:
    options: dict[str, object] = {"plan": None, "write": False}
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-h", "--help"):
            return {"help": True}
        name, separator, inline = argument.partition("=")
        if name == "--write":
            if separator:
                raise UsageError("--write takes no value")
            options["write"] = True
            index += 1
            continue
        if name != "--plan":
            raise UsageError(f"unknown argument: {argument}")
        if separator:
            value = inline
            index += 1
        else:
            if index + 1 >= len(argv):
                raise UsageError("--plan needs a value")
            value = argv[index + 1]
            index += 2
        if not value:
            raise UsageError("--plan needs a value")
        options["plan"] = value

    if options["plan"] is None:
        raise UsageError("--plan is required")
    return options


def _read_plan(path: str) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise PlanError(f"cannot read --plan: {error}") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise PlanError(f"--plan is not valid JSON: {error}") from error
    return payload


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def main(argv: list[str] | None = None, client: WriteClient | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = _parse_arguments(arguments)
    except UsageError as error:
        print(f"pr_apply.py: {error}", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        return EXIT_USAGE
    if options.get("help"):
        print(USAGE, end="")
        return EXIT_OK

    write = options["write"] is True
    token = os.environ.get("GITHUB_TOKEN") or None
    if write and (os.environ.get("GITHUB_ACTIONS") != "true" or token is None):
        print(
            "pr_apply.py: --write is only available inside GitHub Actions with GITHUB_TOKEN",
            file=sys.stderr,
        )
        return EXIT_OUTSIDE_ACTIONS

    try:
        plan = _read_plan(str(options["plan"]))
        if not write:
            operations = resolve_operations(plan)
        else:
            results = apply_plan(plan, client or pr_github.GitHubClient(token))
    except PlanError as error:
        print(f"pr_apply.py: {error}", file=sys.stderr)
        return EXIT_BAD_PLAN

    if not write:
        _emit(
            {
                "schema_version": SCHEMA_VERSION,
                "repo": plan.get("repo"),
                "number": plan.get("number"),
                "status": plan.get("status"),
                "write": False,
                "operations": [operation.as_json() for operation in operations],
            }
        )
        return EXIT_OK

    ok = all(result["ok"] for result in results)
    _emit(
        {
            "schema_version": SCHEMA_VERSION,
            "repo": plan.get("repo"),
            "number": plan.get("number"),
            "write": True,
            "results": results,
            "ok": ok,
        }
    )
    return EXIT_OK if ok else EXIT_ACTION_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
