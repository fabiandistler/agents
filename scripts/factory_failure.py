#!/usr/bin/env python3
"""The Fix task: file one failed factory run as one deduplicated issue.

Model-free. It reads the failed run, its jobs and the first failed job's check
annotations, plans with ``factory_failure_policy.plan`` and prints the plan as
JSON. With ``--write`` it reads everything again right before writing, then
comments on the open issue for the failure signature or files a new one.

Standard library only.
"""

from __future__ import annotations

import datetime
import os
import sys
from typing import Protocol

import pr_cli
import pr_github_client
from factory_failure_policy import (
    AUTHOR,
    LABEL,
    LABEL_COLOR,
    LABEL_DESCRIPTION,
    UNKNOWN,
    failure_reason,
    find_issues,
    first_failure,
    fix_issue_number,
    plan,
    signature,
    skip_reason,
)
from pr_actions import Operation
from pr_apply import WriteClient, send_operation
from pr_github_client import PER_PAGE, GitHubClient, ReadClient, get_json, paginate

SCRIPT = "factory_failure.py"

USAGE = f"""\
usage: factory_failure.py --repo O/R --run-id N [--write]

File a failed factory workflow run as an issue, one per failure signature; a
recurring failure becomes a comment on its open issue. Prints the plan as JSON
and writes only with --write. Runs that did not fail, and workflows that are
not watched, plan nothing.

  --repo O/R     repository as OWNER/REPO
  --run-id N     the workflow run id
  --write        apply the plan; only inside GitHub Actions
  -h, --help     show this message
env: GITHUB_TOKEN (actions: read, checks: read; issues: write with --write)

examples:
  python3 scripts/factory_failure.py --repo fabiandistler/agents --run-id 123456789
  python3 scripts/factory_failure.py --repo fabiandistler/agents --run-id 123456789 --write

{pr_cli.exit_help(0, 1, 2, 4, 5, 7)}
"""


class ApplyError(RuntimeError):
    """A write to GitHub failed after the plan was made."""


class FixTaskClient(ReadClient, WriteClient, Protocol):
    """Reads the failed run and writes the issue; ``GitHubClient`` and fakes implement it."""


def _client(client: FixTaskClient | None) -> FixTaskClient:
    if client is not None:
        return client
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise pr_github_client.MissingTokenError("GITHUB_TOKEN is not set")
    return GitHubClient(token)


def _object(client: ReadClient, path: str, params: dict | None = None) -> dict:
    payload = get_json(client, path, params)
    if not isinstance(payload, dict):
        raise pr_github_client.FetchError(f"GitHub API returned an unexpected payload for {path}")
    return payload


def _login(entry: dict) -> str:
    user = entry.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    return login if isinstance(login, str) else ""


def _issue(entry: dict) -> dict:
    return {
        "number": entry.get("number"),
        "state": entry.get("state"),
        "author": _login(entry),
        "body": entry.get("body") or "",
        "labels": [
            label["name"]
            for label in entry.get("labels") or []
            if isinstance(label, dict) and isinstance(label.get("name"), str)
        ],
    }


def _with_comments(client: ReadClient, repo: str, issue: dict) -> dict:
    comments = paginate(client, f"/repos/{repo}/issues/{issue['number']}/comments")
    return {
        **issue,
        "comments": [{"author": _login(c), "body": c.get("body") or ""} for c in comments],
    }


def _run(client: ReadClient, repo: str, run_id: int) -> dict:
    run = _object(client, f"/repos/{repo}/actions/runs/{run_id}")
    return {
        "id": run_id,
        "attempt": run.get("run_attempt") or 1,
        "path": run.get("path") or "",
        "name": run.get("name") or "",
        "url": run.get("html_url") or "",
        "display_title": run.get("display_title") or "",
        "conclusion": run.get("conclusion"),
    }


def _failure(client: ReadClient, repo: str, run: dict) -> dict:
    path = f"/repos/{repo}/actions/runs/{run['id']}/attempts/{run['attempt']}/jobs"
    # One page of PER_PAGE (100) jobs: the watched workflows have at most four
    # jobs and no matrix. A watched workflow past 100 jobs needs pagination here.
    jobs = _object(client, path, {"per_page": PER_PAGE}).get("jobs")
    if not isinstance(jobs, list):
        raise pr_github_client.FetchError(f"GitHub API returned no job list for {path}")
    failure = first_failure([job for job in jobs if isinstance(job, dict)])
    annotations: list[dict] = []
    if failure["job_id"] is not None:
        annotations = paginate(client, f"/repos/{repo}/check-runs/{failure['job_id']}/annotations")
    return {"job": failure["job"], "step": failure["step"], "reason": failure_reason(annotations)}


