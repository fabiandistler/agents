"""Test doubles for the Retro gate's tests: GitHub pull requests and a routed client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from factory_handoff import REWORK_ROUND, format_marker
from factory_handoff import WORKFLOW_BOT_LOGIN as COMMENT_AUTHOR
from pr_github_client import Response
from pr_github_fake import json_response
from retro_counter import RETRO_DONE

REPO = "fabiandistler/agents"
FLOOR = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Branch:
    """A pull request's head: a branch of a repository, this one unless a fork."""

    ref: str
    repo: str = REPO

    def payload(self) -> dict:
        return {"ref": self.ref, "repo": {"full_name": self.repo}}


def api_pull(
    number: int,
    *,
    merged_at: datetime | None,
    head: Branch | None = None,
    labels: tuple[str, ...] = (),
    body: str = "Closes #1",
) -> dict:
    """A pull request as GitHub lists it; the head defaults to `agent/issue-<number + 1000>`."""
    return {
        "number": number,
        "merged_at": iso(merged_at) if merged_at else None,
        "head": (head or Branch(f"agent/issue-{number + 1000}")).payload(),
        "labels": [{"name": label} for label in labels],
        "body": body,
        "user": {"login": "claude[bot]"},
    }


def after(hours: int) -> datetime:
    return FLOOR + timedelta(hours=hours)


def comment(body: str, login: str, association: str = "NONE") -> dict:
    return {"body": body, "user": {"login": login}, "author_association": association}


def round_marker(round_: int) -> str:
    return format_marker(REWORK_ROUND, round=round_, head=f"{round_:040x}")


def rework(round_: int, login: str = COMMENT_AUTHOR) -> dict:
    return comment(f"{round_marker(round_)}\nRework round {round_}.", login)


class RoutedClient:
    """GET by exact path; POSTs are recorded. A list is one page unless routed per page."""

    def __init__(self, routes: dict[str, object], floor: datetime | None = FLOOR) -> None:
        self.routes = {f"/repos/{REPO}": {"default_branch": "main"}, **routes}
        commits = [] if floor is None else [{"commit": {"committer": {"date": iso(floor)}}}]
        self.routes.setdefault(f"/repos/{REPO}/commits", commits)
        self.routes.setdefault(
            f"/repos/{REPO}/actions/workflows/implementer.yml/runs", {"workflow_runs": []}
        )
        self.posts: list[tuple[str, dict[str, object] | None]] = []
        self.events: list[str] = []

    def get(
        self, path: str, params: dict[str, object] | None = None, accept: str | None = None
    ) -> Response:
        params = params or {}
        key = path
        if path == f"/repos/{REPO}/pulls":
            key = f"{path}?state={params['state']}"
        paged = f"{key}?page={params.get('page')}" in self.routes
        if paged:
            key = f"{key}?page={params['page']}"
        if key not in self.routes:
            raise AssertionError(f"unexpected GET {key}")
        self.events.append(f"GET {key}")
        payload = self.routes[key]
        if isinstance(payload, Exception):
            raise payload
        if not paged and isinstance(payload, list) and params.get("page") not in (None, 1):
            return json_response([])
        return json_response(payload)

    def post(self, path: str, payload: dict[str, object] | None = None) -> Response:
        self.posts.append((path, payload))
        self.events.append(f"POST {path}")
        if path == f"/repos/{REPO}/labels" and self.routes.get("label_exists"):
            return json_response({"message": "already_exists"}, status=422)
        return json_response({}, status=201)

    def patch(self, path: str, payload: dict[str, object] | None = None) -> Response:
        raise AssertionError(f"unexpected PATCH {path}")

    def delete(self, path: str, payload: dict[str, object] | None = None) -> Response:
        raise AssertionError(f"unexpected DELETE {path}")


def label_event(name: str, at: datetime, event: str = "labeled") -> dict:
    return {"event": event, "label": {"name": name}, "created_at": iso(at)}


def gate_routes(
    pulls: list[dict],
    open_pulls: list[dict] | None = None,
    comments=None,
    labelled_at: dict[int, datetime] | None = None,
) -> dict:
    """``labelled_at`` maps a pull request to when it was given `retro:done`."""
    routes: dict[str, object] = {
        f"/repos/{REPO}/pulls?state=closed": pulls,
        f"/repos/{REPO}/pulls?state=open": open_pulls or [],
    }
    for pull in pulls:
        number = pull["number"]
        routes[f"/repos/{REPO}/issues/{number}/comments"] = (comments or {}).get(number, [])
        at = (labelled_at or {}).get(number)
        routes[f"/repos/{REPO}/issues/{number}/events"] = (
            [] if at is None else [label_event(RETRO_DONE, at)]
        )
    return routes


def ten_after_floor(**labels_by_number) -> list[dict]:
    return [
        api_pull(n, merged_at=after(n), labels=labels_by_number.get(f"pr{n}", ()))
        for n in range(1, 11)
    ]
