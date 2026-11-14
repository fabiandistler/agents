#!/usr/bin/env python3
"""The Retro task's model-free gate: pick one merged agent PR and write its context.

About one merged `agent/issue-<n>` pull request in ten becomes a proposed change
to the factory's own instruction texts (ADR-0017, docs/agents/retro.md). This
script decides whether a run is due and which pull request it looks at; the
model only ever sees the context file it writes.

- Eligible: a merged pull request from an `agent/issue-<n>` branch of this
  repository, merged after the floor, the oldest commit on the default branch
  that touches `.github/workflows/retro.yml`. Earlier merges never count, and
  an unreadable floor fails the gate instead of counting from the start.
- Pending: the eligible ones merged after the newest one labelled `retro:done`
  (after the floor while there is none). Fewer than `--every` ends the run, as
  does an open pull request from an `agent/retro-*` branch.
- Selected: the pending one with the most non-pass review rounds (Rework
  markers by the review bot, plus one for a non-pass verdict label), the newest
  on a tie. `select` labels it `retro:done` before it prints, so the model job
  never starts on an unlabelled pull request.

The context holds only text authored by the repository's owner, members and
collaborators, the review bot and the Claude GitHub App: never an outsider's
comment. The App's pull request body and commits can repeat what it read, so
the model treats the whole file as data.

Standard library only. Errors name the API call, never issue or comment text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from implementer_contract import contract_text, read_ticket
from issue_triage_policy import TRUSTED_ASSOCIATIONS
from pr_actions import Operation
from pr_apply import WriteClient
from pr_apply import _send as send_operation
from pr_comment import COMMENT_AUTHOR, COMMENT_MARKER
from pr_github import PER_PAGE, get_json, paginate
from pr_github_client import REPO_PATTERN, FetchError, GitHubClient, MissingTokenError, ReadClient
from pr_labels import VERDICT_PREFIX

RETRO_WORKFLOW = ".github/workflows/retro.yml"
AGENT_BRANCH = re.compile(r"^agent/issue-([1-9][0-9]*)$")
RETRO_BRANCH_PREFIX = "agent/retro-"
RETRO_DONE = "retro:done"
RETRO_DONE_LABEL = ("5319e7", "The Retro task has looked at this merged agent pull request")
REWORK_MARKER = re.compile(r"<!-- rework-round:[^>]*-->")
NON_PASS_VERDICTS = frozenset(
    f"{VERDICT_PREFIX}{verdict}" for verdict in ("concerns", "block", "unavailable")
)
# The login the Claude GitHub App writes as: the implementer's and Rework's replies.
APP_AUTHOR = "claude[bot]"
DEFAULT_EVERY = 10
IMPLEMENTER_WORKFLOW = "implementer.yml"
SUMMARY_ARTIFACT = "run-summary"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_MISSING_TOKEN = 3
EXIT_FETCH_FAILED = 4
EXIT_NO_FLOOR = 5

HELP_EPILOG = """\
select prints one JSON object: {"selected", "issue", "reason", "pending",
"every", "floor", "implementer_run"}; "selected" is null when no retro is due.
Reads GITHUB_TOKEN (pull-requests and issues write, actions and contents read).

exit codes: 0 ok (also when nothing is selected); 2 usage error; 3 no
            GITHUB_TOKEN; 4 a GitHub request failed; 5 the floor commit of
            .github/workflows/retro.yml cannot be read.

examples:
  retro_gate.py select --repo fabiandistler/agents --every 10
  retro_gate.py context --repo fabiandistler/agents --pr 795 \\
      --run-summary summary/run-summary.md --output retro-context.md
"""


class GateClient(ReadClient, WriteClient, Protocol):
    """Reads and the label writes: ``GitHubClient`` and the tests' fake implement it."""


class FloorError(RuntimeError):
    """The commit that added the Retro workflow cannot be read."""


@dataclass(frozen=True)
class MergedPull:
    """A merged pull request from an `agent/issue-<n>` branch of this repository."""

    number: int
    issue: int
    merged_at: datetime
    labels: frozenset[str]

    @property
    def retro_done(self) -> bool:
        return RETRO_DONE in self.labels


@dataclass(frozen=True)
class Selection:
    """The gate's decision; ``selected`` is None when no retro is due."""

    selected: int | None
    issue: int | None
    reason: str
    pending: int
    every: int
    floor: str
    implementer_run: int | None = None


