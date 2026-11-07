"""Tests for the auto-merge decision, asserted through ``plan_publish``.

Auto-merge logic lives in scripts/pr_auto_merge.py; these tests read only the
plan JSON that ``pr_plan.plan_publish`` returns.
"""

from __future__ import annotations

import pr_plan
import pytest
from pr_publish_testkit import (
    actions_of,
    file_entry,
    label_action,
    make_assessment,
    make_context,
    make_review,
)

# --- Auto-merge gates --------------------------------------------------------

AUTO_MERGE_BLOCKERS = [
    ("variable off", {"auto_merge": False}, {}, {}),
    ("risk medium", {}, {"files": [file_entry("skills/x/SKILL.md")]}, {}),
    ("risk high", {}, {"files": [file_entry(".github/workflows/ci.yml")]}, {}),
    ("review raises the risk", {}, {}, {"risk": "high"}),
    ("verdict concerns", {}, {}, {"verdict": "concerns"}),
    ("verdict block", {}, {}, {"verdict": "block"}),
    ("partial review", {}, {}, {"partial": True}),
    ("fork", {}, {"fork": True}, {}),
    ("draft", {}, {"draft": True}, {}),
    ("not mergeable", {}, {"mergeable": False}, {}),
    ("mergeability unknown", {}, {"mergeable": None}, {}),
    ("wrong base branch", {}, {"base_ref": "release"}, {}),
    ("human change request", {}, {"reviews": {"changes_requested": True}}, {}),
    ("do-not-merge label", {}, {"labels": ["do-not-merge"]}, {}),
    (
        "checks failing",
        {},
        {"checks": {"checks": "failure", "mermaid": "success", "secrets": "success"}},
        {},
    ),
    (
        "checks pending",
        {},
        {"checks": {"checks": "pending", "mermaid": "success", "secrets": "success"}},
        {},
    ),
    (
        "checks missing",
        {},
        {"checks": {"mermaid": "success", "secrets": "success"}},
        {},
    ),
    (
        "mermaid failing",
        {},
        {"checks": {"checks": "success", "mermaid": "failure", "secrets": "success"}},
        {},
    ),
    (
        "secrets skipped",
        {},
        {"checks": {"checks": "success", "mermaid": "success", "secrets": "skipped"}},
        {},
    ),
    (
        "review unavailable",
        {},
        {},
        {
            "status": "unavailable",
            "risk": "high",
            "verdict": None,
            "summary": "Review unavailable: the provider call failed.",
            "findings": [],
        },
    ),
    (
        "review skipped",
        {},
        {},
        {
            "status": "skipped",
            "risk": None,
            "verdict": None,
            "summary": "Review skipped: the pull request is a draft.",
            "findings": [],
        },
    ),
]


@pytest.mark.parametrize(
    ("auto_merge", "context_overrides", "review_overrides"),
    [case[1:] for case in AUTO_MERGE_BLOCKERS],
    ids=[case[0] for case in AUTO_MERGE_BLOCKERS],
)
def test_every_auto_merge_gate_blocks(auto_merge, context_overrides, review_overrides):
    plan = pr_plan.plan_publish(
        make_context(**context_overrides),
        make_assessment(),
        make_review(**review_overrides),
        auto_merge=auto_merge,
    )

    assert actions_of(plan, "enable_auto_merge") == []


def test_low_risk_pass_enables_native_auto_merge():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review(), auto_merge=True)

    assert [action["kind"] for action in plan["actions"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
        "enable_auto_merge",
    ]
    assert plan["actions"][-1] == {
        "kind": "enable_auto_merge",
        "method": "merge",
        "delete_branch": True,
    }
    assert label_action(plan)["add"] == ["risk:low", "review:pass", "auto-merge:bot"]


def test_auto_merge_variable_must_be_exactly_true():
    for value in ("TRUE", "True", "1", "yes", "", None):
        plan = pr_plan.plan_publish(
            make_context(), make_assessment(), make_review(), auto_merge=value
        )
        assert actions_of(plan, "enable_auto_merge") == [], value

    enabled = pr_plan.plan_publish(
        make_context(), make_assessment(), make_review(), auto_merge="true"
    )
    assert len(actions_of(enabled, "enable_auto_merge")) == 1


def test_a_raised_risk_disables_the_bots_auto_merge():
    context = make_context(
        files=[file_entry("skills/x/SKILL.md")],
        labels=["risk:low", "review:pass", "auto-merge:bot"],
        auto_merge_active=True,
    )

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=True)

    assert actions_of(plan, "disable_auto_merge") == [{"kind": "disable_auto_merge"}]
    labels = label_action(plan)
    assert "auto-merge:bot" in labels["remove"]
    assert "auto-merge:bot" not in labels["add"]
    assert "risk:medium" in labels["add"]


def test_turning_the_variable_off_disables_the_bots_auto_merge():
    context = make_context(
        labels=["risk:low", "review:pass", "auto-merge:bot"], auto_merge_active=True
    )

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=False)

    assert actions_of(plan, "disable_auto_merge") == [{"kind": "disable_auto_merge"}]
    assert "auto-merge:bot" in label_action(plan)["remove"]


def test_do_not_merge_is_never_removed_by_the_publisher():
    context = make_context(labels=["do-not-merge"])

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    labels = label_action(plan)
    assert "do-not-merge" not in labels["add"]
    assert "do-not-merge" not in labels["remove"]
    assert actions_of(plan, "enable_auto_merge") == []


def test_a_human_enabled_auto_merge_is_never_touched():
    context = make_context(labels=["risk:low", "review:pass"], auto_merge_active=True)

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=False)

    assert actions_of(plan, "disable_auto_merge") == []
    assert actions_of(plan, "set_labels") == []


def test_a_stale_bot_label_without_active_auto_merge_is_only_removed():
    context = make_context(labels=["risk:low", "review:pass", "auto-merge:bot"])

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=False)

    assert actions_of(plan, "disable_auto_merge") == []
    assert label_action(plan)["remove"] == ["auto-merge:bot"]
    assert plan["decision"]["auto_merge"] == "off"


def test_auto_merge_is_not_enabled_twice():
    context = make_context(labels=["risk:low", "review:pass", "auto-merge:bot"])

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=True)

    assert len(actions_of(plan, "enable_auto_merge")) == 1
    assert actions_of(plan, "set_labels") == []
