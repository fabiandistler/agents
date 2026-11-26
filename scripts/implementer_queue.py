#!/usr/bin/env python3
"""Start the next issue waiting for the implementer, once no implementer run is working.

`ready-for-agent` is the queue: implementer_claim.py leaves the label on an
issue it stops as `at-capacity` or `blocked` when the caller's implementer
names this queue (`queue_workflow`), so the issue waits. This script
runs, model-free, after an implementer run ends, when an issue closes (a
blocker may be done) and on a schedule. It dispatches the implementer workflow
for one waiting issue, so no person has to add the label again.

It dispatches nothing while an implementer run is working (the claim's capacity
gate reads the same runs), so a run that stops `at-capacity` and ends cannot
start another one: no loop of model starts while one run works. The capacity
gate stays the only arbiter of who works; this script only picks the next
dispatch.

A waiting issue is an open issue with `ready-for-agent`. Lowest number first,
it is skipped when:

- its latest implementer run, found by its run name (`factory_handoff`),
  has not completed, or ended other than success or skipped: a running issue is
  handled, and a failed or cancelled one waits for a person (and the Fix task),
  so a failing issue is not dispatched again and again;
- its branch exists: a run claimed it and ended without a pull request;
- a pull request holds it, it has no contract, or a blocker is not done, by the
  claim's own checks.

The dispatch goes to the implementer's workflow file on the default branch,
with `inputs.issue`. GITHUB_TOKEN may do that: a workflow_dispatch "always
creates a workflow run" (GitHub docs, "Triggering a workflow", read
2026-11-13). The run's actor is the workflow bot
(`factory_handoff.WORKFLOW_BOT_LOGIN`), which the implementer's
claude-code-action step admits only because it lists it in `allowed_bots`. A
run started this way starts no `workflow_run` workflow, so the implementer's
model-free follow-up job dispatches this queue and, unless the run succeeded,
the Fix task by `workflow_dispatch` (#863; docs/agents/implementer-queue.md).

Standard library only. Prints one JSON object; errors name the API call and
status, never issue text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field

import agent_run_capacity
from factory_handoff import READY_FOR_AGENT, implementer_run_issue
from implementer_blockers import find_blockers
from implementer_capacity import MAX_WORKING_RUNS
from implementer_claim import HTTP_NOT_FOUND, pull_request_holding_issue
from implementer_contract import contract_text, read_ticket
from implementer_setup import (
    BRANCH_PREFIX,
    IMPLEMENT_JOB,
    IMPLEMENTER_WORKFLOW,
    ImplementerSetup,
    branch_prefix,
    workflow_file,
)
from pr_github_client import (
    PER_PAGE,
    REPO_PATTERN,
    FetchError,
    GitHubClient,
    MissingTokenError,
    get_json,
    paginate,
)

DISPATCHED = "dispatched"
BUSY = "busy"
EMPTY = "empty"
FAILED = "failed"

EXIT_OK = 0
EXIT_FAILED = 1

# The conclusions of a latest run after which an issue may be dispatched: the run
# ended normally (a stop at capacity or a blocked ticket), or its job was skipped
# (another label's event).
DISPATCHABLE_CONCLUSIONS = frozenset({"success", "skipped"})

# Why an issue was passed over; fixed codes, never issue text.
RUN_ACTIVE = "run-active"
RUN_FAILED = "run-failed"
HAS_BRANCH = "branch"
HELD_BY_PULL_REQUEST = "pull-request"
NO_CONTRACT = "no-contract"
BLOCKED = "blocked"

HELP_EPILOG = """\
stdout: JSON with outcome, issue, dry_run, skipped ({"issue", "reason"} per passed-over issue;
        "reason" if failed).
outcomes (exit 0 unless failed):
  dispatched  the implementer was dispatched for "issue" (with --dry-run: would be)
  busy        an implementer run is working; nothing dispatched, nothing else read
  empty       no issue waits, or every waiting one was skipped
  failed      an API error (exit 1); nothing more dispatched
skip reasons: run-active, run-failed, branch, pull-request, no-contract, blocked.
order: lowest issue number first.
env: GH_TOKEN (needs Actions write to dispatch; read access to issues, pulls, contents, Actions).

examples:
  implementer_queue.py --repo owner/repo --dry-run
  implementer_queue.py --repo owner/repo --workflow-file implementer.yml --job-name implement \\
      --branch-prefix agent/issue-
  implementer_queue.py --help
