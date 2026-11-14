#!/usr/bin/env python3
"""The automated issue triage, one subcommand per stage of issue-triage.yml.

- ``assess`` (read token, no model): fetch the issue and its comments, decide
  with ``issue_triage_policy.assess`` whether the trigger may start a model
  run, and write the context JSON.
- ``triage`` (model token, no GitHub token): ask the model through the
  read-only ``claude -p`` workspace call and write the triage artifact.
- ``publish`` (write token, no model): re-fetch the labels, post the triage
  comment and move the state label; the bot only ever sets ``needs-info`` or
  keeps ``needs-triage``. A reporter's reply moves ``needs-info`` back to
  ``needs-triage`` even when no triage ran. Without ``--write`` it prints the
  plan only.

Standard library only.
"""

from __future__ import annotations

import os
import sys
import urllib.parse
from pathlib import Path

import pr_cli
import pr_github_client
from issue_triage_answer import AnswerError, artifact, build_request, parse_answer, render_comment
from issue_triage_policy import (
    NEEDS_TRIAGE,
    TRIGGERS,
    assess,
    plan_labels,
    unchanged_since_assessment,
)
from pr_github_client import GitHubClient, get_json, paginate
from pr_review_claude import TOKEN_ENV, ProviderError, run_claude

SCRIPT = "issue_triage.py"
SCHEMA_VERSION = 1

USAGE = f"""\
usage: issue_triage.py assess  --repo O/R --issue N --trigger T --output FILE
       issue_triage.py triage  --context FILE --workspace DIR
       issue_triage.py publish --repo O/R --context FILE [--triage FILE]
                               [--run-url URL] [--write]

Triage one GitHub issue in three stages. `assess` prints a JSON summary and
writes the full context to FILE. `triage` prints the triage artifact; a
missing token or a failed `claude` call is status `unavailable`, an
off-format answer `invalid`, both with exit 0. `publish` prints its plan and
applies it only with --write.

  --repo O/R        repository as OWNER/REPO
  --issue N         issue number
  --trigger T       one of {", ".join(TRIGGERS)}
  --output FILE     where `assess` writes the context JSON
  --context FILE    context JSON written by `assess`
  --workspace DIR   checkout the model may read (Read, Grep, Glob only)
  --triage FILE     artifact written by `triage`; omit it when no triage ran
  --run-url URL     link to the workflow run, shown in the comment
  --write           apply the plan; only inside GitHub Actions
  -h, --help        show this message
env: GITHUB_TOKEN (assess, publish), CLAUDE_CODE_OAUTH_TOKEN (triage),
  ISSUE_TRIAGE_MODEL (Claude Code model alias or name, default sonnet)

examples:
  python3 scripts/issue_triage.py assess --repo fabiandistler/agents --issue 735 \\
      --trigger dispatch --output context.json
  python3 scripts/issue_triage.py triage --context context.json --workspace . > triage.json
  python3 scripts/issue_triage.py publish --repo fabiandistler/agents \\
      --context context.json --triage triage.json

{pr_cli.exit_help(0, 1, 2, 3, 4, 5, 6, 7)}
"""

FLAGS = {
    "assess": (("--repo", "--issue", "--trigger", "--output"), ()),
    "triage": (("--context", "--workspace"), ()),
    "publish": (("--repo", "--context", "--triage", "--run-url"), ("--write",)),
}
REQUIRED = {
    "assess": ("repo", "issue", "trigger", "output"),
    "triage": ("context", "workspace"),
    "publish": ("repo", "context"),
}


def _client(client: object | None) -> object:
    if client is not None:
        return client
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise pr_github_client.MissingTokenError("GITHUB_TOKEN is not set")
    return GitHubClient(token)


def _login(entry: dict) -> str:
    user = entry.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    return login if isinstance(login, str) else ""


def _label_names(entry: dict) -> list[str]:
    labels = entry.get("labels")
    if not isinstance(labels, list):
        raise pr_github_client.FetchError("GitHub API returned an issue without labels")
    return [label["name"] for label in labels if isinstance(label, dict) and "name" in label]


