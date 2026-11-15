#!/usr/bin/env python3
"""Start the follow-ups of an implementer run that the queue dispatched (#863).

implementer_queue.py dispatches the implementer with the job's GITHUB_TOKEN.
Such a run starts no `workflow_run` workflow when it ends, so neither the
caller's queue nor its Fix task would follow it up. The reusable implementer's
model-free follow-up job runs this script after the implement job instead. A
`workflow_dispatch` made with GITHUB_TOKEN does create a run (GitHub docs,
"Triggering a workflow").

It dispatches, on ``--ref``:

- the Fix task with this run's id and `dry_run: false`, unless the implement
  job succeeded. The Fix task's policy decides what is filed
  (FAILED_CONCLUSIONS in factory_failure_policy.py), and factory_failure.py
  waits for this run to complete first;
- the queue with `dry_run: false`, which picks the next waiting issue. The
  capacity gate counts only the implement job, so this run, past it, does not
  keep the queue busy.

An empty workflow argument dispatches nothing for it. Both dispatches are
tried; a failed one fails the script after the other. ``--dry-run`` prints
the planned dispatches and sends none. Starting either twice
changes nothing: the queue runs one at a time and the Fix task records each
run attempt.

Standard library only. Prints one JSON object; errors name the API call and
status, never payload text, and a missing token goes to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Protocol

import pr_cli
from implementer_setup import WORKFLOW_FILE_PATTERN
from pr_github_client import FetchError, GitHubClient

SCRIPT = "implementer_follow_up.py"

SUCCESS = "success"
# The values of `needs.<job>.result` (GitHub docs, "Contexts reference").
JOB_RESULTS = (SUCCESS, "failure", "cancelled", "skipped")

HELP_EPILOG = f"""\
stdout: JSON with "dispatched" (workflow files; with --dry-run: would be), "failed"
        ({{"workflow", "reason"}} each) and "dry_run".
env: GITHUB_TOKEN (needs Actions write; not read with --dry-run).

examples:
  implementer_follow_up.py --repo owner/repo --run-id 123 --ref main \\
      --implement-result failure --queue-workflow implementer-queue.yml \\
      --fix-task-workflow fix-task.yml --dry-run
  implementer_follow_up.py --help

{
    pr_cli.exit_help(
        pr_cli.EXIT_OK, pr_cli.EXIT_ACTION_FAILED, pr_cli.EXIT_USAGE, pr_cli.EXIT_MISSING_TOKEN
    )
}
"""


class Dispatcher(Protocol):
    """The one call this script makes; ``GitHubClient`` and test fakes implement it."""

    def post(self, path: str, payload: dict[str, object] | None = None) -> object: ...


@dataclass(frozen=True)
class Dispatch:
    workflow: str
    inputs: dict[str, str]


@dataclass(frozen=True)
class Failure:
    workflow: str
    reason: str


@dataclass
class FollowUp:
    dispatched: list[str] = field(default_factory=list)
    failed: list[Failure] = field(default_factory=list)
    dry_run: bool = False


def plan(
    *,
    run_id: int,
    implement_result: str,
    queue_workflow: str | None,
    fix_task_workflow: str | None,
) -> list[Dispatch]:
    """The Fix task (unless the implement job succeeded), then the queue."""
    dispatches = []
    if fix_task_workflow is not None and implement_result != SUCCESS:
        dispatches.append(Dispatch(fix_task_workflow, {"run_id": str(run_id), "dry_run": "false"}))
    if queue_workflow is not None:
        dispatches.append(Dispatch(queue_workflow, {"dry_run": "false"}))
    return dispatches


def send(client: Dispatcher, repo: str, ref: str, dispatches: list[Dispatch]) -> FollowUp:
    """Send every dispatch on ``ref``; a failed one does not stop the next."""
    outcome = FollowUp()
    for dispatch in dispatches:
        path = f"/repos/{repo}/actions/workflows/{dispatch.workflow}/dispatches"
        try:
            client.post(path, {"ref": ref, "inputs": dispatch.inputs})
        except FetchError as error:
            outcome.failed.append(Failure(dispatch.workflow, str(error)))
            continue
        outcome.dispatched.append(dispatch.workflow)
    return outcome


def _workflow(value: str) -> str | None:
    """A plain workflow file name, or None for the empty string."""
    if value == "":
        return None
    if not WORKFLOW_FILE_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("must be a plain *.yml or *.yaml file name, or empty")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch the queue and the Fix task after a queue-dispatched implementer run.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", required=True, type=pr_cli.repo_argument, help="OWNER/REPO")
    parser.add_argument(
        "--run-id", required=True, type=pr_cli.positive_int_argument, help="this implementer run"
    )
    parser.add_argument("--ref", required=True, help="the branch to dispatch on")
    parser.add_argument(
        "--implement-result",
        required=True,
        choices=JOB_RESULTS,
        help="the implement job's result",
    )
    parser.add_argument(
        "--queue-workflow", required=True, type=_workflow, help="queue workflow file, or ''"
    )
    parser.add_argument(
        "--fix-task-workflow", required=True, type=_workflow, help="Fix-task workflow file, or ''"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the planned dispatches and send none"
    )
    args = parser.parse_args(argv)

    dispatches = plan(
        run_id=args.run_id,
        implement_result=args.implement_result,
        queue_workflow=args.queue_workflow,
        fix_task_workflow=args.fix_task_workflow,
    )
    if args.dry_run:
        outcome = FollowUp(dispatched=[dispatch.workflow for dispatch in dispatches], dry_run=True)
        print(json.dumps(asdict(outcome)))
        return pr_cli.EXIT_OK
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print(f"{SCRIPT}: GITHUB_TOKEN is not set", file=sys.stderr)
        return pr_cli.EXIT_MISSING_TOKEN
    outcome = send(GitHubClient(token), args.repo, args.ref, dispatches)
    print(json.dumps(asdict(outcome)))
    return pr_cli.EXIT_ACTION_FAILED if outcome.failed else pr_cli.EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