"""


@dataclass(frozen=True)
class Skip:
    issue: int
    reason: str


@dataclass(frozen=True)
class QueueOutcome:
    outcome: str
    issue: int | None = None
    dry_run: bool = False
    skipped: list[Skip] = field(default_factory=list)


def waiting_issues(client: GitHubClient, repo: str) -> list[int]:
    """Open issues (not pull requests) labelled `ready-for-agent`, lowest number first."""
    path = f"/repos/{repo}/issues"
    numbers: list[int] = []
    for issue in paginate(client, path, params={"state": "open", "labels": READY_FOR_AGENT}):
        number = issue.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            raise FetchError(f"GitHub API returned a malformed issue for {path}")
        if "pull_request" not in issue:
            numbers.append(number)
    return sorted(numbers)


def latest_runs(client: GitHubClient, repo: str, workflow: str) -> dict[int, dict]:
    """The newest run of ``workflow`` per issue, from its run name; one page, newest first.

    An issue whose last run is older than the page reads as having none, which
    is right: such a run ended long ago.
    """
    path = f"/repos/{repo}/actions/workflows/{workflow}/runs"
    listing = get_json(client, path, params={"per_page": PER_PAGE})
    runs = listing.get("workflow_runs") if isinstance(listing, dict) else None
    if not isinstance(runs, list):
        raise FetchError(f"GitHub API returned an unexpected payload for {path}")
    newest: dict[int, dict] = {}
    for run in runs:
        if not isinstance(run, dict):
            raise FetchError(f"GitHub API returned a malformed run for {path}")
        issue = implementer_run_issue(run.get("display_title"))
        if issue is not None:
            newest.setdefault(issue, run)
    return newest


def _run_skip_reason(run: dict | None) -> str | None:
    if run is None:
        return None
    if run.get("status") != "completed":
        return RUN_ACTIVE
    if run.get("conclusion") not in DISPATCHABLE_CONCLUSIONS:
        return RUN_FAILED
    return None


def _branch_exists(client: GitHubClient, repo: str, branch: str) -> bool:
    try:
        get_json(client, f"/repos/{repo}/git/ref/heads/{branch}")
    except FetchError as error:
        if error.status == HTTP_NOT_FOUND:
            return False
        raise
    return True


def _skip_reason(
    client: GitHubClient, repo: str, issue: int, latest_run: dict | None, setup: ImplementerSetup
) -> str | None:
    """Why ``issue`` must not be dispatched, cheapest check first; None if it may be."""
    run_reason = _run_skip_reason(latest_run)
    if run_reason is not None:
        return run_reason
    branch = setup.branch(issue)
    if _branch_exists(client, repo, branch):
        return HAS_BRANCH
    if pull_request_holding_issue(client, repo, issue, branch) is not None:
        return HELD_BY_PULL_REQUEST
    ticket = read_ticket(client, repo, issue)
    if contract_text(ticket, issue) is None:
        return NO_CONTRACT
    blockers, unresolved = find_blockers(client, repo, issue, ticket)
    if blockers or unresolved:
        return BLOCKED
    return None


def _default_branch(client: GitHubClient, repo: str) -> str:
    path = f"/repos/{repo}"
    repository = get_json(client, path)
    branch = repository.get("default_branch") if isinstance(repository, dict) else None
    if not isinstance(branch, str) or not branch:
        raise FetchError(f"GitHub API returned a malformed repository for {path}")
    return branch


def start_next(
    client: GitHubClient, repo: str, setup: ImplementerSetup, *, dry_run: bool
) -> QueueOutcome:
    """Dispatch the implementer for the first dispatchable waiting issue, unless a run works."""
    working = agent_run_capacity.working_runs(client, repo, setup.workflow_file, (setup.job_name,))
    if len(working) >= MAX_WORKING_RUNS:
        return QueueOutcome(BUSY, dry_run=dry_run)
    runs = latest_runs(client, repo, setup.workflow_file)
    skipped: list[Skip] = []
    for issue in waiting_issues(client, repo):
        reason = _skip_reason(client, repo, issue, runs.get(issue), setup)
        if reason is not None:
            skipped.append(Skip(issue, reason))
            continue
        if not dry_run:
            client.post(
                f"/repos/{repo}/actions/workflows/{setup.workflow_file}/dispatches",
                {"ref": _default_branch(client, repo), "inputs": {"issue": str(issue)}},
            )
        return QueueOutcome(DISPATCHED, issue, dry_run, skipped)
    return QueueOutcome(EMPTY, dry_run=dry_run, skipped=skipped)


def _repo_argument(value: str) -> str:
    if not REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("must be OWNER/REPO")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch the implementer for the next waiting issue, once no run is working.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", required=True, type=_repo_argument, help="OWNER/REPO")
    parser.add_argument(
        "--workflow-file",
        default=IMPLEMENTER_WORKFLOW,
        help="the implementer's caller workflow file, which is dispatched (default: %(default)s)",
    )
    parser.add_argument(
        "--job-name",
        default=IMPLEMENT_JOB,
        help="the implementer job; also matches '<caller job> / <name>' (default: %(default)s)",
    )
    parser.add_argument(
        "--branch-prefix",
        default=BRANCH_PREFIX,
        help="branch name before the issue number; ends in / or - (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the pick and dispatch nothing"
    )
    args = parser.parse_args(argv)

    try:
        # An explicit file name: GITHUB_WORKFLOW_REF here names this script's own workflow.
        setup = ImplementerSetup(
            workflow_file(args.workflow_file), args.job_name, branch_prefix(args.branch_prefix)
        )
        token = os.environ.get("GH_TOKEN")
        if not token:
            raise MissingTokenError("GH_TOKEN is not set")
        picked = start_next(GitHubClient(token), args.repo, setup, dry_run=args.dry_run)
    except FetchError as error:
        print(json.dumps({"outcome": FAILED, "reason": str(error)}))
        return EXIT_FAILED
    print(json.dumps(asdict(picked)))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
