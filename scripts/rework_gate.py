#!/usr/bin/env python3
"""The model-free gate of the Rework task (rework.yml, ADR-0015).

`locate` names the pr-review run whose artifacts the gate reads: the
triggering run of a `workflow_run` event, or for a manual run the latest
successful review run of the pull request's live head that uploaded a review.
`decide` reads that run, its `pr-review` and `pr-context` artifacts, the live
pull request, its linked issue and its comments, and applies
``rework_policy.decide``. On `proceed` it
also checks that no other rework run is working, then writes the findings file
the model job receives and posts the round marker. On `handoff` it swaps the
issue to `ready-for-human`, then comments on the pull request. A stop writes
nothing, and neither does a run without `--write`.

Runs with the workflow's GITHUB_TOKEN. Standard library only. Prints one JSON
object; errors name the API call and status, never pull request or issue text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import rework_policy
from agent_run_capacity import runs_working_ahead
from implementer_claim import swap_to_human
from pr_github import comment_entry
from pr_github_client import (
    REPO_PATTERN,
    FetchError,
    GitHubClient,
    MissingTokenError,
    ReadClient,
    get_json,
    paginate,
)

REWORK_WORKFLOW = "rework.yml"
GATE_JOB = "gate"
REWORK_JOB = "rework"
MAX_WORKING_REWORK_RUNS = 1
REVIEW_WORKFLOW = "pr-review.yml"
REVIEW_ARTIFACT = "pr-review"

NO_REVIEW = rework_policy.Decision(rework_policy.STOP, "the review job did not run")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

HELP_EPILOG = """\
stdout: locate {"run_id"}; decide {"action", "reason", "pull_request", "issue", "round"}.
decide actions: proceed (with --write: findings file written, marker posted),
  handoff (with --write: ready-for-human, then the comment), stop (no write).
Without --write decide plans only and writes nothing, not even the findings file.
A missing --review file is a stop: pr-review uploads none when it skips the review.
--outputs FILE appends the same fields as key=value lines (numbers and words only).
exit codes: 0 decided; 1 GitHub API or artifact error; 2 usage error.
env: GITHUB_TOKEN; GITHUB_RUN_ID (decide: the capacity check).

examples:
  rework_gate.py locate --repo owner/repo --pr 42
  rework_gate.py decide --repo owner/repo --run-id 123 --review review.json \\
      --context context.json --findings "$RUNNER_TEMP/rework/findings.json" --write
