"""Tests for the publish plan (scripts/pr_plan.py): shape, staleness, labels, reviewer.

The public seam is ``plan_publish(context, assessment, review, auto_merge)``.
Every test asserts the plan JSON, never a private helper, and no test
performs a network call.
"""

from __future__ import annotations

import pr_plan
import pytest
from pr_publish_testkit import (
    ACTION_KINDS,
    MAINTAINER,
    MARKER,
    actions_of,
    comment_action,
    file_entry,
    label_action,
    make_assessment,
    make_context,
    make_review,
)

# --- Plan shape and identity -------------------------------------------------


def test_plan_has_the_documented_shape():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    assert set(plan) == {
        "schema_version",
        "repo",
        "number",
        "head_sha",
        "status",
        "abort_reason",
        "decision",
        "actions",
    }
    assert plan["schema_version"] == 1
    assert plan["repo"] == "fabiandistler/agents"
    assert plan["number"] == 42
    assert plan["head_sha"] == "abc123"
    assert plan["status"] == "planned"
    assert plan["abort_reason"] is None


def test_plan_carries_the_decision_for_the_step_summary():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    assert plan["decision"] == {
        "risk": "low",
        "review_status": "ok",
        "verdict": "pass",
        "auto_merge": "off",
    }


def test_decision_reports_enabled_auto_merge():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review(), auto_merge=True)

    assert plan["decision"]["auto_merge"] == "enabled"


def test_decision_reports_disabled_auto_merge():
    context = make_context(
        labels=["risk:low", "review:pass", "auto-merge:bot"], auto_merge_active=True
    )

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(), auto_merge=False)

    assert plan["decision"]["auto_merge"] == "disabled"


def test_decision_reports_the_effective_risk_and_verdict():
    plan = pr_plan.plan_publish(
        make_context(), make_assessment(), make_review(risk="high", verdict="concerns")
    )

    assert plan["decision"]["risk"] == "high"
    assert plan["decision"]["verdict"] == "concerns"


def test_aborted_plan_has_no_decision_to_apply():
    plan = pr_plan.plan_publish(
        make_context(head_sha="def456"),
        make_assessment(head_sha="abc123"),
        make_review(head_sha="abc123"),
    )

    assert plan["decision"] == {
        "risk": None,
        "review_status": "ok",
        "verdict": None,
        "auto_merge": "off",
    }


def test_plan_uses_only_the_documented_action_kinds():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    assert {action["kind"] for action in plan["actions"]} <= ACTION_KINDS
    assert not any(
        word in action["kind"] for action in plan["actions"] for word in ("approve", "change")
    )


