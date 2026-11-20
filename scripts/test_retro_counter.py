"""Tests for the Retro gate's counter (scripts/retro_counter.py, ADR-0017, #922)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import retro_counter
import retro_gate
from pr_github_client import PER_PAGE, FetchError
from retro_gate_fake import (
    FLOOR,
    REPO,
    Branch,
    RoutedClient,
    after,
    api_pull,
    gate_routes,
    iso,
    label_event,
    ten_after_floor,
)

# --- Counting ----------------------------------------------------------------


def test_unmerged_foreign_and_retro_pulls_are_not_counted():
    pulls = ten_after_floor()[:9] + [
        api_pull(20, merged_at=None),
        api_pull(21, merged_at=after(30), head=Branch("feature/x")),
        api_pull(22, merged_at=after(31), head=Branch("agent/retro-5")),
        api_pull(23, merged_at=after(32), head=Branch("agent/issue-1023", "someone/fork")),
        api_pull(24, merged_at=after(33), head=Branch("agent/issue-12-extra")),
    ]
    selection = retro_gate.run_gate(RoutedClient(gate_routes(pulls)), REPO, 10)
    assert selection.selected is None
    assert selection.pending == 9


def test_counting_restarts_at_the_last_retro_run_not_the_selected_merge():
    """Issue #922: the retro after PR 10 merged selected the older PR 4."""
    pulls = ten_after_floor(pr4=(retro_counter.RETRO_DONE,)) + [
        api_pull(n, merged_at=after(n)) for n in range(11, 20)
    ]
    labelled_at = {4: after(10) + timedelta(minutes=30)}
    client = RoutedClient(gate_routes(pulls, labelled_at=labelled_at))
    selection = retro_gate.run_gate(client, REPO, 10)
    assert selection.selected is None
    assert selection.pending == 9  # 11..19, not 5..19


def _run_and_label(pulls: list[dict], labelled_at: dict[int, datetime], at: datetime):
    """One gate run at time ``at``; returns the pending numbers, labels the selection."""
    client = RoutedClient(gate_routes(pulls, labelled_at=labelled_at))
    eligible = retro_counter.eligible_pulls(retro_counter.merged_pulls(client, REPO), FLOOR)
    last = retro_counter.last_retro(client, REPO, eligible)
    pending = {pull.number for pull in retro_counter.pending_pulls(eligible, FLOOR, last)}
    selected = retro_gate.run_gate(client, REPO, 10).selected
    if selected is not None:
        labelled_at[selected] = at
        pulls[:] = [
            {**pull, "labels": [*pull["labels"], {"name": retro_counter.RETRO_DONE}]}
            if pull["number"] == selected
            else pull
            for pull in pulls
        ]
    return pending, selected


def test_an_older_selection_neither_drops_nor_recounts_merges():
    pulls = ten_after_floor(pr3=("review:block",))
    labelled_at: dict[int, datetime] = {}
    first, selected = _run_and_label(pulls, labelled_at, after(10) + timedelta(minutes=30))
    assert selected == 3
    assert first == set(range(1, 11))  # the ones merged before PR 3 count in this retro

    pulls += [api_pull(n, merged_at=after(n)) for n in range(11, 20)]
    second, selected = _run_and_label(pulls, labelled_at, after(20))
    assert selected is None
    assert second == set(range(11, 20))  # 4..10 do not count again

    pulls.append(api_pull(20, merged_at=after(20) + timedelta(minutes=10)))
    third, selected = _run_and_label(pulls, labelled_at, after(21))
    assert third == set(range(11, 21))
    assert selected == 20
    assert first.isdisjoint(third)


def test_removing_the_newest_label_makes_that_retro_pending_again():
    """The runbook's retry (docs/agents/retro.md): remove retro:done, run by hand."""
    pulls = [api_pull(n, merged_at=after(n)) for n in range(1, 21)]
    labelled_at = {2: after(10) + timedelta(minutes=30), 13: after(20) + timedelta(minutes=30)}
    with_labels = [
        {**pull, "labels": [{"name": retro_counter.RETRO_DONE}]}
        if pull["number"] in labelled_at
        else pull
        for pull in pulls
    ]
    client = RoutedClient(gate_routes(with_labels, labelled_at=labelled_at))
    assert retro_gate.run_gate(client, REPO, 10).pending == 0

    retried = [{**pull, "labels": []} if pull["number"] == 13 else pull for pull in with_labels]
    client = RoutedClient(gate_routes(retried, labelled_at={2: labelled_at[2]}))
    selection = retro_gate.run_gate(client, REPO, 10)
    assert selection.pending == 10  # 11..20, PR 13 among them
    assert selection.selected == 20


def test_the_label_time_is_the_newest_retro_done_event_across_pages():
    events_path = f"/repos/{REPO}/issues/4/events"
    routes = gate_routes(ten_after_floor(pr4=(retro_counter.RETRO_DONE,)))
    noise = [label_event("review:pass", after(1)) for _ in range(PER_PAGE)]
    routes[f"{events_path}?page=1"] = [label_event(retro_counter.RETRO_DONE, after(2)), *noise]
    routes[f"{events_path}?page=2"] = [
        label_event(retro_counter.RETRO_DONE, after(3), event="unlabeled"),
        label_event(retro_counter.RETRO_DONE, after(7)),
    ]
    routes[f"{events_path}?page=3"] = []
    client = RoutedClient(routes)
    selection = retro_gate.run_gate(client, REPO, 3)
    assert selection.pending == 3  # 8..10
    assert f"GET {events_path}?page=2" in client.events


def test_a_labelled_pull_without_a_label_event_fails_the_gate():
    client = RoutedClient(gate_routes(ten_after_floor(pr4=(retro_counter.RETRO_DONE,))))
    with pytest.raises(FetchError, match="no retro:done label event"):
        retro_gate.run_gate(client, REPO, 10)
    assert client.posts == []


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
    assert selected is not None
    second = RoutedClient(gate_routes(labelled, labelled_at={selected: after(11)}))
    assert retro_gate.run_gate(second, REPO, 10).selected is None
    assert second.posts == []
