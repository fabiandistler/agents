"""How many runs of an agent workflow are working ahead of this one.

The agent-run workflows (implementer.yml, rework.yml) allow a fixed number of
runs to work at a time. Each asks the Actions API, from inside its own run,
how many other runs of the same workflow are working and come earlier.

A workflow names its *working jobs*. The first one is the job that asks; its
start orders the runs. A run is working while its first job is in progress, or
after it, while a later working job has not completed. Every status but
`completed` counts (queued, waiting, pending): the run has decided to work, so a
job held back by its concurrency group keeps the capacity until it ends. A job
the workflow's ``if`` skipped is completed.

Standard library only. Errors name the API call, never run or job payloads.
"""

from __future__ import annotations

from datetime import datetime

from pr_github import PER_PAGE, get_json
from pr_github_client import FetchError, ReadClient


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


def _job_statuses(client: ReadClient, path: str, jobs: tuple[str, ...]) -> dict[str, dict]:
    """The listed jobs of one run attempt that are working jobs, by name."""
    found: dict[str, dict] = {}
    for job in _single_page(client, path, "jobs"):
        try:
            name = job["name"]
            status = job["status"]
        except (KeyError, TypeError) as error:
            raise FetchError(f"GitHub API returned a malformed job for {path}") from error
        if name in jobs and isinstance(status, str):
            found[name] = job
    return found


def _work_start(
    client: ReadClient, repo: str, run_id: int, jobs: tuple[str, ...]
) -> datetime | None:
    """When the run's latest attempt started working, or None while it is not working.

    The job's status tells a working run from one whose job the workflow's `if`
    skipped, or one still queued.
    """
    path = f"/repos/{repo}/actions/runs/{run_id}/jobs"
    listed = _job_statuses(client, path, jobs)
    first = listed.get(jobs[0])
    if first is None:
        return None
    later_working = any(
        listed[name]["status"] != "completed" for name in jobs[1:] if name in listed
    )
    if first["status"] != "in_progress" and not (first["status"] == "completed" and later_working):
        return None
    try:
        started_at = datetime.fromisoformat(first["started_at"])
    except (KeyError, TypeError, ValueError) as error:
        raise FetchError(f"GitHub API returned a malformed job for {path}") from error
    if started_at.tzinfo is None:
        raise FetchError(f"GitHub API returned a malformed job for {path}")
    return started_at


def runs_working_ahead(
    client: ReadClient, repo: str, run_id: int, workflow: str, jobs: tuple[str, ...]
) -> int:
    """How many other working runs of ``workflow`` come before run ``run_id``.

    Runs are ordered by (start of the first working job, run id), and only
    earlier runs count, so of two simultaneous starts exactly one sees the
    other and stops. The job start comes first because a re-run keeps its old
    run id: ordering by id alone would let a re-run ignore every newer run
    already working.
    """
    own_start = _work_start(client, repo, run_id, jobs)
    if own_start is None:
        raise FetchError(f"GitHub API lists no working {jobs[0]} job for this run")
    runs_path = f"/repos/{repo}/actions/workflows/{workflow}/runs"
    runs_ahead = 0
    for run in _single_page(client, runs_path, "workflow_runs", {"status": "in_progress"}):
        other_id = run.get("id") if isinstance(run, dict) else None
        if not isinstance(other_id, int):
            raise FetchError(f"GitHub API returned a malformed run for {runs_path}")
        if other_id == run_id:
            continue
        other_start = _work_start(client, repo, other_id, jobs)
        if other_start is not None and (other_start, other_id) < (own_start, run_id):
            runs_ahead += 1
    return runs_ahead