# --- Pure selection ----------------------------------------------------------


def _timestamp(value: object, what: str) -> datetime:
    if not isinstance(value, str):
        raise FetchError(f"GitHub API returned no {what}")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise FetchError(f"GitHub API returned a malformed {what}") from error


def merged_agent_pull(pull: dict, repo: str) -> MergedPull | None:
    """The pull request as a `MergedPull`, or None when it is not an eligible kind.

    Closed-unmerged pull requests, other branches, Retro branches and forks
    (anyone can name a fork branch `agent/issue-1`) are not.
    """
    if pull.get("merged_at") is None:
        return None
    head = _mapping(pull.get("head"))
    ref = head.get("ref")
    match = AGENT_BRANCH.fullmatch(ref) if isinstance(ref, str) else None
    full_name = _mapping(head.get("repo")).get("full_name")
    if match is None or not isinstance(full_name, str) or full_name.lower() != repo.lower():
        return None
    number = pull.get("number")
    if isinstance(number, bool) or not isinstance(number, int):
        raise FetchError("GitHub API returned a pull request without a number")
    labels = pull.get("labels")
    if not isinstance(labels, list):
        raise FetchError(f"GitHub API returned no labels for pull request #{number}")
    names = frozenset(
        label["name"]
        for label in labels
        if isinstance(label, dict) and isinstance(label.get("name"), str)
    )
    return MergedPull(
        number,
        int(match.group(1)),
        _timestamp(pull["merged_at"], "merge time"),
        names,
    )


def pending_pulls(pulls: list[MergedPull], floor: datetime) -> list[MergedPull]:
    """The eligible pull requests merged since the newest retro, or the floor."""
    eligible = [pull for pull in pulls if pull.merged_at > floor]
    done = [pull.merged_at for pull in eligible if pull.retro_done]
    since = max(done, default=floor)
    return [pull for pull in eligible if pull.merged_at > since]


def non_pass_rounds(pull: MergedPull, comments: list[dict]) -> int:
    """Rework markers by the review bot, plus one for a non-pass verdict at merge."""
    markers = {
        marker
        for comment in comments
        if _login(comment) == COMMENT_AUTHOR
        for marker in REWORK_MARKER.findall(_body(comment))
    }
    return len(markers) + (1 if pull.labels & NON_PASS_VERDICTS else 0)


def choose(pending: list[MergedPull], rounds: dict[int, int]) -> MergedPull:
    """The most non-pass rounds; the newest merge on a tie."""
    return max(pending, key=lambda pull: (rounds[pull.number], pull.merged_at, pull.number))


# --- GitHub reads ------------------------------------------------------------


def _mapping(value: object) -> dict:
    """A JSON object field, or an empty one when GitHub sent something else."""
    return value if isinstance(value, dict) else {}


def _login(item: dict) -> str:
    user = item.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    return login if isinstance(login, str) else ""


def _body(item: dict) -> str:
    body = item.get("body")
    return body if isinstance(body, str) else ""


def read_floor(client: ReadClient, repo: str) -> datetime:
    """The committer time of the oldest default-branch commit touching the Retro workflow."""
    try:
        repository = get_json(client, f"/repos/{repo}")
        branch = repository.get("default_branch") if isinstance(repository, dict) else None
        if not isinstance(branch, str) or not branch:
            raise FloorError(f"GitHub API returned no default branch for /repos/{repo}")
        commits = paginate(
            client, f"/repos/{repo}/commits", params={"path": RETRO_WORKFLOW, "sha": branch}
        )
    except FetchError as error:
        raise FloorError(f"cannot list the commits of {RETRO_WORKFLOW}: {error}") from error
    if not commits:
        raise FloorError(f"no commit on the default branch adds {RETRO_WORKFLOW}")
    commit = commits[-1].get("commit")
    committer = commit.get("committer") if isinstance(commit, dict) else None
    date = committer.get("date") if isinstance(committer, dict) else None
    try:
        return _timestamp(date, "commit time")
    except FetchError as error:
        raise FloorError(f"the floor commit of {RETRO_WORKFLOW} has no usable time") from error


def _open_retro_pull(client: ReadClient, repo: str) -> bool:
    for pull in paginate(client, f"/repos/{repo}/pulls", params={"state": "open"}):
        ref = _mapping(pull.get("head")).get("ref")
        if isinstance(ref, str) and ref.startswith(RETRO_BRANCH_PREFIX):
            return True
    return False