def make_plan(client: ReadClient, repo: str, run_id: int, date: str) -> dict:
    """Fetch every fact the planner needs for one run and plan its write."""
    run = _run(client, repo, run_id)
    if skip_reason(run) is not None:
        failure = {"job": UNKNOWN, "step": UNKNOWN, "reason": ""}
        return plan(run, failure, None, None, None, date)
    failure = _failure(client, repo, run)
    marker = signature(run["path"], failure["job"], failure["step"], failure["reason"])["marker"]
    issues = [
        _issue(entry)
        for entry in paginate(
            client,
            f"/repos/{repo}/issues",
            {"labels": LABEL, "state": "all", "creator": AUTHOR},
        )
        if "pull_request" not in entry
    ]
    open_issue, closed_issue = find_issues(issues, marker)
    if open_issue is not None:
        open_issue = _with_comments(client, repo, open_issue)
    fix_issue = None
    number = fix_issue_number(run)
    if number is not None:
        fix_issue = _with_comments(
            client, repo, _issue(_object(client, f"/repos/{repo}/issues/{number}"))
        )
    return plan(run, failure, open_issue, closed_issue, fix_issue, date)


def create_label(client: WriteClient, repo: str) -> None:
    """Create the ``factory-failure`` label; one that already exists counts as done."""
    label: dict[str, object] = {
        "name": LABEL,
        "color": LABEL_COLOR,
        "description": LABEL_DESCRIPTION,
    }
    try:
        send_operation(
            client,
            Operation(
                kind="create_label",
                method="POST",
                path=f"/repos/{repo}/labels",
                payload=label,
                tolerate="already_exists",
            ),
        )
    except pr_github_client.FetchError as error:
        raise ApplyError(str(error)) from error


def apply(client: WriteClient, repo: str, planned: dict) -> None:
    """Send the plan's one write: a comment or a new issue."""
    action = planned["action"]
    if action is None:
        return
    try:
        if action["kind"] == "comment":
            client.post(
                f"/repos/{repo}/issues/{action['number']}/comments", {"body": action["body"]}
            )
            return
        client.post(
            f"/repos/{repo}/issues",
            {"title": action["title"], "body": action["body"], "labels": action["labels"]},
        )
    except pr_github_client.FetchError as error:
        raise ApplyError(str(error)) from error


def _parse(argv: list[str]) -> dict | None:
    options = pr_cli.parse_flags(argv, ("--repo", "--run-id"), ("--write",))
    if options is None:
        return None
    if options["repo"] is None or options["run_id"] is None:
        raise pr_cli.UsageError("--repo and --run-id are both required")
    if not pr_github_client.REPO_PATTERN.fullmatch(str(options["repo"])):
        raise pr_cli.UsageError("--repo must be OWNER/REPO")
    run_id = str(options["run_id"])
    if not run_id.isdigit() or int(run_id) <= 0:
        raise pr_cli.UsageError("--run-id must be a positive integer")
    options["run_id"] = int(run_id)
    return options


def main(
    argv: list[str] | None = None, client: FixTaskClient | None = None, today: str | None = None
) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = _parse(arguments)
    except pr_cli.UsageError as error:
        return pr_cli.usage_failure(SCRIPT, USAGE, error)
    if options is None:
        print(USAGE, end="")
        return pr_cli.EXIT_OK
    write = options["write"] is True
    if write and os.environ.get("GITHUB_ACTIONS") != "true":
        print(f"{SCRIPT}: --write is only available inside GitHub Actions", file=sys.stderr)
        return pr_cli.EXIT_OUTSIDE_ACTIONS
    date = today or datetime.datetime.now(datetime.UTC).date().isoformat()
    repo = str(options["repo"])
    try:
        github = _client(client)
        planned = make_plan(github, repo, options["run_id"], date)
        if write and planned["action"] is not None:
            if planned["action"]["kind"] == "create_issue":
                # Before the re-read, so no other call sits between it and the
                # write. A plan that turns into a new issue only on the re-read
                # had a labelled match a moment ago, so the label exists.
                create_label(github, repo)
            # Re-read right before writing: a parallel run may have filed it.
            planned = make_plan(github, repo, options["run_id"], date)
            apply(github, repo, planned)
    except pr_github_client.MissingTokenError as error:
        print(f"{SCRIPT}: {error}", file=sys.stderr)
        return pr_cli.EXIT_MISSING_TOKEN
    except pr_github_client.FetchError as error:
        print(f"{SCRIPT}: GitHub fetch failed: {error}", file=sys.stderr)
        return pr_cli.EXIT_FETCH_FAILED
    except ApplyError as error:
        print(f"{SCRIPT}: GitHub write failed: {error}", file=sys.stderr)
        return pr_cli.EXIT_ACTION_FAILED
    pr_cli.print_json({**planned, "written": write and planned["action"] is not None})
    return pr_cli.EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