def _fetch_issue(client, repo: str, number: int) -> dict:
    issue = get_json(client, f"/repos/{repo}/issues/{number}")
    if not isinstance(issue, dict):
        raise pr_github_client.FetchError("GitHub API returned an unexpected issue payload")
    return issue


# --- assess ------------------------------------------------------------------


def fetch_context(client, repo: str, number: int, trigger: str) -> dict:
    """Fetch issue ``number`` and decide whether ``trigger`` may triage it."""
    issue = _fetch_issue(client, repo, number)
    comments = [
        {"author": _login(entry), "body": entry.get("body") or ""}
        for entry in paginate(client, f"/repos/{repo}/issues/{number}/comments")
    ]
    labels = _label_names(issue)
    user = issue.get("user")
    if not isinstance(user, dict):
        user = {}
    facts = {
        "state": issue.get("state"),
        "is_pull_request": "pull_request" in issue,
        "author_type": user.get("type"),
        "author_association": issue.get("author_association"),
        "labels": labels,
    }
    decision = assess(facts, comments, trigger)
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": repo,
        "number": number,
        "trigger": trigger,
        "author": _login(issue),
        "title": issue.get("title") or "",
        "body": issue.get("body") or "",
        "other_labels": [label for label in labels if label not in decision["states"]],
        "comments": comments,
        **decision,
    }


# --- triage ------------------------------------------------------------------


def triage(context: dict, workspace: Path, transport=None, token: str | None = None) -> dict:
    """Ask the model about an eligible context; never raises for a failed call."""
    if context.get("eligible") is not True:
        raise pr_cli.InputError("the context is not eligible for triage")
    oauth_token = token if token is not None else os.environ.get(TOKEN_ENV)
    if not oauth_token:
        print(f"{SCRIPT}: {TOKEN_ENV} is not set", file=sys.stderr)
        return artifact(context, "unavailable")
    request = build_request(context)
    try:
        if transport is None:
            text = run_claude(request, oauth_token, workspace=workspace)
        else:
            text = transport(request)
    except ProviderError as error:
        # The run stays green on a failed call, so this line is the only trace of why.
        print(f"{SCRIPT}: {error}", file=sys.stderr)
        return artifact(context, "unavailable")
    try:
        return artifact(context, "ok", parse_answer(text))
    except AnswerError as error:
        print(f"{SCRIPT}: the answer is off-format: {error}", file=sys.stderr)
        return artifact(context, "invalid")


# --- publish -----------------------------------------------------------------


def plan(
    context: dict, result: dict | None, current_labels: list[str], run_url: str | None
) -> dict:
    """The comment and label changes for one triage result, or why there are none.

    ``result`` is None when no triage ran. A usable result gets a comment and
    its label move; without one, a reply still moves needs-info back to
    needs-triage (``requeue``), with no comment.
    """
    if result is not None and result.get("number") != context.get("number"):
        raise pr_cli.InputError("the triage artifact belongs to another issue")
    usable = result is not None and result.get("status") == "ok"
    skip = None
    if not unchanged_since_assessment(context["states"], current_labels):
        skip = "the state labels changed since the assessment"
    elif not usable and context.get("requeue") is not True:
        skip = context.get("skip_reason") or f"the triage is {(result or {}).get('status')}"
    if skip is not None:
        return {"number": context["number"], "skip_reason": skip, "comment": None, "add": []}
    if not usable:
        return {
            "number": context["number"],
            "skip_reason": None,
            "comment": None,
            **plan_labels(current_labels, NEEDS_TRIAGE),
        }
    return {
        "number": context["number"],
        "skip_reason": None,
        "comment": render_comment(result, context["author"], run_url),
        **plan_labels(current_labels, result["state"]),
    }


class ApplyError(RuntimeError):
    """A write to GitHub failed after the plan was made."""


