"""The shared Actions-listing reader of ``agent_run_capacity``: paging and its stops."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import cast

import agent_run_capacity
import pytest
from pr_github_client import PER_PAGE, FetchError, GitHubClient, Response

REPO = "fabiandistler/agents"
RUNS = f"/repos/{REPO}/actions/workflows/implementer.yml/runs"
START = "2026-11-10T10:00:00Z"


@dataclass
class PagedListing:
    """Serves ``pages`` of one Actions listing under ``items_key``, each with ``total_count``."""

    pages: list[list[dict]]
    total_count: object
    items_key: str = "workflow_runs"
    requested: list[dict] = field(default_factory=list)

    def get(self, path: str, params: dict | None = None, accept: str | None = None) -> Response:
        params = params or {}
        self.requested.append(params)
        page = params["page"]
        items = self.pages[page - 1] if page <= len(self.pages) else []
        body = {"total_count": self.total_count, self.items_key: items}
        return Response(status=200, body=json.dumps(body).encode("utf-8"))


def runs(first_id: int, count: int) -> list[dict]:
    return [{"id": run_id} for run_id in range(first_id, first_id + count)]


def read(listing: PagedListing) -> list:
    client = cast(GitHubClient, listing)
    return agent_run_capacity._all_pages(client, RUNS, listing.items_key, {"status": "x"})


def test_a_total_count_beyond_the_items_of_a_short_page_returns_those_items():
    # The four failed queue runs of issue #905 saw this shape.
    listing = PagedListing(pages=[runs(1, 1)], total_count=200)
    assert read(listing) == runs(1, 1)
    assert [params["page"] for params in listing.requested] == [1]
    assert listing.requested[0]["status"] == "x", "the caller's filter is kept"
    assert listing.requested[0]["per_page"] == PER_PAGE


def test_a_listing_longer_than_one_page_is_read_to_its_end():
    listing = PagedListing(pages=[runs(1, PER_PAGE), runs(1001, 5)], total_count=PER_PAGE + 5)
    assert read(listing) == runs(1, PER_PAGE) + runs(1001, 5)
    assert [params["page"] for params in listing.requested] == [1, 2]


@pytest.mark.parametrize("second_page", [runs(1001, 3), []], ids=["short", "empty"])
def test_paging_stops_on_a_short_or_empty_page_before_total_count(second_page):
    listing = PagedListing(pages=[runs(1, PER_PAGE), second_page], total_count=10 * PER_PAGE)
    assert read(listing) == runs(1, PER_PAGE) + second_page
    assert [params["page"] for params in listing.requested] == [1, 2]


def test_paging_stops_once_total_count_items_are_held():
    listing = PagedListing(pages=[runs(1, PER_PAGE), runs(1001, 1)], total_count=PER_PAGE)
    assert read(listing) == runs(1, PER_PAGE)
    assert [params["page"] for params in listing.requested] == [1]


@pytest.mark.parametrize(
    "total_count", [None, "200", 1.5, True], ids=["missing", "string", "float", "bool"]
)
def test_a_total_count_that_is_not_an_integer_is_an_api_error(total_count):
    with pytest.raises(FetchError, match="unexpected payload"):
        read(PagedListing(pages=[runs(1, 1)], total_count=total_count))


def test_a_missing_items_key_on_a_later_page_is_an_api_error():
    class SecondPageWithoutItems(PagedListing):
        def get(self, path: str, params: dict | None = None, accept: str | None = None):
            if (params or {}).get("page") == 2:
                return Response(status=200, body=b'{"total_count": 300}')
            return super().get(path, params, accept)

    listing = SecondPageWithoutItems(pages=[runs(1, PER_PAGE)], total_count=3 * PER_PAGE)
    with pytest.raises(FetchError, match="unexpected payload"):
        read(listing)


def test_the_jobs_listing_of_work_start_tolerates_a_total_count_beyond_its_items():
    job = {"name": "implement", "status": "in_progress", "started_at": START}
    listing = PagedListing(pages=[[job]], total_count=50, items_key="jobs")
    start = agent_run_capacity._work_start(cast(GitHubClient, listing), REPO, 5000, ("implement",))
    assert start is not None and start.isoformat() == "2026-11-10T10:00:00+00:00"