"""


def _uploaded_review(client: ReadClient, repo: str, run_id: int) -> bool:
    """Whether the run still holds a `pr-review` artifact; a label-only run uploads none."""
    path = f"/repos/{repo}/actions/runs/{run_id}/artifacts"
    listing = get_json(client, path, params={"name": REVIEW_ARTIFACT})
    artifacts = listing.get("artifacts") if isinstance(listing, dict) else None
    if not isinstance(artifacts, list):
        raise FetchError(f"GitHub API returned an unexpected payload for {path}")
    return any(
        isinstance(artifact, dict)
        and artifact.get("name") == REVIEW_ARTIFACT
        and artifact.get("expired") is False
        for artifact in artifacts
    )


def locate_run(client: ReadClient, repo: str, pr: int) -> int:
    """The latest successful review run of the pull request's live head that uploaded a review.

    A newer failed or cancelled run, or a run started by a label (which skips
    the review), would only make the gate stop, so neither shadows the review.
    """
    pull = get_json(client, f"/repos/{repo}/pulls/{pr}")
    head = pull.get("head") if isinstance(pull, dict) else None
    head_sha = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(head_sha, str):
        raise FetchError(f"GitHub API returned a malformed pull request for /repos/{repo}/pulls")
    path = f"/repos/{repo}/actions/workflows/{REVIEW_WORKFLOW}/runs"
    listing = get_json(
        client,
        path,
        params={"head_sha": head_sha, "event": rework_policy.REVIEW_EVENT, "status": "success"},
    )
    runs = listing.get("workflow_runs") if isinstance(listing, dict) else None
    if not isinstance(runs, list):
        raise FetchError(f"GitHub API returned an unexpected payload for {path}")
    ids = [
        run.get("id")
        for run in runs
        if isinstance(run, dict) and run.get("conclusion") == "success"
    ]
    for run_id in sorted((run_id for run_id in ids if isinstance(run_id, int)), reverse=True):
        if _uploaded_review(client, repo, run_id):
            return run_id
    raise FetchError(f"GitHub API lists no successful review run with a review in {path}")


def _read_artifact(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise FetchError(f"artifact {path.name} is missing or not JSON") from error
    if not isinstance(payload, dict):
        raise FetchError(f"artifact {path.name} is not a JSON object")
    return payload


def _gate_inputs(client: ReadClient, repo: str, run_id: int, review: dict) -> dict:
    """The live facts ``rework_policy.decide`` reads besides the artifacts."""
    run = get_json(client, f"/repos/{repo}/actions/runs/{run_id}")
    number = review.get("number")
    if not isinstance(run, dict) or not isinstance(number, int) or isinstance(number, bool):
        raise FetchError(f"the run or the review of /repos/{repo}/actions/runs is malformed")
    pull = get_json(client, f"/repos/{repo}/pulls/{number}")
    if not isinstance(pull, dict):
        raise FetchError(f"GitHub API returned a malformed pull request for /repos/{repo}/pulls")
    issue_number = rework_policy.linked_issue(pull, repo)
    issue = None
    if issue_number is not None:
        issue = get_json(client, f"/repos/{repo}/issues/{issue_number}")
    comments = [
        comment_entry(entry)
        for entry in paginate(client, f"/repos/{repo}/issues/{number}/comments")
    ]
    return {"run": run, "pull": pull, "issue": issue, "comments": comments}


def decide_rework(
    client: GitHubClient,
    repo: str,
    run_id: int,
    review: dict,
    context: dict,
    *,
    own_run_id: int,
    findings_path: Path,
    write: bool,
) -> rework_policy.Decision:
    """Decide the gate and, with ``write``, make its writes."""
    facts = _gate_inputs(client, repo, run_id, review)
    decision = rework_policy.decide(repo=repo, review=review, context=context, **facts)
    pr = review["number"] if decision.action != rework_policy.STOP else None
    if decision.action == rework_policy.HANDOFF and write:
        # Swap first: the comment's marker turns a rerun into a stop, so it may
        # land only once the issue waits for a person.
        swap_to_human(client, f"/repos/{repo}/issues/{decision.issue}")
        client.post(
            f"/repos/{repo}/issues/{pr}/comments",
            {"body": rework_policy.handoff_comment(decision.head_sha or "")},
        )
    if decision.action != rework_policy.PROCEED:
        return decision
    working = runs_working_ahead(client, repo, own_run_id, REWORK_WORKFLOW, (GATE_JOB, REWORK_JOB))
    if working >= MAX_WORKING_REWORK_RUNS:
        return rework_policy.Decision(rework_policy.STOP, "another rework run is working")
    if not write:
        return decision
    round_number = decision.round or 0
    head_sha = decision.head_sha or ""
    findings_path.parent.mkdir(parents=True, exist_ok=True)
    findings_path.write_text(
        json.dumps(
            {
                "repository": repo,
                "pull_request": pr,
                "issue": decision.issue,
                "branch": f"agent/issue-{decision.issue}",
                "round": round_number,
                "max_rounds": rework_policy.MAX_REWORK_ROUNDS,
                "head_sha": head_sha,
                "verdict": review["verdict"],
                "findings": review["findings"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # The marker is the counter: it lands before the model job starts.
    client.post(
        f"/repos/{repo}/issues/{pr}/comments",
        {"body": rework_policy.round_comment(round_number, head_sha)},
    )
    return decision


def _report(decision: rework_policy.Decision, pr: int | None) -> dict:
    return {
        "action": decision.action,
        "reason": decision.reason,
        "pull_request": pr if decision.action != rework_policy.STOP else None,
        "issue": decision.issue,
        "round": decision.round,
    }


def _append_outputs(path: Path | None, fields: dict) -> None:
    if path is None:
        return
    lines = [f"{key}={'' if value is None else value}" for key, value in fields.items()]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _positive(value: str) -> int:
    if not value.isdecimal() or int(value) < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return int(value)


def _repo(value: str) -> str:
    if not REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("must be OWNER/REPO")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gate one rework round of an agent/issue-<n> pull request.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    locate = commands.add_parser("locate", help="name the pr-review run to read")
    which = locate.add_mutually_exclusive_group(required=True)
    which.add_argument("--run-id", type=_positive, help="the triggering run (workflow_run)")
    which.add_argument("--pr", type=_positive, help="the pull request (manual run)")
    decide = commands.add_parser("decide", help="decide the gate and make its writes")
    decide.add_argument("--run-id", required=True, type=_positive, help="the pr-review run")
    decide.add_argument("--review", required=True, type=Path, help="review.json artifact")
    decide.add_argument("--context", required=True, type=Path, help="context.json artifact")
    decide.add_argument("--findings", required=True, type=Path, help="findings file to write")
    decide.add_argument("--write", action="store_true", help="make the writes (default: plan)")
    for command in (locate, decide):
        command.add_argument("--repo", required=True, type=_repo, help="OWNER/REPO")
        command.add_argument("--outputs", type=Path, help="append key=value lines to FILE")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise MissingTokenError("GITHUB_TOKEN is not set")
        client = GitHubClient(token)
        if args.command == "locate":
            run_id = args.run_id or locate_run(client, args.repo, args.pr)
            fields: dict = {"run_id": run_id}
        else:
            own_run_id = os.environ.get("GITHUB_RUN_ID", "")
            if not own_run_id.isdecimal():
                raise FetchError("GITHUB_RUN_ID is not a positive integer")
            if not args.review.exists():
                # pr-review skips its review job for a draft or a fork and then
                # uploads no review artifact: there is nothing to rework.
                print(json.dumps(_report(NO_REVIEW, None)))
                _append_outputs(args.outputs, _report(NO_REVIEW, None))
                return EXIT_OK
            review = _read_artifact(args.review)
            decision = decide_rework(
                client,
                args.repo,
                args.run_id,
                review,
                _read_artifact(args.context),
                own_run_id=int(own_run_id),
                findings_path=args.findings,
                write=args.write,
            )
            fields = _report(decision, review.get("number"))
    except FetchError as error:
        print(json.dumps({"action": "failed", "reason": str(error)}))
        return EXIT_FAILED
    _append_outputs(args.outputs, fields)
    print(json.dumps(fields))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