def test_docs_pull_request_plans_labels_comment_and_reviewer():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    assert [action["kind"] for action in plan["actions"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]
    assert label_action(plan)["add"] == ["risk:low", "review:pass"]
    assert label_action(plan)["remove"] == []
    assert actions_of(plan, "request_reviewer") == [
        {"kind": "request_reviewer", "login": MAINTAINER}
    ]
    assert comment_action(plan)["comment_id"] is None
    assert comment_action(plan)["marker"] == MARKER


# --- Staleness ---------------------------------------------------------------


def test_stale_assessment_sha_aborts_every_action():
    plan = pr_plan.plan_publish(
        make_context(head_sha="def456"),
        make_assessment(head_sha="abc123"),
        make_review(head_sha="abc123"),
        auto_merge=True,
    )

    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "head_sha_changed"
    assert plan["actions"] == []
    assert plan["head_sha"] == "def456"


def test_stale_review_sha_aborts_every_action():
    plan = pr_plan.plan_publish(
        make_context(head_sha="def456"),
        make_assessment(head_sha="def456"),
        make_review(head_sha="abc123"),
    )

    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "head_sha_changed"
    assert plan["actions"] == []


def test_review_without_a_head_sha_does_not_abort():
    plan = pr_plan.plan_publish(
        make_context(),
        make_assessment(),
        make_review(status="skipped", head_sha=None, risk=None, verdict=None, findings=[]),
    )

    assert plan["status"] == "planned"
    assert plan["abort_reason"] is None


# --- Risk and verdict labels -------------------------------------------------


def test_fresh_policy_overrides_the_assessment_risk():
    plan = pr_plan.plan_publish(
        make_context(),
        make_assessment(risk="high"),
        make_review(),
    )

    assert label_action(plan)["add"] == ["risk:low", "review:pass"]


def test_review_risk_never_lowers_the_policy_risk():
    context = make_context(files=[file_entry(".github/workflows/ci.yml")])

    plan = pr_plan.plan_publish(context, make_assessment(), make_review(risk="low"))

    labels = label_action(plan)
    assert "risk:high" in labels["add"]
    assert actions_of(plan, "enable_auto_merge") == []


def test_review_risk_raises_the_policy_risk():
    plan = pr_plan.plan_publish(
        make_context(),
        make_assessment(),
        make_review(risk="high", verdict="concerns"),
    )

    labels = label_action(plan)
    assert "risk:high" in labels["add"]
    assert "risk:low" not in labels["add"]
    assert "needs-review" in labels["add"]


def test_risk_label_family_is_replaced_not_accumulated():
    context = make_context(labels=["risk:high", "review:block", "needs-review"])

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    labels = label_action(plan)
    assert labels["add"] == ["risk:low", "review:pass"]
    assert labels["remove"] == ["risk:high", "review:block", "needs-review"]


def test_verdict_label_family_is_replaced_without_touching_risk():
    context = make_context(labels=["risk:low", "review:pass"])
    review = make_review(verdict="concerns")

    plan = pr_plan.plan_publish(context, make_assessment(), review)

    labels = label_action(plan)
    assert labels["add"] == ["review:concerns", "needs-review"]
    assert labels["remove"] == ["review:pass"]


def test_already_correct_labels_plan_no_label_action():
    context = make_context(labels=["risk:low", "review:pass"])

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    assert actions_of(plan, "set_labels") == []


def test_unavailable_review_labels_review_unavailable_and_needs_review():
    review = make_review(
        status="unavailable",
        risk="high",
        verdict=None,
        summary="Review unavailable: the provider call failed.",
        findings=[],
    )

    plan = pr_plan.plan_publish(make_context(), make_assessment(), review)

    labels = label_action(plan)
    assert "review:unavailable" in labels["add"]
    assert "needs-review" in labels["add"]
    assert not any(label.startswith("review:pass") for label in labels["add"])


def test_unavailable_review_replaces_a_stale_verdict_label():
    context = make_context(labels=["review:pass"])
    review = make_review(
        status="unavailable",
        risk="high",
        verdict=None,
        summary="Review unavailable: the provider call failed.",
        findings=[],
    )

    plan = pr_plan.plan_publish(context, make_assessment(), review)

    labels = label_action(plan)
    assert "review:unavailable" in labels["add"]
    assert labels["remove"] == ["review:pass"]


def test_skipped_review_plans_no_verdict_label():
    context = make_context(draft=True, labels=["review:concerns"])
    review = make_review(
        status="skipped",
        risk=None,
        verdict=None,
        summary="Review skipped: the pull request is a draft.",
        findings=[],
    )

    plan = pr_plan.plan_publish(context, make_assessment(), review)

    labels = label_action(plan)
    assert labels["add"] == ["risk:low"]
    assert labels["remove"] == ["review:concerns"]


# --- Reviewer or assignee ----------------------------------------------------


def test_self_authored_pull_request_is_assigned_and_needs_review():
    context = make_context(author=MAINTAINER, files=[file_entry("skills/x/SKILL.md")])
    review = make_review(risk="medium", verdict="concerns")

    plan = pr_plan.plan_publish(context, make_assessment(), review)

    assert actions_of(plan, "request_reviewer") == []
    assert actions_of(plan, "assign") == [{"kind": "assign", "login": MAINTAINER}]
    assert "needs-review" in label_action(plan)["add"]


def test_self_authored_low_risk_pull_request_still_carries_needs_review():
    context = make_context(author=MAINTAINER)

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    assert actions_of(plan, "assign") == [{"kind": "assign", "login": MAINTAINER}]
    assert "needs-review" in label_action(plan)["add"]


def test_foreign_pull_request_requests_the_maintainer_as_reviewer():
    context = make_context(author="octocat")

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    assert actions_of(plan, "assign") == []
    assert actions_of(plan, "request_reviewer") == [
        {"kind": "request_reviewer", "login": MAINTAINER}
    ]


@pytest.mark.parametrize("author", ["octocat", MAINTAINER])
def test_a_draft_is_labeled_but_neither_requests_nor_assigns(author):
    # A draft is not ready for review; ready_for_review runs publish again
    # without the draft flag, and that run asks for the reviewer.
    context = make_context(author=author, draft=True)
    review = make_review(status="skipped", risk=None, verdict=None, findings=[])

    plan = pr_plan.plan_publish(context, make_assessment(), review)

    assert actions_of(plan, "request_reviewer") == []
    assert actions_of(plan, "assign") == []
    assert "risk:low" in label_action(plan)["add"]

    ready = pr_plan.plan_publish(make_context(author=author), make_assessment(), make_review())
    assert actions_of(ready, "request_reviewer") + actions_of(ready, "assign") != []
