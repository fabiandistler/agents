#!/usr/bin/env python3
"""Publish the review of one pull request: plan it, and with --write apply it.

The command reads the risk decision and the review artifact, plans the labels,
the sticky comment, the reviewer, the auto-merge decision and the
`pr-review/verdict` commit status (``pr_plan.py``), and with ``--write``
re-fetches the pull request and applies the fresh plan through ``pr_apply.py``.
Without ``--write`` nothing is written.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pr_apply
import pr_cli
import pr_github
import pr_github_client
import pr_plan
import pr_summary

AUTO_MERGE_ENV = "PR_AUTO_MERGE"


def publish_live(
    repo: str,
    number: int,
    assessment: dict,
    review: dict,
    write: bool = False,
    client=None,
    status_url: str | None = None,
):
    """Fetch, plan and optionally apply one pull request.

    Without ``write`` the return value is the plan. With ``write`` it is the
    plan when the plan aborts, otherwise the results wrapper. When GitHub
    refuses to arm auto-merge because the pull request is already mergeable,
    the wrapper gains ``follow_up``: a replan from a third fetch that drops the
    bot's label, asks for a human and says so in the comment (decision D).
    ``client`` is a ``GitHubClient`` or a fake implementing
    ``get/post/patch/delete``; the fetches and the writes use it, so tests
    never touch the network. ``status_url`` is the run page the verdict status
    links to.
    """
    assessment = pr_plan.validate_assessment(assessment)
    review = pr_plan.validate_review(review)
    token = _token(write, client)

    context = pr_github.fetch_context(repo, number, token=token, client=client)
    plan = pr_plan.plan_publish(
        context,
        assessment,
        review,
        auto_merge=os.environ.get(AUTO_MERGE_ENV),
        status_url=status_url,
    )
    if not write or plan["status"] == "aborted":
        return plan

    fresh = pr_github.fetch_context(repo, number, token=token, client=client)
    plan = pr_plan.plan_publish(
        fresh,
        assessment,
        review,
        auto_merge=os.environ.get(AUTO_MERGE_ENV),
        status_url=status_url,
    )
    if plan["status"] == "aborted":
        return plan
    applied = _apply(plan, token, client)
    if not any(result.get("armed") is False for result in applied["results"]):
        return applied

    after = pr_github.fetch_context(repo, number, token=token, client=client)
    follow_up = pr_plan.plan_publish(
        after,
        assessment,
        review,
        auto_merge=os.environ.get(AUTO_MERGE_ENV),
        auto_merge_refused=True,
        status_url=status_url,
    )
    if follow_up["status"] == "aborted":
        return {**applied, "follow_up": {"plan": follow_up, "results": []}}
    results = pr_apply.apply_plan(follow_up, _writer(token, client))
    return {
        **applied,
        "follow_up": {"plan": follow_up, "results": results},
        "ok": applied["ok"] and all(result["ok"] for result in results),
    }


def hold_live(repo: str, number: int, write: bool = False, client=None):
    """Fetch, plan and optionally apply the auto-merge hold of one pull request.

    The hold needs no review: the workflow runs it on every push and when
    ``do-not-merge`` is added. Return values follow ``publish_live``.
    """
    token = _token(write, client)
    plan = pr_plan.plan_hold(pr_github.fetch_context(repo, number, token=token, client=client))
    if not write or plan["status"] == "aborted":
        return plan
    return _apply(plan, token, client)


def _token(write: bool, client) -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or None
    if write and client is None and token is None:
        raise pr_github_client.MissingTokenError("GITHUB_TOKEN is not set")
    return token


def _writer(token: str | None, client):
    return client if client is not None else pr_github_client.GitHubClient(token)


def _apply(plan: dict, token: str | None, client) -> dict:
    results = pr_apply.apply_plan(plan, _writer(token, client))
    return {
        "schema_version": pr_plan.SCHEMA_VERSION,
        "plan": plan,
        "results": results,
        "ok": all(result["ok"] for result in results),
    }


# --- CLI ---------------------------------------------------------------------

USAGE = f"""usage: pr_publish.py --context FILE --assessment FILE --review FILE
       pr_publish.py --live --repo O/R --pr N (--assessment FILE --review FILE | --hold) [--write]

Plan the labels, the sticky comment, the reviewer, the auto-merge decision and
the pr-review/verdict status of one pull request. Prints JSON; --write applies it.

  --context FILE      fresh context JSON from pr_github.py
  --assessment FILE   risk decision JSON from pr_risk.py
  --review FILE       review artifact JSON from pr_review.py
  --live              re-fetch the context from GitHub; needs GITHUB_TOKEN
  --repo O/R --pr N   repository as OWNER/REPO and pull request number (with --live)
  --hold              without a review: only disable the bot's auto-merge (any under do-not-merge)
  --write             apply the plan; needs --live and GITHUB_ACTIONS=true
  --summary FILE      either form: also append a Markdown summary to FILE (not --hold)
  --status-url URL    either form: https link for the pr-review/verdict status (not --hold)
  -h, --help          show this message
env: PR_AUTO_MERGE=true enables auto-merge planning; any other value keeps it off.
examples:
  python3 scripts/pr_publish.py --context c.json --assessment a.json --review r.json
  python3 scripts/pr_publish.py --live --repo fabiandistler/agents --pr 42 \\
      --assessment a.json --review r.json --write

