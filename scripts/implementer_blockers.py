"""Which issues keep a ticket from starting, for the implementer's claim and queue.

Three sources count: "Blocked by" lines in the issue body and in the latest
trusted brief (parsed by ticket_blockers.py), and the issue's native "blocked
by" dependencies. A blocker counts as done only when it is an issue of this
repository closed as completed; anything that cannot be shown to be done
blocks.

Standard library only. Errors name the API call, never issue text.
"""

from __future__ import annotations

from dataclasses import dataclass

from implementer_contract import Ticket
from pr_github_client import HTTP_NOT_FOUND, FetchError, GitHubClient, get_json, paginate
from ticket_blockers import declared_blockers

HTTP_GONE = 410


def _closed_as_completed(issue: object, path: str) -> bool:
    """Only a completed issue counts: not planned still blocks, and a PR has no such state."""
    if not isinstance(issue, dict) or not isinstance(issue.get("state"), str):
        raise FetchError(f"GitHub API returned a malformed issue for {path}")
    return (
        issue["state"] == "closed"
        and issue.get("state_reason") == "completed"
        and "pull_request" not in issue
    )


def _belongs_to_repo(issue: dict, repo: str, path: str) -> bool:
    repository_url = issue.get("repository_url")
    if not isinstance(repository_url, str):
        raise FetchError(f"GitHub API returned a malformed issue for {path}")
    return repository_url.lower().endswith(f"/repos/{repo.lower()}")


def _declared_blocker_blocks(client: GitHubClient, repo: str, number: int) -> bool:
    """Fail closed: a deleted, missing or transferred blocker cannot be shown to be done."""
    path = f"/repos/{repo}/issues/{number}"
    try:
        blocker = get_json(client, path)
    except FetchError as error:
        if error.status in (HTTP_NOT_FOUND, HTTP_GONE):
            return True
        raise
    return not (_closed_as_completed(blocker, path) and _belongs_to_repo(blocker, repo, path))


@dataclass(frozen=True)
class Blockers:
    """What keeps a ticket from starting.

    ``numbers`` are this repository's blocking issues, ``unresolved`` the
    entries and visible edges that name none, and ``hidden`` the open native
    blockers the token cannot see.
    """

    numbers: tuple[int, ...]
    unresolved: int
    hidden: int

    @property
    def block(self) -> bool:
        return bool(self.numbers or self.unresolved or self.hidden)


def find_blockers(client: GitHubClient, repo: str, issue: int, ticket: Ticket) -> Blockers:
    """The ticket's blockers, from its body, its latest trusted brief and its native edges.

    The ticket skills omit the "Blocked by" section when they set native
    edges, and a brief written later cannot erase a blocker the body declares.
    The body counts whoever wrote it, because a blocker can only stop a run. The
    edge list, unlike the issue's dependency summary, also returns closed
    blockers, so one closed as not planned is seen. But the edge list leaves out
    an edge into a repository the token cannot read, while the summary still
    counts it, so open blockers the summary counts beyond the visible open
    edges are hidden ones. They block until GitHub counts them closed, which
    lets one closed as not planned through.
    """
    declared_numbers: set[int] = set()
    unresolved = 0
    for text in (ticket.body, ticket.brief or ""):
        declared = declared_blockers(text, repo)
        declared_numbers |= declared.numbers
        unresolved += declared.unresolved
    blocking = {
        number for number in declared_numbers if _declared_blocker_blocks(client, repo, number)
    }
    issue_path = f"/repos/{repo}/issues/{issue}"
    if ticket.open_native_blockers is None:
        raise FetchError(f"GitHub API returned no dependency summary for {issue_path}")
    edges_path = f"{issue_path}/dependencies/blocked_by"
    open_edges = 0
    for edge in paginate(client, edges_path):
        if _closed_as_completed(edge, edges_path):
            continue
        open_edges += edge["state"] == "open"
        if _belongs_to_repo(edge, repo, edges_path):
            number = edge.get("number")
            if not isinstance(number, int):
                raise FetchError(f"GitHub API returned a malformed issue for {edges_path}")
            blocking.add(number)
        else:
            unresolved += 1
    # An edge that closes between the two reads can leave more open edges than the count.
    hidden = max(ticket.open_native_blockers - open_edges, 0)
    return Blockers(tuple(sorted(blocking)), unresolved, hidden)
