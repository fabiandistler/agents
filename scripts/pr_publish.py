#!/usr/bin/env python3
"""Publish the review of one pull request: plan it, and with --write apply it.

The command reads the risk decision and the review artifact, plans the labels,
the sticky comment, the reviewer and the auto-merge decision (``pr_plan.py``),
and with ``--write`` re-fetches the pull request and applies the fresh plan
through ``pr_apply.py``. Without ``--write`` nothing is written.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pr_apply
import pr_github
import pr_github_client
import pr_plan

AUTO_MERGE_ENV = "PR_AUTO_MERGE"

EXIT_OK = 0
EXIT_ACTION_FAILED = 1
EXIT_USAGE = 2
EXIT_BAD_INPUT = 3
EXIT_LIVE_FAILED = 4
EXIT_OUTSIDE_ACTIONS = 5


def _fetch_context(repo: str, number: int, token: str | None, client=None) -> dict:
    if client is None:
        return pr_github.fetch_context(repo, number, token=token)
    return pr_github.fetch_context(repo, number, token=token, client=client)


def publish_live(
    repo: str,
    number: int,
    assessment: dict,
    review: dict,
    write: bool = False,
    client=None,
):
    """Fetch, plan and optionally apply one pull request.

    Without ``write`` the return value is the plan. With ``write`` it is the
    plan when the plan aborts, otherwise the results wrapper. ``client`` is a
    ``GitHubClient`` or a fake implementing ``get/post/patch/delete``; both
    fetches and the writes use it, so tests never touch the network.
    """
    assessment = pr_plan.validate_assessment(assessment)
    review = pr_plan.validate_review(review)
    token = _token(write, client)

    context = _fetch_context(repo, number, token, client)
    plan = pr_plan.plan_publish(
        context, assessment, review, auto_merge=os.environ.get(AUTO_MERGE_ENV)
    )
    if not write or plan["status"] == "aborted":
        return plan

    fresh = _fetch_context(repo, number, token, client)
    plan = pr_plan.plan_publish(
        fresh, assessment, review, auto_merge=os.environ.get(AUTO_MERGE_ENV)
    )
    if plan["status"] == "aborted":
        return plan
    return _apply(plan, token, client)


def hold_live(repo: str, number: int, write: bool = False, client=None):
    """Fetch, plan and optionally apply the auto-merge hold of one pull request.

    The hold needs no review: the workflow runs it on every push and when
    ``do-not-merge`` is added. Return values follow ``publish_live``.
    """
    token = _token(write, client)
    plan = pr_plan.plan_hold(_fetch_context(repo, number, token, client))
    if not write or plan["status"] == "aborted":
        return plan
    return _apply(plan, token, client)


def _token(write: bool, client) -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or None
    if write and client is None and token is None:
        raise pr_github_client.MissingTokenError("GITHUB_TOKEN is not set")
    return token


def _apply(plan: dict, token: str | None, client) -> dict:
    writer = client if client is not None else pr_github_client.GitHubClient(token)
    results = pr_apply.apply_plan(plan, writer)
    return {
        "schema_version": pr_plan.SCHEMA_VERSION,
        "plan": plan,
        "results": results,
        "ok": all(result["ok"] for result in results),
    }


# --- CLI ---------------------------------------------------------------------

USAGE = """usage: pr_publish.py --context FILE --assessment FILE --review FILE
       pr_publish.py --live --repo O/R --pr N (--assessment FILE --review FILE | --hold) [--write]

Plan the labels, the sticky comment, the reviewer and the auto-merge decision
for one pull request. Prints JSON on stdout; --write applies the plan.

  --context FILE      fresh context JSON from pr_github.py
  --assessment FILE   risk decision JSON from pr_risk.py
  --review FILE       review artifact JSON from pr_review.py
  --live              re-fetch the context from GitHub; needs GITHUB_TOKEN
  --repo O/R --pr N   repository as OWNER/REPO and pull request number (with --live)
  --hold              without a review: only disable the bot's auto-merge (any under do-not-merge)
  --write             apply the plan; needs --live and GITHUB_ACTIONS=true
  -h, --help          show this message

env: PR_AUTO_MERGE=true enables auto-merge planning; any other value keeps it off.

examples:
  python3 scripts/pr_publish.py --context c.json --assessment a.json --review r.json
  python3 scripts/pr_publish.py --live --repo fabiandistler/agents --pr 42 \\
      --assessment a.json --review r.json --write

exit: 0 plan or write result | 1 a write action failed | 2 usage |
      3 bad input/artifact | 4 live fetch failed | 5 --write outside GitHub Actions
