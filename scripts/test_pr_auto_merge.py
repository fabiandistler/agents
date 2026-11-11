"""Tests for the auto-merge decision, asserted through ``plan_publish``.

Auto-merge logic lives in scripts/pr_auto_merge.py; these tests read only the
plan JSON that ``pr_plan.plan_publish`` returns.
"""

from __future__ import annotations

from typing import Any

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


BOT_LABELS = ["risk:low", "review:pass", "auto-merge:bot"]
NODE_ID = "PR_kwDOtest42"
# Every gate except unknown mergeability is a failed gate: it disables an
# active bot auto-merge. Unknown mergeability only blocks enabling.
FAILED_GATES = [case for case in AUTO_MERGE_BLOCKERS if case[0] != "mergeability unknown"]


def bot_auto_merge_context(labels: list[str] | None = None, **overrides: Any) -> dict:
    return make_context(labels=[*BOT_LABELS, *(labels or [])], auto_merge_active=True, **overrides)


def auto_merge_actions(plan: dict) -> list[dict]:
    kinds = ("enable_auto_merge", "disable_auto_merge")
    return [action for action in plan["actions"] if action["kind"] in kinds]


def test_low_risk_pass_enables_native_auto_merge():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review(), auto_merge=True)

    assert [action["kind"] for action in plan["actions"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
        "enable_auto_merge",
        "set_status",
    ]
    # Merge commit, pinned to the reviewed head. Branch deletion comes from the
    # repository setting delete_branch_on_merge, not from the plan.
    assert plan["actions"][-2] == {
        "kind": "enable_auto_merge",
        "pull_request_id": NODE_ID,
        "method": "merge",
        "expected_head_oid": "abc1234",
    }
    assert label_action(plan)["add"] == ["risk:low", "review:pass", "auto-merge:bot"]
    assert plan["decision"]["auto_merge"] == "enabled"


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


def test_an_active_bot_auto_merge_is_kept_without_writes_while_the_gates_hold():
    plan = pr_plan.plan_publish(
        bot_auto_merge_context(), make_assessment(), make_review(), auto_merge=True
    )

    assert auto_merge_actions(plan) == []
    assert actions_of(plan, "set_labels") == []
    assert plan["decision"]["auto_merge"] == "kept"


def test_unknown_mergeability_keeps_an_active_bot_auto_merge():
    plan = pr_plan.plan_publish(
        bot_auto_merge_context(mergeable=None), make_assessment(), make_review(), auto_merge=True
    )

    assert auto_merge_actions(plan) == []
    assert plan["decision"]["auto_merge"] == "kept"


@pytest.mark.parametrize(
    ("auto_merge", "context_overrides", "review_overrides"),
    [case[1:] for case in FAILED_GATES],
    ids=[case[0] for case in FAILED_GATES],
)
def test_every_failed_gate_disables_the_bots_auto_merge(
    auto_merge, context_overrides, review_overrides
):
    plan = pr_plan.plan_publish(
        bot_auto_merge_context(**context_overrides),
        make_assessment(),
        make_review(**review_overrides),
        auto_merge=auto_merge,
    )

    assert auto_merge_actions(plan) == [{"kind": "disable_auto_merge", "pull_request_id": NODE_ID}]
    labels = label_action(plan)
    assert "auto-merge:bot" in labels["remove"]
    assert "auto-merge:bot" not in labels["add"]
    assert plan["decision"]["auto_merge"] == "disabled"


def test_a_raised_risk_relabels_while_it_disables():
    context = bot_auto_merge_context(files=[file_entry("skills/x/SKILL.md")])

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=True)

    assert "risk:medium" in label_action(plan)["add"]
    assert len(actions_of(plan, "disable_auto_merge")) == 1


def test_a_human_enabled_auto_merge_is_never_taken_over():
    context = make_context(labels=["risk:low", "review:pass"], auto_merge_active=True)

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=True)

    assert auto_merge_actions(plan) == []
    assert actions_of(plan, "set_labels") == []
    assert plan["decision"]["auto_merge"] == "human"


def test_do_not_merge_disables_a_human_enabled_auto_merge():
    context = make_context(labels=["do-not-merge"], auto_merge_active=True)

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=True)

    assert auto_merge_actions(plan) == [{"kind": "disable_auto_merge", "pull_request_id": NODE_ID}]
    assert "auto-merge:bot" not in label_action(plan)["add"]
    assert plan["decision"]["auto_merge"] == "disabled"


def test_do_not_merge_is_never_removed_by_the_publisher():
    context = make_context(labels=["do-not-merge"])

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    labels = label_action(plan)
    assert "do-not-merge" not in labels["add"]
    assert "do-not-merge" not in labels["remove"]
    assert actions_of(plan, "enable_auto_merge") == []


def test_a_human_enabled_auto_merge_is_never_disabled_by_a_failed_gate():
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


# --- Decision D: GitHub refused to arm auto-merge -----------------------------


def refused_plan(**context_overrides: Any) -> dict:
    return pr_plan.plan_publish(
        make_context(**context_overrides),
        make_assessment(),
        make_review(),
        auto_merge=True,
        auto_merge_refused=True,
    )


def test_a_refused_auto_merge_is_not_enabled_again_and_asks_for_a_human():
    plan = refused_plan(labels=["risk:low", "review:pass", "auto-merge:bot"])

    assert plan["decision"]["auto_merge"] == "refused"
    assert actions_of(plan, "enable_auto_merge") == []
    assert label_action(plan) == {
        "kind": "set_labels",
        "add": ["needs-review"],
        "remove": ["auto-merge:bot"],
    }


def test_the_comment_says_a_refused_auto_merge_could_not_be_armed():
    body = actions_of(refused_plan(), "upsert_comment")[0]["body"]

    assert "Auto-merge could not be armed" in body


def test_a_refusal_changes_nothing_when_the_gates_no_longer_hold():
    plan = refused_plan(mergeable=False)

    assert plan["decision"]["auto_merge"] == "off"
    assert "needs-review" not in label_action(plan)["add"]


def test_a_context_without_a_node_id_is_bad_input():
    context = make_context()
    del context["node_id"]

    with pytest.raises(pr_plan.ArtifactError, match="node_id"):
        pr_plan.plan_publish(context, make_assessment(), make_review())


@pytest.mark.parametrize("labels", [None, "do-not-merge", ["do-not-merge", 7]])
def test_a_context_with_unreadable_labels_is_bad_input(labels):
    # Ignoring an unreadable label list could hide do-not-merge.
    context = make_context(labels=labels, auto_merge_active=True)

    with pytest.raises(pr_plan.ArtifactError, match="labels"):
        pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=True)
    with pytest.raises(pr_plan.ArtifactError, match="labels"):
        pr_plan.plan_hold(context)
