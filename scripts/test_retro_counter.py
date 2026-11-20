"""Tests for the Retro gate's counter (scripts/retro_counter.py, ADR-0017)."""

from __future__ import annotations

from datetime import timedelta

import pytest
import retro_counter
import retro_gate
from pr_github_client import FetchError
from retro_gate_fake import (
    FLOOR,
    REPO,
    RoutedClient,
    after,
    api_pull,
    gate_routes,
    iso,
    ten_after_floor,
)

# --- Counting ----------------------------------------------------------------


def test_unmerged_foreign_and_retro_pulls_are_not_counted():
    pulls = ten_after_floor()[:9] + [
        api_pull(20, merged_at=None),
        api_pull(21, merged_at=after(30), ref="feature/x"),
        api_pull(22, merged_at=after(31), ref="agent/retro-5"),
        api_pull(23, merged_at=after(32), head_repo="someone/fork"),
        api_pull(24, merged_at=after(33), ref="agent/issue-12-extra"),
    ]
    selection = retro_gate.run_gate(RoutedClient(gate_routes(pulls)), REPO, 10)
    assert selection.selected is None
    assert selection.pending == 9


def test_counting_restarts_at_the_newest_retro():
    pulls = ten_after_floor(pr4=(retro_counter.RETRO_DONE,)) + [
        api_pull(n, merged_at=after(n)) for n in range(11, 14)
    ]
    selection = retro_gate.run_gate(RoutedClient(gate_routes(pulls)), REPO, 10)
    assert selection.selected is None
    assert selection.pending == 9  # 5..13


# --- Floor -------------------------------------------------------------------


def test_first_run_ignores_pulls_merged_before_the_floor():
    before = [api_pull(n, merged_at=FLOOR - timedelta(hours=n)) for n in range(1, 21)]
    client = RoutedClient(gate_routes(before))
    selection = retro_gate.run_gate(client, REPO, 10)
    assert selection.selected is None
    assert selection.pending == 0
    assert client.posts == []


def test_pulls_before_the_floor_are_never_selected():
    before = [
        api_pull(n, merged_at=FLOOR - timedelta(hours=n), labels=("review:block",))
        for n in range(100, 120)
    ]
    selection = retro_gate.run_gate(RoutedClient(gate_routes(before + ten_after_floor())), REPO, 10)
    assert selection.selected == 10
    assert selection.pending == 10


def test_floor_is_the_oldest_commit_of_the_workflow_file():
    routes = gate_routes([])
    routes[f"/repos/{REPO}/commits"] = [
        {"commit": {"committer": {"date": iso(after(50))}}},
        {"commit": {"committer": {"date": iso(FLOOR)}}},
    ]
    assert retro_counter.read_floor(RoutedClient(routes), REPO) == FLOOR


def test_a_missing_workflow_file_fails_the_gate():
    client = RoutedClient(gate_routes(ten_after_floor()), floor=None)
    with pytest.raises(retro_counter.FloorError):
        retro_gate.run_gate(client, REPO, 10)
    assert client.posts == []


def test_an_unreadable_floor_fails_the_gate():
    routes = gate_routes(ten_after_floor())
    routes[f"/repos/{REPO}/commits"] = FetchError("GitHub API returned 500", status=500)
    client = RoutedClient(routes)
    with pytest.raises(retro_counter.FloorError):
        retro_gate.run_gate(client, REPO, 10)
    assert client.posts == []


def test_cli_exits_5_without_a_floor(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    client = RoutedClient(gate_routes([]), floor=None)
    monkeypatch.setattr(retro_gate, "GitHubClient", lambda token: client)
    assert retro_gate.main(["select", "--repo", REPO]) == retro_gate.EXIT_NO_FLOOR
    assert capsys.readouterr().out == ""


def test_second_run_without_new_merges_selects_nothing():
    pulls = ten_after_floor()
    first = RoutedClient(gate_routes(pulls))
    selected = retro_gate.run_gate(first, REPO, 10).selected
    labelled = [
        {**pull, "labels": [{"name": retro_counter.RETRO_DONE}]}
        if pull["number"] == selected
        else pull
        for pull in pulls
    ]
    second = RoutedClient(gate_routes(labelled))
    assert retro_gate.run_gate(second, REPO, 10).selected is None
    assert second.posts == []
