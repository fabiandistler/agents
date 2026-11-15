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
tried; a failed one fails the script after the other. Starting either twice
changes nothing: the queue runs one at a time and the Fix task records each
run attempt.

Standard library only. Prints one JSON object; errors name the API call and
status, never payload text.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Protocol

from implementer_setup import WORKFLOW_FILE_PATTERN
from pr_github_client import REPO_PATTERN, FetchError, GitHubClient

EXIT_OK = 0
EXIT_FAILED = 1

SUCCESS = "success"
# The values of `needs.<job>.result` (GitHub docs, "Contexts reference").
JOB_RESULTS = (SUCCESS, "failure", "cancelled", "skipped")

HELP_EPILOG = """\
stdout: JSON with "dispatched" (workflow files) and "failed" ({"workflow", "reason"} each).
exit: 0 every named dispatch was sent; 1 one failed, or no GH_TOKEN; 2 usage.
env: GH_TOKEN (needs Actions write).

examples:
  implementer_follow_up.py --repo owner/repo --run-id 123 --ref main \\
      --implement-result failure --queue-workflow implementer-queue.yml \\
      --fix-task-workflow fix-task.yml
  implementer_follow_up.py --help
"""


class Dispatcher(Protocol):
    """The one call this script makes; ``GitHubClient`` and test fakes implement it."""

    def post(self, path: str, payload: dict[str, object] | None = None) -> object: ...


@dataclass(frozen=True)
class Failure:
    workflow: str
    reason: str


@dataclass
class FollowUp:
    dispatched: list[str] = field(default_factory=list)
    failed: list[Failure] = field(default_factory=list)


def follow_up(
    client: Dispatcher,
    repo: str,
    *,
    run_id: int,
    ref: str,
    implement_result: str,
    queue_workflow: str | None,
    fix_task_workflow: str | None,
) -> FollowUp:
    """Dispatch the Fix task (unless the implement job succeeded), then the queue."""
    dispatches: list[tuple[str, dict[str, str]]] = []
    if fix_task_workflow is not None and implement_result != SUCCESS:
        dispatches.append((fix_task_workflow, {"run_id": str(run_id), "dry_run": "false"}))
    if queue_workflow is not None:
        dispatches.append((queue_workflow, {"dry_run": "false"}))
    outcome = FollowUp()
    for workflow, inputs in dispatches:
        path = f"/repos/{repo}/actions/workflows/{workflow}/dispatches"
        try:
            client.post(path, {"ref": ref, "inputs": inputs})
        except FetchError as error:
            outcome.failed.append(Failure(workflow, str(error)))
            continue
        outcome.dispatched.append(workflow)
    return outcome


def _repo(value: str) -> str:
    if not REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("must be OWNER/REPO")
    return value


def _run_id(value: str) -> int:
    if not value.isdigit() or int(value) <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return int(value)


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
    parser.add_argument("--repo", required=True, type=_repo, help="OWNER/REPO")
    parser.add_argument("--run-id", required=True, type=_run_id, help="this implementer run")
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
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN")
    if not token:
        print(
            json.dumps(
                {"dispatched": [], "failed": [{"workflow": "", "reason": "GH_TOKEN is not set"}]}
            )
        )
        return EXIT_FAILED
    outcome = follow_up(
        GitHubClient(token),
        args.repo,
        run_id=args.run_id,
        ref=args.ref,
        implement_result=args.implement_result,
        queue_workflow=args.queue_workflow,
        fix_task_workflow=args.fix_task_workflow,
    )
    print(json.dumps(asdict(outcome)))
    return EXIT_FAILED if outcome.failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
