#!/usr/bin/env python3
"""Decide whether the PR review leaves a pull request alone by its head branch.

A repository that calls the reusable PR review can name head-branch prefixes
whose pull requests another process reviews (repo-maintenance: ``maintenance/``).
The workflow passes them in ``PR_SKIP_HEAD_PREFIXES``, comma-separated. A
skipped pull request gets no model call, no publish and no hold: ``assess``
reads ``skip`` from this CLI, and ``pr_plan`` aborts the publish and the hold
plans with ``head_skipped`` from a fresh fetch, so nothing is written even
when a job runs anyway.
"""

from __future__ import annotations

import os
import sys

import pr_cli

PREFIXES_ENV = "PR_SKIP_HEAD_PREFIXES"
ABORT_REASON = "head_skipped"

USAGE = f"""\
usage: pr_skip.py --context FILE

Print `skip=true` when the head branch of the pull request in FILE starts with
one of the prefixes in {PREFIXES_ENV}, else `skip=false`, for $GITHUB_OUTPUT.

  --context FILE  context JSON produced by pr_github.py
  -h, --help      show this message
env: {PREFIXES_ENV} (comma-separated head-branch prefixes, e.g. `maintenance/`;
  unset or empty skips nothing)

example:
  PR_SKIP_HEAD_PREFIXES=maintenance/ python3 scripts/pr_skip.py --context context.json

{pr_cli.exit_help(0, 2, 3)}
"""


def prefixes_from_env() -> tuple[str, ...]:
    """The configured prefixes; blanks around a comma and empty entries drop out."""
    text = os.environ.get(PREFIXES_ENV) or ""
    return tuple(prefix.strip() for prefix in text.split(",") if prefix.strip())


def head_skipped(context: dict, prefixes: tuple[str, ...]) -> bool:
    """True when the context's head branch starts with one of ``prefixes``.

    A context without a head branch (an unavailable fetch) is not skipped, so
    the review runs as it would without the setting.
    """
    head_ref = context.get("head_ref")
    if not isinstance(head_ref, str) or not head_ref:
        return False
    return any(head_ref.startswith(prefix) for prefix in prefixes)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = pr_cli.parse_flags(arguments, ("--context",))
        if options is not None and options["context"] is None:
            raise pr_cli.UsageError("--context is required")
    except pr_cli.UsageError as error:
        return pr_cli.usage_failure("pr_skip.py", USAGE, error)
    if options is None:
        print(USAGE, end="")
        return pr_cli.EXIT_OK
    try:
        context = pr_cli.read_json_object(str(options["context"]), "--context")
    except pr_cli.InputError as error:
        print(f"pr_skip.py: {error}", file=sys.stderr)
        return pr_cli.EXIT_BAD_INPUT
    skipped = head_skipped(context, prefixes_from_env())
    print("skip=" + ("true" if skipped else "false"))
    return pr_cli.EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