"""

VALUE_FLAGS = ("--context", "--pr", "--repo", "--assessment", "--review")


class UsageError(Exception):
    """The command line was not usable."""


def _parse_arguments(argv: list[str]) -> dict:
    options: dict[str, object] = {
        "context": None,
        "live": False,
        "pr": None,
        "repo": None,
        "assessment": None,
        "review": None,
        "write": False,
        "hold": False,
    }
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-h", "--help"):
            return {"help": True}
        name, separator, inline = argument.partition("=")
        if name == "--live":
            if separator:
                raise UsageError("--live takes no value")
            options["live"] = True
            index += 1
            continue
        if name in ("--write", "--hold"):
            if separator:
                raise UsageError(f"{name} takes no value")
            options[name[2:]] = True
            index += 1
            continue
        if name not in VALUE_FLAGS:
            raise UsageError(f"unknown argument: {argument}")
        if separator:
            value = inline
            index += 1
        else:
            if index + 1 >= len(argv):
                raise UsageError(f"{name} needs a value")
            value = argv[index + 1]
            index += 2
        if not value:
            raise UsageError(f"{name} needs a value")
        options[name[2:]] = value

    if options["hold"] is True:
        if any(options[name] is not None for name in ("context", "assessment", "review")):
            raise UsageError("--hold takes no --context, --assessment or --review")
        if options["live"] is not True:
            raise UsageError("--hold requires --live")
    else:
        for required in ("assessment", "review"):
            if options[required] is None:
                raise UsageError(f"--{required} is required")

    has_context = isinstance(options["context"], str)
    has_live = options["live"] is True
    if has_context and has_live:
        raise UsageError("--context and --live are mutually exclusive")
    if not has_context and not has_live:
        raise UsageError("one of --context or --live is required")
    if options["write"] is True and not has_live:
        raise UsageError("--write requires --live")
    if not has_live:
        if options["pr"] is not None or options["repo"] is not None:
            raise UsageError("--pr and --repo are only valid with --live")
        return options

    if options["pr"] is None or options["repo"] is None:
        raise UsageError("--live requires --pr and --repo")
    try:
        number = int(str(options["pr"]))
    except ValueError as error:
        raise UsageError("--pr must be a positive integer") from error
    if number <= 0:
        raise UsageError("--pr must be a positive integer")
    options["pr"] = number
    if not pr_github_client.REPO_PATTERN.fullmatch(str(options["repo"])):
        raise UsageError("--repo must be OWNER/REPO")
    return options


def _read_json(path: str, flag: str) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise pr_plan.ArtifactError(f"cannot read {flag}: {error}") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise pr_plan.ArtifactError(f"{flag} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise pr_plan.ArtifactError(f"{flag} must contain a JSON object")
    return payload


def main(argv: list[str] | None = None, client=None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = _parse_arguments(arguments)
    except UsageError as error:
        print(f"pr_publish.py: {error}", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        return EXIT_USAGE
    if options.get("help"):
        print(USAGE, end="")
        return EXIT_OK

    if options["write"] is True and os.environ.get("GITHUB_ACTIONS") != "true":
        print(
            "pr_publish.py: --write is only available inside GitHub Actions",
            file=sys.stderr,
        )
        return EXIT_OUTSIDE_ACTIONS

    if options["hold"] is True:
        try:
            payload = hold_live(
                str(options["repo"]),
                int(options["pr"]),
                write=options["write"] is True,
                client=client,
            )
        except pr_github_client.FetchError as error:
            print(f"pr_publish.py: live fetch failed: {error}", file=sys.stderr)
            return EXIT_LIVE_FAILED
        except pr_plan.ArtifactError as error:
            print(f"pr_publish.py: {error}", file=sys.stderr)
            return EXIT_BAD_INPUT
        return _emit(payload, options["write"] is True)

    try:
        assessment = _read_json(str(options["assessment"]), "--assessment")
        review = _read_json(str(options["review"]), "--review")
        if options["live"] is True:
            try:
                payload = publish_live(
                    str(options["repo"]),
                    int(options["pr"]),
                    assessment,
                    review,
                    write=options["write"] is True,
                    client=client,
                )
            except pr_github_client.FetchError as error:
                print(f"pr_publish.py: live fetch failed: {error}", file=sys.stderr)
                return EXIT_LIVE_FAILED
        else:
            context = _read_json(str(options["context"]), "--context")
            payload = pr_plan.plan_publish(
                context,
                assessment,
                review,
                auto_merge=os.environ.get(AUTO_MERGE_ENV),
            )
    except (pr_plan.ArtifactError, pr_apply.PlanError) as error:
        print(f"pr_publish.py: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT

    return _emit(payload, options["write"] is True)


def _emit(payload: dict, write: bool) -> int:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    if write and payload.get("ok") is False:
        return EXIT_ACTION_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
