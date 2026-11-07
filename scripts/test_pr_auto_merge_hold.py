"""Tests for the auto-merge hold, the review-free plan of ``pr_plan.plan_hold``.

The workflow runs the hold on every push and when ``do-not-merge`` is added.
GitHub keeps auto-merge on when someone with write access pushes, so without
the hold a new, unreviewed head could merge before its review is published.
The hold disables the bot's auto-merge (any auto-merge under ``do-not-merge``)
and never enables anything; the publish run after the review decides again.
"""

from __future__ import annotations

import pr_plan
import pytest
from pr_publish_testkit import actions_of, make_context

NODE_ID = "PR_kwDOtest42"
DISABLE = {"kind": "disable_auto_merge", "pull_request_id": NODE_ID}


@pytest.mark.parametrize(
    ("labels", "active", "actions", "state"),
    [
        (
            ["risk:low", "auto-merge:bot"],
            True,
            [{"kind": "set_labels", "add": [], "remove": ["auto-merge:bot"]}, DISABLE],
            "disabled",
        ),
        (["do-not-merge"], True, [DISABLE], "disabled"),
        (
            ["do-not-merge", "auto-merge:bot"],
            True,
            [{"kind": "set_labels", "add": [], "remove": ["auto-merge:bot"]}, DISABLE],
            "disabled",
        ),
        (["risk:low"], True, [], "human"),
        (
            ["auto-merge:bot"],
            False,
            [{"kind": "set_labels", "add": [], "remove": ["auto-merge:bot"]}],
            "off",
        ),
        (["do-not-merge"], False, [], "off"),
        ([], False, [], "off"),
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
def test_the_hold_disables_only_what_it_may(labels, active, actions, state):
    plan = pr_plan.plan_hold(make_context(labels=labels, auto_merge_active=active))

    assert plan["status"] == "planned"
    assert plan["actions"] == actions
    assert plan["decision"] == {
        "risk": None,
        "review_status": None,
        "verdict": None,
        "auto_merge": state,
    }


def test_the_hold_never_enables_auto_merge():
    plan = pr_plan.plan_hold(make_context(labels=["risk:low", "review:pass"]))

    assert actions_of(plan, "enable_auto_merge") == []


def test_the_hold_of_a_closed_pull_request_does_nothing():
    context = make_context(state="closed", labels=["auto-merge:bot"], auto_merge_active=True)

    plan = pr_plan.plan_hold(context)

    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "pull_request_closed"
    assert plan["actions"] == []


def test_the_hold_rejects_a_context_without_a_node_id():
    context = make_context(labels=["auto-merge:bot"], auto_merge_active=True)
    del context["node_id"]

    with pytest.raises(pr_plan.ArtifactError, match="node_id"):
        pr_plan.plan_hold(context)
