"""The Retro gate's counter: which merged agent pull requests are pending (ADR-0017).

- Eligible: a merged pull request from an `agent/issue-<n>` branch of this
  repository, merged after the floor, the oldest commit on the default branch
  that touches `.github/workflows/retro.yml`. Earlier merges never count, and
  an unreadable floor fails the gate instead of counting from the start.
- Pending: the eligible ones merged after the newest one labelled `retro:done`
  (after the floor while there is none).

The counter lives on GitHub, in the `retro:done` label; there is no state file.
Standard library only. Errors name the API call, never issue or comment text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import factory_handoff
from factory_handoff import workflow_path
from pr_github_client import FetchError, ReadClient, get_json, paginate

RETRO_WORKFLOW = workflow_path(factory_handoff.RETRO_WORKFLOW)
RETRO_DONE = "retro:done"


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


def json_object(value: object) -> dict:
    """A JSON object field, or an empty one when GitHub sent something else."""
    return value if isinstance(value, dict) else {}


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
    head = json_object(pull.get("head"))
    ref = head.get("ref")
    issue = factory_handoff.agent_branch_issue(ref)
    full_name = json_object(head.get("repo")).get("full_name")
    if issue is None or not isinstance(full_name, str) or full_name.lower() != repo.lower():
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
        issue,
        _timestamp(pull["merged_at"], "merge time"),
        names,
    )


def pending_pulls(pulls: list[MergedPull], floor: datetime) -> list[MergedPull]:
    """The eligible pull requests merged since the newest retro, or the floor."""
    eligible = [pull for pull in pulls if pull.merged_at > floor]
    done = [pull.merged_at for pull in eligible if pull.retro_done]
    since = max(done, default=floor)
    return [pull for pull in eligible if pull.merged_at > since]


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


def merged_pulls(client: ReadClient, repo: str) -> list[MergedPull]:
    pulls = paginate(client, f"/repos/{repo}/pulls", params={"state": "closed"})
    return [merged for pull in pulls if (merged := merged_agent_pull(pull, repo)) is not None]
