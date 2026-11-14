"""Tests for the state rules of the automated issue triage."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from issue_triage_policy import (
    COMMENT_AUTHOR,
    COMMENT_MARKER,
    MAX_AUTOMATIC_TRIAGES,
    NEEDS_INFO,
    NEEDS_TRIAGE,
    READY_FOR_AGENT,
    READY_FOR_HUMAN,
    STATE_LABELS,
    WONTFIX,
    assess,
    plan_labels,
    unchanged_since_assessment,
)

LABELS_DOC = Path(__file__).resolve().parent.parent / "docs" / "agents" / "triage-labels.md"


def issue(**overrides: object) -> dict:
    facts = {
        "state": "open",
        "is_pull_request": False,
        "author_type": "User",
        "author_association": "OWNER",
        "labels": [NEEDS_TRIAGE, "bug"],
        "label_events": [],
    }
    facts.update(overrides)
    return facts


CREATED = "2026-11-13T10:00:00Z"
TRIAGED = "2026-11-13T10:02:00Z"
RELABELED = "2026-11-13T12:00:00Z"


def bot_triage(created_at: str = TRIAGED) -> dict:
    return {
        "author": COMMENT_AUTHOR,
        "body": f"{COMMENT_MARKER}\nearlier triage",
        "created_at": created_at,
    }


def labeled(created_at: str, actor_type: str = "User", label: str = NEEDS_TRIAGE) -> dict:
    return {"label": label, "actor_type": actor_type, "created_at": created_at}


def test_the_state_labels_match_the_tracker_vocabulary():
    rows = re.findall(
        r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|",
        LABELS_DOC.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    mapping: dict[str, str] = {}
    for role, label in rows:  # the role table comes first; later tables do not override it
        mapping.setdefault(role, label)
    assert tuple(mapping[role] for role in STATE_LABELS) == STATE_LABELS


@pytest.mark.parametrize("labels", [[], [NEEDS_TRIAGE], ["bug"]], ids=["none", "triage", "other"])
def test_a_new_issue_waiting_for_triage_is_eligible(labels: list[str]):
    decision = assess(issue(labels=labels), [], "opened")
    assert decision["eligible"] is True
    assert decision["skip_reason"] is None


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"is_pull_request": True}, "pull requests"),
        ({"state": "closed"}, "closed"),
        ({"author_type": "Bot"}, "bot"),
        ({"author_association": "NONE"}, "write access"),
        ({"author_association": "CONTRIBUTOR"}, "write access"),
        ({"labels": [NEEDS_TRIAGE, NEEDS_INFO]}, "conflicting"),
        ({"labels": [READY_FOR_AGENT]}, "not waiting"),
        ({"labels": [WONTFIX]}, "not waiting"),
    ],
)
def test_an_issue_outside_the_triage_queue_is_skipped(overrides: dict, reason: str):
    decision = assess(issue(**overrides), [], "opened")
    assert decision["eligible"] is False
    assert reason in decision["skip_reason"]


def test_a_reply_re_triages_only_a_needs_info_issue():
    assert assess(issue(labels=[NEEDS_INFO]), [bot_triage()], "reply")["eligible"] is True
    assert assess(issue(labels=[NEEDS_TRIAGE]), [], "reply")["eligible"] is False


def test_automatic_triggers_stop_at_the_limit_but_a_human_does_not():
    comments = [bot_triage()] * MAX_AUTOMATIC_TRIAGES
    capped = assess(issue(labels=[NEEDS_INFO]), comments, "reply")
    assert capped["eligible"] is False
    assert "limit" in capped["skip_reason"]
    relabeled = issue(label_events=[labeled(CREATED), labeled(RELABELED)])
    for trigger in ("relabel", "dispatch"):
        assert assess(relabeled, comments, trigger)["eligible"] is True


def test_opened_first_then_the_creation_label_event_does_not_triage_again():
    created = issue(label_events=[labeled(CREATED)])
    assert assess(created, [], "opened")["eligible"] is True
    decision = assess(created, [bot_triage()], "relabel")
    assert decision["eligible"] is False
    assert "since the last triage" in decision["skip_reason"]


def test_labeled_first_then_opened_does_not_triage_again():
    created = issue(label_events=[labeled(CREATED)])
    assert assess(created, [], "relabel")["eligible"] is True
    decision = assess(created, [bot_triage()], "opened")
    assert decision["eligible"] is False
    assert "first triage" in decision["skip_reason"]
    assert "limit" not in decision["skip_reason"]


def test_a_person_re_adding_needs_triage_after_the_triage_gets_a_run():
    once = issue(label_events=[labeled(CREATED), labeled(RELABELED)])
    assert assess(once, [bot_triage()], "relabel")["eligible"] is True
    older = issue(label_events=[labeled(CREATED)])
    triaged_twice = [bot_triage(), bot_triage(RELABELED)]
    assert assess(older, triaged_twice, "relabel")["eligible"] is False


@pytest.mark.parametrize(
    "event",
    [labeled(RELABELED, actor_type="Bot"), labeled(RELABELED, label="bug")],
    ids=["bot", "other-label"],
)
def test_only_a_persons_needs_triage_event_counts_as_a_re_add(event: dict):
    decision = assess(issue(label_events=[labeled(CREATED), event]), [bot_triage()], "relabel")
    assert decision["eligible"] is False
    assert "since the last triage" in decision["skip_reason"]


def test_only_the_bot_comment_with_the_marker_counts_as_a_triage():
    quoted = {"author": "someone", "body": f"quoting {COMMENT_MARKER}"}
    unmarked = {"author": COMMENT_AUTHOR, "body": "other bot comment"}
    decision = assess(issue(), [quoted, unmarked, bot_triage()], "opened")
    assert decision["bot_triages"] == 1


def test_an_unknown_trigger_is_an_error():
    with pytest.raises(ValueError, match="trigger"):
        assess(issue(), [], "push")


@pytest.mark.parametrize(
    ("current", "recommended", "add", "remove"),
    [
        ([NEEDS_TRIAGE], NEEDS_INFO, [NEEDS_INFO], [NEEDS_TRIAGE]),
        ([], NEEDS_INFO, [NEEDS_INFO], []),
        ([NEEDS_TRIAGE], READY_FOR_AGENT, [], []),
        ([NEEDS_TRIAGE], READY_FOR_HUMAN, [], []),
        ([NEEDS_TRIAGE], WONTFIX, [], []),
        ([], READY_FOR_AGENT, [NEEDS_TRIAGE], []),
        ([NEEDS_INFO, "bug"], READY_FOR_AGENT, [NEEDS_TRIAGE], [NEEDS_INFO]),
        ([NEEDS_INFO], NEEDS_INFO, [], []),
    ],
)
def test_the_bot_sets_needs_info_and_leaves_every_other_state_to_the_maintainer(
    current: list[str], recommended: str, add: list[str], remove: list[str]
):
    assert plan_labels(current, recommended) == {"add": add, "remove": remove}


def test_needs_triage_added_in_parallel_counts_as_unchanged():
    assert unchanged_since_assessment([], [NEEDS_TRIAGE, "bug"]) is True
    assert unchanged_since_assessment([NEEDS_TRIAGE], [NEEDS_TRIAGE]) is True
    assert unchanged_since_assessment([NEEDS_TRIAGE], [READY_FOR_AGENT]) is False
    assert unchanged_since_assessment([NEEDS_INFO], [NEEDS_TRIAGE]) is False
    assert unchanged_since_assessment([], [READY_FOR_HUMAN]) is False


def test_a_reply_requeues_a_needs_info_issue_even_past_the_limit_or_from_outside():
    capped = [bot_triage()] * MAX_AUTOMATIC_TRIAGES
    assert assess(issue(labels=[NEEDS_INFO]), capped, "reply")["requeue"] is True
    outside = issue(labels=[NEEDS_INFO], author_association="NONE")
    assert assess(outside, [], "reply")["requeue"] is True


@pytest.mark.parametrize(
    ("overrides", "trigger"),
    [
        ({"labels": [NEEDS_INFO]}, "opened"),
        ({"labels": [NEEDS_TRIAGE]}, "reply"),
        ({"labels": [NEEDS_INFO], "state": "closed"}, "reply"),
        ({"labels": [NEEDS_INFO], "is_pull_request": True}, "reply"),
    ],
)
def test_only_a_reply_on_an_open_needs_info_issue_requeues(overrides: dict, trigger: str):
    assert assess(issue(**overrides), [], trigger)["requeue"] is False
