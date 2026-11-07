#!/usr/bin/env python3
"""Apply a publish plan through the GitHub REST API.

This is the only module in the pipeline that writes. It takes the plan JSON
produced by ``pr_publish.py``, resolves every action into HTTP operations
(``pr_actions.py``), and executes them through an injected ``GitHubClient``.
Resolution rejects an unexpected plan before the first call.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Protocol

import pr_actions
import pr_github_client
from pr_actions import Operation, PlanError

EXIT_OK = 0
EXIT_ACTION_FAILED = 1
EXIT_USAGE = 2
EXIT_BAD_PLAN = 3
EXIT_OUTSIDE_ACTIONS = 5


class ApplyError(RuntimeError):
    """A resolved operation returned an error status."""


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
    if not isinstance(body, dict) or errors:
        messages = [str(error.get("message")) for error in errors or [] if isinstance(error, dict)]
        raise ApplyError(f"{operation.kind}: {'; '.join(messages) or 'unexpected response'}")


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
        return f"requested {pr_actions.BOT_LOGIN}"
    if kind == "enable_auto_merge":
        return "enabled auto-merge with a merge commit"
    if kind == "disable_auto_merge":
        return "disabled auto-merge"
    if kind == "assign":
        return f"assigned {pr_actions.BOT_LOGIN}"
    return f"{len(operations)} operation(s)"


def _apply_action(client: WriteClient, kind: str, operations: list[Operation]) -> dict:
    try:
        for operation in operations:
            _send(client, operation)
    except pr_github_client.FetchError as error:
        detail = f"{error} (HTTP {error.status})" if error.status is not None else str(error)
        return {"kind": kind, "ok": False, "detail": detail}
    except ApplyError as error:
        return {"kind": kind, "ok": False, "detail": str(error)}
    return {"kind": kind, "ok": True, "detail": _detail(kind, operations)}


def apply_plan(plan: dict, client: WriteClient) -> list[dict]:
    """Apply every action in ``plan`` and return one result per action."""
    resolved = pr_actions.resolve_plan(plan)
    return [_apply_action(client, action["kind"], operations) for action, operations in resolved]


def resolve_operations(plan: object) -> list[Operation]:
    """Resolve a plan into HTTP operations without sending anything."""
    resolved = pr_actions.resolve_plan(plan)
    return [operation for _, operations in resolved for operation in operations]


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
            results = apply_plan(plan, client or pr_github_client.GitHubClient(token))
    except PlanError as error:
        print(f"pr_apply.py: {error}", file=sys.stderr)
        return EXIT_BAD_PLAN

    if not write:
        _emit(
            {
                "schema_version": pr_actions.SCHEMA_VERSION,
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
            "schema_version": pr_actions.SCHEMA_VERSION,
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
