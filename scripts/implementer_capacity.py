"""The implementer's capacity gate: how many other implementer runs work ahead of this one.

It reads the Actions API, whose run and job listings are the only record of
which runs are working. The caller passes a client holding the job token
(ACTIONS_READ_TOKEN), because the App token cannot be shown to have Actions
read (ADR-0014).

Standard library only.
"""

from __future__ import annotations

from datetime import datetime

from pr_github import PER_PAGE, get_json
from pr_github_client import FetchError, ReadClient

IMPLEMENTER_WORKFLOW = "implementer.yml"
IMPLEMENT_JOB = "implement"
MAX_WORKING_RUNS = 1


def _single_page(
    client: ReadClient, path: str, items_key: str, params: dict[str, object] | None = None
) -> list:
    """The list under ``items_key``; more than one page would undercount, so it fails."""
    listing = get_json(client, path, params={**(params or {}), "per_page": PER_PAGE})
    items = listing.get(items_key) if isinstance(listing, dict) else None
    total_count = listing.get("total_count") if isinstance(listing, dict) else None
    if not isinstance(items, list) or not isinstance(total_count, int):
        raise FetchError(f"GitHub API returned an unexpected payload for {path}")
    if total_count > len(items):
        raise FetchError(f"GitHub API listed more items than one page holds for {path}")
    return items


def _implement_job_start(client: ReadClient, repo: str, run_id: int) -> datetime | None:
    """When the run's latest attempt started working, or None while it is not working.

    The job's status tells a working run from one whose job the workflow's `if`
    skipped, or one still queued.
    """
    path = f"/repos/{repo}/actions/runs/{run_id}/jobs"
    for job in _single_page(client, path, "jobs"):
        try:
            if job["name"] != IMPLEMENT_JOB:
                continue
            if job["status"] != "in_progress":
                return None
            started_at = datetime.fromisoformat(job["started_at"])
        except (KeyError, TypeError, ValueError) as error:
            raise FetchError(f"GitHub API returned a malformed job for {path}") from error
        if started_at.tzinfo is None:
            raise FetchError(f"GitHub API returned a malformed job for {path}")
        return started_at
    return None


def runs_working_ahead(client: ReadClient, repo: str, run_id: int) -> int:
    """How many other working runs come before this one.

    Runs are ordered by (job start, run id), and only earlier runs count, so of
    two simultaneous starts exactly one sees the other and stops. The job start
    comes first because a re-run keeps its old run id: ordering by id alone would
    let a re-run ignore every newer run already working.
    """
    own_start = _implement_job_start(client, repo, run_id)
    if own_start is None:
        raise FetchError(f"GitHub API lists no working {IMPLEMENT_JOB} job for this run")
    runs_path = f"/repos/{repo}/actions/workflows/{IMPLEMENTER_WORKFLOW}/runs"
    runs_ahead = 0
    for run in _single_page(client, runs_path, "workflow_runs", {"status": "in_progress"}):
        other_id = run.get("id") if isinstance(run, dict) else None
        if not isinstance(other_id, int):
            raise FetchError(f"GitHub API returned a malformed run for {runs_path}")
        if other_id == run_id:
            continue
        other_start = _implement_job_start(client, repo, other_id)
        if other_start is not None and (other_start, other_id) < (own_start, run_id):
            runs_ahead += 1
    return runs_ahead
