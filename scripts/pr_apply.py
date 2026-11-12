#!/usr/bin/env python3
"""Apply a publish plan through the GitHub REST API.

This is the only module in the pipeline that writes. It takes the plan JSON
produced by ``pr_publish.py``, resolves every action into HTTP operations
(``pr_actions.py``), and executes them through an injected ``GitHubClient``.
Resolution rejects an unexpected plan before the first call.
"""

from __future__ import annotations

import os
import sys
import urllib.parse
from collections.abc import Callable
from typing import Protocol

import pr_actions
import pr_cli
import pr_github_client
import pr_verdict_status
from pr_actions import Operation, PlanError


class ApplyError(RuntimeError):
    """A resolved operation returned an error status."""


class AutoMergeRefused(ApplyError):
    """GitHub would not arm auto-merge: the pull request can be merged right now."""


# GitHub's refusal to arm auto-merge on a pull request whose merge state is
# CLEAN ("Pull request" twice, verbatim). It documents no error code; public
# reports show this message with type UNPROCESSABLE. Matched exactly, so any
# other refusal still fails the action.
CLEAN_STATUS_REFUSAL = "Pull request Pull request is in clean status"


class WriteClient(Protocol):
    """The write surface ``apply_plan`` needs; ``GitHubClient`` and fakes implement it."""

    def post(
        self, path: str, payload: dict[str, object] | None = None
    ) -> pr_github_client.Response: ...

    def patch(
        self, path: str, payload: dict[str, object] | None = None
    ) -> pr_github_client.Response: ...

    def delete(
        self, path: str, payload: dict[str, object] | None = None
    ) -> pr_github_client.Response: ...


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
    except pr_github_client.FetchError as error:
        if _tolerated(operation, error.status):
            return
        raise
    if _tolerated(operation, response.status):
        return
    if response.status >= 400:
        raise ApplyError(f"{operation.method} {operation.path} returned {response.status}")
    if operation.path == pr_actions.GRAPHQL_PATH:
        _check_graphql(operation, response)


def _check_graphql(operation: Operation, response: pr_github_client.Response) -> None:
    """GraphQL reports a refused mutation with HTTP 200 and an errors list."""
    try:
        body = response.json()
    except (UnicodeDecodeError, ValueError) as error:
        raise ApplyError(f"{operation.kind}: GraphQL returned no JSON") from error
    errors = body.get("errors") if isinstance(body, dict) else None
    if operation.kind == "enable_auto_merge" and _is_clean_refusal(errors):
        raise AutoMergeRefused(operation.kind)
    if not isinstance(body, dict) or errors:
        messages = [str(error.get("message")) for error in errors or [] if isinstance(error, dict)]
        raise ApplyError(f"{operation.kind}: {'; '.join(messages) or 'unexpected response'}")


def _is_clean_refusal(errors: object) -> bool:
    if not isinstance(errors, list) or len(errors) != 1 or not isinstance(errors[0], dict):
        return False
    error = errors[0]
    return error.get("message") == CLEAN_STATUS_REFUSAL and error.get("type") in (
        None,
        "UNPROCESSABLE",
    )


def _label_detail(operations: list[Operation]) -> str:
    created = sum(1 for operation in operations if operation.tolerate == "already_exists")
    added = sum(
        1 for operation in operations if operation.method == "POST" and operation.tolerate is None
    )
    removed = sum(1 for operation in operations if operation.method == "DELETE")
    return f"created {created}, added {added}, removed {removed}"


def _comment_detail(operations: list[Operation]) -> str:
    if operations[0].method == "PATCH":
        return f"updated comment {operations[0].path.rsplit('/', 1)[-1]}"
    return "posted a comment"


# One line per applied action kind for the results JSON and the step summary;
# the keys match pr_actions.RESOLVERS.
DETAILS: dict[str, Callable[[list[Operation]], str]] = {
    "set_labels": _label_detail,
    "upsert_comment": _comment_detail,
    "request_reviewer": lambda _operations: f"requested {pr_actions.MAINTAINER_LOGIN}",
    "assign": lambda _operations: f"assigned {pr_actions.MAINTAINER_LOGIN}",
    "enable_auto_merge": lambda _operations: "enabled auto-merge with a merge commit",
    "disable_auto_merge": lambda _operations: "disabled auto-merge",
    "set_status": lambda operations: (
        f"set {pr_verdict_status.CONTEXT} to {(operations[0].payload or {})['state']}"
    ),
}


def _written_labels(sent: list[Operation]) -> dict[str, list[str]]:
    """The labels the sent operations put on or took off the pull request."""
    added: list[str] = []
    removed: list[str] = []
    for operation in sent:
        if operation.method == "DELETE":
            removed.append(urllib.parse.unquote(operation.path.rsplit("/", 1)[-1]))
        elif operation.tolerate is None and operation.payload is not None:
            labels = operation.payload["labels"]
            if not isinstance(labels, list):  # pragma: no cover - the resolver builds a list
                raise ApplyError("set_labels sent a label payload that is not a list")
            added.extend(str(label) for label in labels)
    return {"added": added, "removed": removed}


