"""Tests for the auto-merge hold, the review-free plan of ``pr_plan.plan_hold``.

The workflow runs the hold on every push and when ``do-not-merge`` is added.
GitHub keeps auto-merge on when someone with write access pushes, so without
the hold a new, unreviewed head could merge before its review is published.
The hold disables the bot's auto-merge (any auto-merge under ``do-not-merge``)
and never enables anything; the publish run after the review decides again.
On a push it also takes every ``review:*`` label off, so a verdict label always
describes the current head (#1034).
"""

from __future__ import annotations

import pr_plan
import pytest
from pr_publish_testkit import REMOVE_BOT_LABEL, actions_of, make_context

NODE_ID = "PR_kwDOtest42"
DISABLE = {"kind": "disable_auto_merge", "pull_request_id": NODE_ID}
PUSH = "synchronize"
LABELED = "labeled"
VERDICTS = ["review:pass", "review:concerns", "review:block", "review:unavailable"]


@pytest.mark.parametrize(
    ("event", "labels", "active", "actions", "state"),
    [
        (PUSH, ["risk:low", "auto-merge:bot"], True, [DISABLE, REMOVE_BOT_LABEL], "disabled"),
        (LABELED, ["do-not-merge"], True, [DISABLE], "disabled"),
        (
            LABELED,
            ["do-not-merge", "auto-merge:bot"],
            True,
            [DISABLE, REMOVE_BOT_LABEL],
            "disabled",
        ),
        (PUSH, ["risk:low"], True, [], "human"),
        (PUSH, ["auto-merge:bot"], False, [REMOVE_BOT_LABEL], "off"),
        (LABELED, ["do-not-merge"], False, [], "off"),
        (PUSH, [], False, [], "off"),
    ],
    ids=[
        "bot auto-merge on a push",
        "do-not-merge on a human auto-merge",
        "do-not-merge on the bot auto-merge",
        "human auto-merge on a push",
        "stale bot label",
        "do-not-merge without auto-merge",
        "nothing to hold",
    ],
)
def test_the_hold_disables_only_what_it_may(event, labels, active, actions, state):
    plan = pr_plan.plan_hold(make_context(labels=labels, auto_merge_active=active), event)

    assert plan["status"] == "planned"
    assert plan["actions"] == actions
    assert plan["decision"] == {
        "risk": None,
        "review_status": None,
        "verdict": None,
        "auto_merge": state,
    }


@pytest.mark.parametrize("event", [PUSH, LABELED])
def test_the_hold_never_enables_auto_merge(event):
    plan = pr_plan.plan_hold(make_context(labels=["risk:low", "review:pass"]), event)

    assert actions_of(plan, "enable_auto_merge") == []


# --- A push clears the verdict label (#1034) ----------------------------------


@pytest.mark.parametrize("verdict", VERDICTS)
def test_a_push_takes_the_verdict_label_off(verdict):
    context = make_context(labels=["risk:low", verdict, "needs-review"])

    plan = pr_plan.plan_hold(context, PUSH)

    assert plan["actions"] == [{"kind": "set_labels", "add": [], "remove": [verdict]}]


def test_a_push_clears_the_verdict_after_the_auto_merge_disable():
    context = make_context(
        labels=["risk:low", "review:pass", "auto-merge:bot"], auto_merge_active=True
    )

    plan = pr_plan.plan_hold(context, PUSH)

    assert plan["actions"] == [
        DISABLE,
        REMOVE_BOT_LABEL,
        {"kind": "set_labels", "add": [], "remove": ["review:pass"]},
    ]


def test_a_push_without_a_verdict_label_plans_no_label_action():
    plan = pr_plan.plan_hold(make_context(labels=["risk:high", "needs-review"]), PUSH)

    assert actions_of(plan, "set_labels") == []


@pytest.mark.parametrize("verdict", VERDICTS)
def test_do_not_merge_leaves_the_verdict_label(verdict):
    context = make_context(labels=["do-not-merge", verdict], auto_merge_active=True)

    plan = pr_plan.plan_hold(context, LABELED)

    assert plan["actions"] == [DISABLE]


def test_the_hold_rejects_an_unknown_event():
    with pytest.raises(ValueError, match="event"):
        pr_plan.plan_hold(make_context(labels=["review:pass"]), "opened")


def test_the_hold_of_a_closed_pull_request_does_nothing():
    context = make_context(state="closed", labels=["auto-merge:bot"], auto_merge_active=True)

    plan = pr_plan.plan_hold(context, PUSH)

    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "pull_request_closed"
    assert plan["actions"] == []


def test_the_hold_rejects_a_context_without_a_node_id():
    context = make_context(labels=["auto-merge:bot"], auto_merge_active=True)
    del context["node_id"]

    with pytest.raises(pr_plan.ArtifactError, match="node_id"):
        pr_plan.plan_hold(context, PUSH)