{pr_cli.exit_help(0, 1, 2, 3, 4, 5, 6, 7)}
"""

VALUE_FLAGS = (
    "--context",
    "--pr",
    "--repo",
    "--assessment",
    "--review",
    "--summary",
    "--status-url",
)


def _parse_arguments(argv: list[str]) -> dict | None:
    options = pr_cli.parse_flags(argv, VALUE_FLAGS, ("--live", "--write", "--hold"))
    if options is None:
        return None
    if options["hold"] is True:
        if any(
            options[name] is not None
            for name in ("context", "assessment", "review", "summary", "status_url")
        ):
            raise pr_cli.UsageError(
                "--hold takes no --context, --assessment, --review, --summary or --status-url"
            )
        if options["live"] is not True:
            raise pr_cli.UsageError("--hold requires --live")
    else:
        for required in ("assessment", "review"):
            if options[required] is None:
                raise pr_cli.UsageError(f"--{required} is required")

    status_url = options["status_url"]
    if status_url is not None and not str(status_url).startswith("https://"):
        raise pr_cli.UsageError("--status-url must be an https URL")

    has_context = isinstance(options["context"], str)
    has_live = options["live"] is True
    if has_context and has_live:
        raise pr_cli.UsageError("--context and --live are mutually exclusive")
    if not has_context and not has_live:
        raise pr_cli.UsageError("one of --context or --live is required")
    if options["write"] is True and not has_live:
        raise pr_cli.UsageError("--write requires --live")
    if has_live:
        pr_cli.require_pull_request(options)
    elif options["pr"] is not None or options["repo"] is not None:
        raise pr_cli.UsageError("--pr and --repo are only valid with --live")
    return options


def main(argv: list[str] | None = None, client=None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = _parse_arguments(arguments)
    except pr_cli.UsageError as error:
        return pr_cli.usage_failure("pr_publish.py", USAGE, error)
    if options is None:
        print(USAGE, end="")
        return pr_cli.EXIT_OK

    if options["write"] is True and os.environ.get("GITHUB_ACTIONS") != "true":
        print(
            "pr_publish.py: --write is only available inside GitHub Actions",
            file=sys.stderr,
        )
        return pr_cli.EXIT_OUTSIDE_ACTIONS

    if options["hold"] is True:
        try:
            payload = hold_live(
                str(options["repo"]),
                int(options["pr"]),
                write=options["write"] is True,
                client=client,
            )
        except pr_github_client.MissingTokenError as error:
            print(f"pr_publish.py: {error}", file=sys.stderr)
            return pr_cli.EXIT_MISSING_TOKEN
        except pr_github_client.FetchError as error:
            print(f"pr_publish.py: live fetch failed: {error}", file=sys.stderr)
            return pr_cli.EXIT_FETCH_FAILED
        except pr_plan.ArtifactError as error:
            print(f"pr_publish.py: {error}", file=sys.stderr)
            return pr_cli.EXIT_BAD_INPUT
        return _emit(payload, options["write"] is True)

    try:
        assessment = pr_cli.read_json_object(str(options["assessment"]), "--assessment")
        review = pr_cli.read_json_object(str(options["review"]), "--review")
        if options["live"] is True:
            try:
                payload = publish_live(
                    str(options["repo"]),
                    int(options["pr"]),
                    assessment,
                    review,
                    write=options["write"] is True,
                    client=client,
                    status_url=options["status_url"],
                )
            except pr_github_client.MissingTokenError as error:
                print(f"pr_publish.py: {error}", file=sys.stderr)
                return pr_cli.EXIT_MISSING_TOKEN
            except pr_github_client.FetchError as error:
                print(f"pr_publish.py: live fetch failed: {error}", file=sys.stderr)
                _append_summary(
                    options["summary"], f"### PR review decision\n\n- live fetch failed: {error}\n"
                )
                return pr_cli.EXIT_FETCH_FAILED
        else:
            context = pr_cli.read_json_object(str(options["context"]), "--context")
            payload = pr_plan.plan_publish(
                context,
                assessment,
                review,
                auto_merge=os.environ.get(AUTO_MERGE_ENV),
                status_url=options["status_url"],
            )
    except (pr_cli.InputError, pr_plan.ArtifactError, pr_apply.PlanError) as error:
        print(f"pr_publish.py: {error}", file=sys.stderr)
        return pr_cli.EXIT_BAD_INPUT

    status = _emit(payload, options["write"] is True)
    summary = pr_summary.render_summary(payload, review)
    if not _append_summary(options["summary"], summary) and status == pr_cli.EXIT_OK:
        return pr_cli.EXIT_OUTPUT_FAILED
    return status


def _emit(payload: dict, write: bool) -> int:
    pr_cli.print_json(payload)
    if write and payload.get("ok") is False:
        return pr_cli.EXIT_ACTION_FAILED
    return pr_cli.EXIT_OK


def _append_summary(path: object, text: str) -> bool:
    """Append ``text`` to the --summary file; False when it cannot be written."""
    if not isinstance(path, str):
        return True
    try:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(text)
    except OSError as error:
        print(f"pr_publish.py: cannot write --summary: {error}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