def _apply_action(client: WriteClient, kind: str, operations: list[Operation]) -> dict:
    sent: list[Operation] = []
    result = _send_all(client, kind, operations, sent)
    if kind == "set_labels":
        # The labels actually written, for the step summary; a failure stops
        # the action, so they can be fewer than the plan asked for.
        result.update(_written_labels(sent))
    return result


def _send_all(
    client: WriteClient, kind: str, operations: list[Operation], sent: list[Operation]
) -> dict:
    try:
        for operation in operations:
            _send(client, operation)
            sent.append(operation)
    except pr_github_client.FetchError as error:
        detail = f"{error} (HTTP {error.status})" if error.status is not None else str(error)
        return {"kind": kind, "ok": False, "detail": detail}
    except AutoMergeRefused:
        # Decision D: no failure. The pull request waits for a human merge instead.
        detail = "not armed: GitHub reports the pull request as already mergeable"
        return {"kind": kind, "ok": True, "armed": False, "detail": detail}
    except ApplyError as error:
        return {"kind": kind, "ok": False, "detail": str(error)}
    result = {"kind": kind, "ok": True, "detail": DETAILS[kind](operations)}
    if kind == "enable_auto_merge":
        result["armed"] = True
    return result


def apply_plan(plan: dict, client: WriteClient) -> list[dict]:
    """Apply every action in ``plan`` and return one result per action.

    A green ``set_status`` is sent only when every earlier action succeeded:
    a run that failed to publish its verdict must not let the merge go ahead.
    The red job is the signal, and re-running it sets the status.
    """
    resolved = pr_actions.resolve_plan(plan)
    results: list[dict] = []
    for action, operations in resolved:
        if (
            action["kind"] == "set_status"
            and action.get("state") == "success"
            and not all(result["ok"] for result in results)
        ):
            detail = "not set: an earlier action failed, so the verdict is not published"
            results.append({"kind": "set_status", "ok": False, "detail": detail})
            continue
        results.append(_apply_action(client, action["kind"], operations))
    return results


def resolve_operations(plan: object) -> list[Operation]:
    """Resolve a plan into HTTP operations without sending anything."""
    resolved = pr_actions.resolve_plan(plan)
    return [operation for _, operations in resolved for operation in operations]


# --- CLI ---------------------------------------------------------------------

USAGE = f"""usage: pr_apply.py --plan FILE [--write]

Apply a pr_publish plan through the GitHub REST API. Without --write it prints
the resolved HTTP operations and makes no network call.

  --plan FILE   plan JSON from pr_publish.py
  --write       apply the plan; needs GITHUB_ACTIONS=true and GITHUB_TOKEN
  -h, --help    show this message

examples:
  python3 scripts/pr_apply.py --plan plan.json
  GITHUB_TOKEN=... python3 scripts/pr_apply.py --plan plan.json --write

{pr_cli.exit_help(0, 1, 2, 3, 5, 7)}
"""


def main(argv: list[str] | None = None, client: WriteClient | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = pr_cli.parse_flags(arguments, ("--plan",), ("--write",))
        if options is not None and options["plan"] is None:
            raise pr_cli.UsageError("--plan is required")
    except pr_cli.UsageError as error:
        return pr_cli.usage_failure("pr_apply.py", USAGE, error)
    if options is None:
        print(USAGE, end="")
        return pr_cli.EXIT_OK

    write = options["write"] is True
    token = os.environ.get("GITHUB_TOKEN") or None
    if write and os.environ.get("GITHUB_ACTIONS") != "true":
        print("pr_apply.py: --write is only available inside GitHub Actions", file=sys.stderr)
        return pr_cli.EXIT_OUTSIDE_ACTIONS
    if write and token is None:
        print("pr_apply.py: --write needs GITHUB_TOKEN", file=sys.stderr)
        return pr_cli.EXIT_MISSING_TOKEN

    try:
        plan = pr_cli.read_json_object(str(options["plan"]), "--plan")
        if not write:
            operations = resolve_operations(plan)
        else:
            results = apply_plan(plan, client or pr_github_client.GitHubClient(token))
    except (pr_cli.InputError, PlanError) as error:
        print(f"pr_apply.py: {error}", file=sys.stderr)
        return pr_cli.EXIT_BAD_INPUT

    if not write:
        pr_cli.print_json(
            {
                "schema_version": pr_actions.SCHEMA_VERSION,
                "repo": plan.get("repo"),
                "number": plan.get("number"),
                "status": plan.get("status"),
                "write": False,
                "operations": [operation.as_json() for operation in operations],
            }
        )
        return pr_cli.EXIT_OK

    ok = all(result["ok"] for result in results)
    pr_cli.print_json(
        {
            "schema_version": pr_actions.SCHEMA_VERSION,
            "repo": plan.get("repo"),
            "number": plan.get("number"),
            "write": True,
            "results": results,
            "ok": ok,
        }
    )
    return pr_cli.EXIT_OK if ok else pr_cli.EXIT_ACTION_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
