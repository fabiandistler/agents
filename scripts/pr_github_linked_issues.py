"""The issues a pull request says it closes, for ``pr_github.py --linked-issues``.

Same repository only, at most ``LINKED_ISSUE_LIMIT``. Text by an author without
write access never enters the context (ADR-0013); a failed fetch makes one
issue ``unavailable``, never the run. The field's shape is in
docs/agents/pr-review-linked-issues.md.
"""

from __future__ import annotations

import sys

from agent_brief import is_trusted
from check_pr_issue_links import closing_references
from pr_github_client import FetchError, ReadClient, get_json

LINKED_ISSUE_LIMIT = 3
LINKED_ISSUE_STATUSES = ("ok", "unavailable", "outside_author")


def _linked_issue_numbers(body: str, repo: str) -> list[int]:
    """The same-repository issues ``body`` declares it closes: ascending, at most 3."""
    prefix = f"{repo.lower()}#"
    numbers = {
        int(reference[len(prefix) :])
        for reference in closing_references(body, repo)
        if reference.startswith(prefix)
    }
    return sorted(numbers)[:LINKED_ISSUE_LIMIT]


def _linked_issue(client: ReadClient, repo: str, number: int) -> dict | None:
    """One linked issue for the context; None when the number names a pull request.

    The token reads this repository only, so other repositories are never
    asked. Text by an author without write access stays out of the context
    (ADR-0013). A failed fetch leaves the issue unavailable, never the run.
    """
    unavailable = {"number": number, "status": "unavailable", "title": "", "body": ""}
    try:
        issue = get_json(client, f"/repos/{repo}/issues/{number}")
    except FetchError as error:
        status = error.status if error.status is not None else "none"
        # Number and status only: the issue text never reaches a log.
        print(f"pr_github.py: linked issue #{number} unavailable (HTTP {status})", file=sys.stderr)
        return unavailable
    if not isinstance(issue, dict):
        print(f"pr_github.py: linked issue #{number} unavailable (HTTP 200)", file=sys.stderr)
        return unavailable
    if "pull_request" in issue:
        return None
    if not is_trusted(issue):
        return {"number": number, "status": "outside_author", "title": "", "body": ""}
    title = issue.get("title")
    body = issue.get("body")
    return {
        "number": number,
        "status": "ok",
        "title": title if isinstance(title, str) else "",
        "body": body if isinstance(body, str) else "",
    }


def fetch_linked_issues(client: ReadClient, repo: str, body: str) -> list[dict]:
    issues = (_linked_issue(client, repo, number) for number in _linked_issue_numbers(body, repo))
    return [issue for issue in issues if issue is not None]
