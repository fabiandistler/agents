#!/usr/bin/env python3
"""The skill audit's model-free gate: is a scheduled run still due?

GitHub starts this repository's scheduled runs hours late and sometimes not at
all, so skill-audit.yml is scheduled on the 8th and the 22nd plus two catch-up
days each. The first of those runs that finds no successful audit in its
half-month bucket (skill_audit_select.half_month_start) runs the audit; every
later one, a late duplicate included, ends here. A manual run is always due:
the Run workflow button starts an extra audit on purpose.

Standard library only. Errors name the API call, never response text.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from dataclasses import asdict, dataclass

from pr_github_client import REPO_PATTERN, FetchError, GitHubClient, ReadClient, get_json
from skill_audit_select import half_month_start

WORKFLOW_FILE = "skill-audit.yml"
SCHEDULE_EVENT = "schedule"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_MISSING_TOKEN = 3
EXIT_FETCH_FAILED = 4

HELP_EPILOG = """\
Prints one JSON object: {"due", "reason", "since", "successful_runs"}.
Reads GITHUB_TOKEN (actions: read).

exit codes: 0 ok (also when not due); 2 usage error; 3 no GITHUB_TOKEN;
            4 a GitHub request failed.

examples:
  skill_audit_gate.py --repo fabiandistler/agents --event schedule
  skill_audit_gate.py --repo fabiandistler/agents --event schedule --date 2026-11-23
"""


@dataclass(frozen=True)
class Decision:
    due: bool
    reason: str
    since: str
    successful_runs: int


def successful_runs_since(client: ReadClient, repo: str, since: datetime.date) -> int:
    """Successful runs of the audit workflow, any event, created on or after `since` (UTC)."""
    payload = get_json(
        client,
        f"/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs",
        params={"status": "success", "created": f">={since.isoformat()}", "per_page": 1},
    )
    count = payload.get("total_count") if isinstance(payload, dict) else None
    if not isinstance(count, int):
        raise FetchError(f"GitHub API returned an unexpected payload for {WORKFLOW_FILE} runs")
    return count


def decide(client: ReadClient, repo: str, event: str, today: datetime.date) -> Decision:
    since = half_month_start(today)
    if event != SCHEDULE_EVENT:
        return Decision(True, f"{event} runs are always due", since.isoformat(), 0)
    count = successful_runs_since(client, repo, since)
    if count:
        reason = "an audit already succeeded this half-month"
        return Decision(False, reason, since.isoformat(), count)
    return Decision(True, "no successful audit this half-month", since.isoformat(), 0)


def _repo_argument(value: str) -> str:
    if not REPO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("must be OWNER/REPO")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decide whether this skill-audit.yml run should run the audit.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", required=True, type=_repo_argument)
    parser.add_argument("--event", required=True, help="github.event_name of this run")
    parser.add_argument(
        "--date",
        type=datetime.date.fromisoformat,
        default=datetime.datetime.now(datetime.timezone.utc).date(),
        help="run date as YYYY-MM-DD (default: today, UTC)",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return EXIT_OK if exit_.code == 0 else EXIT_USAGE

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("skill_audit_gate.py: GITHUB_TOKEN is not set", file=sys.stderr)
        return EXIT_MISSING_TOKEN
    try:
        decision = decide(GitHubClient(token), args.repo, args.event, args.date)
    except FetchError as error:
        print(f"skill_audit_gate.py: {error}", file=sys.stderr)
        return EXIT_FETCH_FAILED
    print(json.dumps(asdict(decision)))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