def _merged_pulls(client: ReadClient, repo: str) -> list[MergedPull]:
    pulls = paginate(client, f"/repos/{repo}/pulls", params={"state": "closed"})
    return [merged for pull in pulls if (merged := merged_agent_pull(pull, repo)) is not None]


def _issue_comments(client: ReadClient, repo: str, number: int) -> list[dict]:
    return paginate(client, f"/repos/{repo}/issues/{number}/comments")


def implementer_run(client: ReadClient, repo: str, issue: int) -> int | None:
    """The newest implementer run for the issue that kept a run-summary artifact."""
    title = f"implementer: issue #{issue}"
    path = f"/repos/{repo}/actions/workflows/{IMPLEMENTER_WORKFLOW}/runs"
    page = 1
    while True:
        # Newest first, page by page: the run can sit past the first page.
        payload = get_json(client, path, params={"per_page": PER_PAGE, "page": page})
        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list):
            raise FetchError(f"GitHub API returned no runs for {IMPLEMENTER_WORKFLOW}")
        for run in runs:
            if not isinstance(run, dict) or run.get("display_title") != title:
                continue
            run_id = run.get("id")
            if isinstance(run_id, bool) or not isinstance(run_id, int):
                continue
            artifacts = get_json(client, f"/repos/{repo}/actions/runs/{run_id}/artifacts")
            listed = artifacts.get("artifacts") if isinstance(artifacts, dict) else None
            if not isinstance(listed, list):
                raise FetchError(f"GitHub API returned no artifacts list for run {run_id}")
            if any(
                isinstance(artifact, dict)
                and artifact.get("name") == SUMMARY_ARTIFACT
                and not artifact.get("expired")
                for artifact in listed
            ):
                return run_id
        if len(runs) < PER_PAGE:
            return None
        page += 1


def label_done(client: GateClient, repo: str, number: int) -> None:
    """Create `retro:done` if missing, then put it on the pull request."""
    color, description = RETRO_DONE_LABEL
    send_operation(
        client,
        Operation(
            kind="set_labels",
            method="POST",
            path=f"/repos/{repo}/labels",
            payload={"name": RETRO_DONE, "color": color, "description": description},
            tolerate="already_exists",
        ),
    )
    send_operation(
        client,
        Operation(
            kind="set_labels",
            method="POST",
            path=f"/repos/{repo}/issues/{number}/labels",
            payload={"labels": [RETRO_DONE]},
        ),
    )


def run_gate(client: GateClient, repo: str, every: int) -> Selection:
    """Decide whether a retro is due, and label the selected pull request."""
    floor = read_floor(client, repo)
    floor_text = floor.isoformat()
    pending = pending_pulls(_merged_pulls(client, repo), floor)
    if len(pending) < every:
        reason = (
            f"{len(pending)} merged agent pull request(s) since the last retro, fewer than {every}"
        )
        return Selection(None, None, reason, len(pending), every, floor_text)
    if _open_retro_pull(client, repo):
        reason = "an agent/retro-* pull request is still open"
        return Selection(None, None, reason, len(pending), every, floor_text)
    rounds = {
        pull.number: non_pass_rounds(pull, _issue_comments(client, repo, pull.number))
        for pull in pending
    }
    selected = choose(pending, rounds)
    run_id = implementer_run(client, repo, selected.issue)
    label_done(client, repo, selected.number)
    reason = f"{rounds[selected.number]} non-pass review round(s), the most of {len(pending)}"
    return Selection(
        selected.number, selected.issue, reason, len(pending), every, floor_text, run_id
    )


# --- Context -----------------------------------------------------------------


def _is_trusted(item: dict) -> bool:
    return item.get("author_association") in TRUSTED_ASSOCIATIONS


def _section(title: str, parts: list[str]) -> str:
    text = "\n\n---\n\n".join(part.strip() for part in parts if part.strip())
    return f"## {title}\n\n{text or '(none)'}\n"