def apply(client, repo: str, planned: dict) -> None:
    """Post the comment first, so a failed label write still leaves the reasoning."""
    if planned["skip_reason"] is not None:
        return
    path = f"/repos/{repo}/issues/{planned['number']}"
    try:
        if planned["comment"] is not None:
            client.post(f"{path}/comments", {"body": planned["comment"]})
        for label in planned["remove"]:
            client.delete(f"{path}/labels/{urllib.parse.quote(label, safe='')}")
        if planned["add"]:
            client.post(f"{path}/labels", {"labels": planned["add"]})
    except pr_github_client.FetchError as error:
        raise ApplyError(str(error)) from error


def publish(options: dict, client) -> dict:
    context = pr_cli.read_json_object(str(options["context"]), "--context")
    result = None
    if options["triage"] is not None:
        result = pr_cli.read_json_object(str(options["triage"]), "--triage")
    repo = str(options["repo"])
    issue = _fetch_issue(client, repo, int(context["number"]))
    planned = plan(context, result, _label_names(issue), options["run_url"])
    if options["write"] is True:
        apply(client, repo, planned)
    return {**planned, "written": options["write"] is True}


# --- CLI ---------------------------------------------------------------------


def _parse(argv: list[str]) -> tuple[str, dict] | None:
    if not argv or argv[0] in ("-h", "--help"):
        return None
    command = argv[0]
    if command not in FLAGS:
        raise pr_cli.UsageError(f"unknown command: {command}")
    values, switches = FLAGS[command]
    options = pr_cli.parse_flags(argv[1:], values, switches)
    if options is None:
        return None
    missing = [f"--{name}" for name in REQUIRED[command] if options[name] is None]
    if missing:
        raise pr_cli.UsageError(f"{command} needs {', '.join(missing)}")
    if "repo" in options and not pr_github_client.REPO_PATTERN.fullmatch(str(options["repo"])):
        raise pr_cli.UsageError("--repo must be OWNER/REPO")
    if command == "assess":
        if options["trigger"] not in TRIGGERS:
            raise pr_cli.UsageError(f"--trigger must be one of {', '.join(TRIGGERS)}")
        if not str(options["issue"]).isdigit() or int(str(options["issue"])) <= 0:
            raise pr_cli.UsageError("--issue must be a positive integer")
    return command, options


def _run(command: str, options: dict, client) -> int:
    if command == "assess":
        context = fetch_context(
            _client(client), str(options["repo"]), int(str(options["issue"])), options["trigger"]
        )
        if not pr_cli.write_json_file(SCRIPT, "--output", str(options["output"]), context):
            return pr_cli.EXIT_OUTPUT_FAILED
        pr_cli.print_json({key: context[key] for key in ("number", "eligible", "skip_reason")})
        return pr_cli.EXIT_OK
    if command == "triage":
        context = pr_cli.read_json_object(str(options["context"]), "--context")
        pr_cli.print_json(triage(context, Path(str(options["workspace"]))))
        return pr_cli.EXIT_OK
    if options["write"] is True and os.environ.get("GITHUB_ACTIONS") != "true":
        print(f"{SCRIPT}: --write is only available inside GitHub Actions", file=sys.stderr)
        return pr_cli.EXIT_OUTSIDE_ACTIONS
    pr_cli.print_json(publish(options, _client(client)))
    return pr_cli.EXIT_OK


def main(argv: list[str] | None = None, client=None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        parsed = _parse(arguments)
    except pr_cli.UsageError as error:
        return pr_cli.usage_failure(SCRIPT, USAGE, error)
    if parsed is None:
        print(USAGE, end="")
        return pr_cli.EXIT_OK
    command, options = parsed
    try:
        return _run(command, options, client)
    except pr_cli.InputError as error:
        print(f"{SCRIPT}: {error}", file=sys.stderr)
        return pr_cli.EXIT_BAD_INPUT
    except pr_github_client.MissingTokenError as error:
        print(f"{SCRIPT}: {error}", file=sys.stderr)
        return pr_cli.EXIT_MISSING_TOKEN
    except pr_github_client.FetchError as error:
        print(f"{SCRIPT}: GitHub fetch failed: {error}", file=sys.stderr)
        return pr_cli.EXIT_FETCH_FAILED
    except ApplyError as error:
        print(f"{SCRIPT}: GitHub write failed: {error}", file=sys.stderr)
        return pr_cli.EXIT_ACTION_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