def build_context(
    client: ReadClient, repo: str, number: int, run_summary: str | None = None
) -> str:
    """The Retro model's whole view of one merged agent pull request, trusted text only."""
    pr_path = f"/repos/{repo}/pulls/{number}"
    pull = get_json(client, pr_path)
    merged = merged_agent_pull(pull, repo) if isinstance(pull, dict) else None
    if merged is None:
        raise FetchError(f"{pr_path} is not a merged agent/issue-<n> pull request")
    commits = paginate(client, f"{pr_path}/commits")
    files = paginate(client, f"{pr_path}/files")
    comments = _issue_comments(client, repo, number)
    reviews = paginate(client, f"{pr_path}/reviews")
    review_comments = paginate(client, f"{pr_path}/comments")
    contract = contract_text(read_ticket(client, repo, merged.issue), merged.issue)

    commit_lines = []
    for commit in commits:
        message = _mapping(commit.get("commit")).get("message")
        sha = commit.get("sha")
        if isinstance(message, str) and isinstance(sha, str):
            commit_lines.append(f"### {sha[:12]}\n\n{message}")
    stat = [
        f"- `{entry.get('filename')}` +{entry.get('additions')} -{entry.get('deletions')}"
        for entry in files
    ]
    sticky = [
        _body(comment)
        for comment in comments
        if _login(comment) == COMMENT_AUTHOR and COMMENT_MARKER in _body(comment)
    ]
    rework = [
        _body(comment)
        for comment in comments
        if _login(comment) == COMMENT_AUTHOR and REWORK_MARKER.search(_body(comment))
    ]
    app_replies = [_body(comment) for comment in comments if _login(comment) == APP_AUTHOR]
    trusted = [
        f"{kind} by @{_login(item)}:\n\n{_body(item)}"
        for kind, items in (
            ("Comment", comments),
            ("Review", reviews),
            ("Review comment", review_comments),
        )
        for item in items
        if _is_trusted(item) and _body(item).strip()
    ]

    header = (
        f"# Retro context for pull request #{number}\n\n"
        f"Branch `agent/issue-{merged.issue}`, merged {merged.merged_at.isoformat()}, "
        f"labels: {', '.join(sorted(merged.labels)) or '(none)'}.\n"
    )
    sections = [
        header,
        _section("Pull request body", [_body(pull)]),
        _section("Commits", commit_lines),
        _section("Diff stat", ["\n".join(stat)]),
        _section(f"Issue contract (#{merged.issue})", [contract or ""]),
        _section("Review comment (sticky, by the review bot)", sticky),
        _section("Rework rounds (by the review bot)", rework),
        _section("Replies by the Claude GitHub App", app_replies),
        _section("Comments by people with write access", trusted),
        _section("Implementer run summary", [run_summary or ""]),
    ]
    return "\n".join(sections)


# --- CLI ---------------------------------------------------------------------


def _repo_argument(value: str) -> str:
    if not REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("must be OWNER/REPO")
    return value


def _positive(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("must be a positive integer")
    return int(value)


def _every(value: str) -> int:
    # An unset repository variable reaches the workflow as an empty string.
    return DEFAULT_EVERY if value == "" else _positive(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The Retro task's gate: select one merged agent PR, or write its context.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("select", help="decide, label retro:done, print JSON")
    select.add_argument("--repo", required=True, type=_repo_argument)
    select.add_argument(
        "--every", type=_every, default=DEFAULT_EVERY, help="threshold (default 10; empty = 10)"
    )
    context = commands.add_parser("context", help="write the context file for one PR")
    context.add_argument("--repo", required=True, type=_repo_argument)
    context.add_argument("--pr", required=True, type=_positive)
    context.add_argument("--run-summary", type=Path, help="the implementer's run-summary.md")
    context.add_argument("--output", required=True, type=Path)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return EXIT_OK if exit_.code == 0 else EXIT_USAGE

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("retro_gate.py: GITHUB_TOKEN is not set", file=sys.stderr)
        return EXIT_MISSING_TOKEN
    client = GitHubClient(token)
    try:
        if args.command == "select":
            print(json.dumps(asdict(run_gate(client, args.repo, args.every))))
        else:
            summary = None
            if args.run_summary is not None and args.run_summary.is_file():
                summary = args.run_summary.read_text(encoding="utf-8")
            text = build_context(client, args.repo, args.pr, summary)
            args.output.write_text(text, encoding="utf-8")
            print(json.dumps({"pr": args.pr, "output": str(args.output), "bytes": len(text)}))
    except FloorError as error:
        print(f"retro_gate.py: {error}", file=sys.stderr)
        return EXIT_NO_FLOOR
    except (MissingTokenError, FetchError) as error:
        print(f"retro_gate.py: {error}", file=sys.stderr)
        return EXIT_FETCH_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
