"""Tests for the sticky review comment (scripts/pr_comment.py).

The comment is asserted through the ``upsert_comment`` action of the plan.
"""

from __future__ import annotations

import pr_plan
from pr_publish_testkit import (
    BOT_AUTHOR,
    MARKER,
    actions_of,
    comment_action,
    make_assessment,
    make_context,
    make_review,
)

# --- Sticky comment ----------------------------------------------------------


def comment_body(plan: dict) -> str:
    return comment_action(plan)["body"]


def test_comment_starts_with_the_marker_and_states_risk_and_verdict():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    body = comment_body(plan)
    assert body.startswith(MARKER)
    assert "risk **low**" in body
    assert "verdict **pass**" in body
    assert "abc123" in body


def test_comment_carries_the_summary_and_the_policy_reasons():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    body = comment_body(plan)
    assert "The documentation change is accurate and complete." in body
    assert "docs: docs/guide.md" in body


def test_comment_lists_findings_with_location_severity_message_and_fix():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    body = comment_body(plan)
    assert "`docs/guide.md:12`" in body
    assert "**info**" in body
    assert "The heading could name the command it documents." in body
    assert "Fix: Use the command name in the heading." in body


def test_comment_renders_a_finding_without_a_line_or_a_suggestion():
    review = make_review(
        findings=[
            {
                "path": "docs/guide.md",
                "line": None,
                "severity": "warning",
                "message": "The example is stale.",
                "suggestion": "",
            }
        ]
    )

    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), review))

    assert "`docs/guide.md`" in body
    assert "`docs/guide.md:None`" not in body
    assert "Fix:" not in body


def test_comment_says_the_bot_never_approves_or_merges_directly():
    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), make_review()))

    assert "never approves" in body
    assert "never merges" in body


def test_comment_reports_a_review_that_raised_the_risk():
    review = make_review(risk="high", verdict="concerns")

    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), review))

    assert "risk **high**" in body
    assert "raised the risk from low to high" in body


def test_comment_warns_about_a_partial_review():
    review = make_review(partial=True)

    plan = pr_plan.plan_publish(make_context(), make_assessment(), review, auto_merge=True)

    assert "Partial review" in comment_body(plan)
    assert actions_of(plan, "enable_auto_merge") == []


def test_comment_reports_an_unavailable_review():
    review = make_review(
        status="unavailable",
        risk="high",
        verdict=None,
        summary="Review unavailable: the provider is not configured.",
        findings=[],
    )

    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), review))

    assert "review unavailable" in body
    assert "Review unavailable: the provider is not configured." in body
    assert "Auto-merge stays off until a review succeeds." in body
    assert "**Findings**" not in body


def test_comment_reports_a_skipped_draft_review():
    context = make_context(draft=True)
    review = make_review(
        status="skipped",
        risk=None,
        verdict=None,
        summary="Review skipped: the pull request is a draft.",
        findings=[],
    )

    body = comment_body(pr_plan.plan_publish(context, make_assessment(), review))

    assert "review skipped" in body
    assert "Review skipped: the pull request is a draft." in body
    assert "Auto-merge stays off until the pull request is ready for review." in body


def test_comment_reports_a_skipped_fork_review():
    context = make_context(fork=True)
    review = make_review(
        status="skipped",
        risk=None,
        verdict=None,
        summary="Review skipped: the pull request comes from a fork.",
        findings=[],
    )

    body = comment_body(pr_plan.plan_publish(context, make_assessment(), review))

    assert "Fork pull requests are never auto-merged." in body


def test_comment_shows_an_unparseable_response_verbatim():
    review = make_review(
        risk="high",
        verdict="concerns",
        summary="",
        findings=[],
        raw="RISK low\nlooks fine to me",
    )

    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), review))

    assert "could not be parsed" in body
    assert "RISK low\nlooks fine to me" in body


def test_unchanged_sticky_comment_plans_no_comment_action():
    first = pr_plan.plan_publish(make_context(), make_assessment(), make_review())
    body = comment_body(first)
    context = make_context(comments=[{"id": 7, "body": body, "author": BOT_AUTHOR}])

    second = pr_plan.plan_publish(context, make_assessment(), make_review())

    assert actions_of(second, "upsert_comment") == []


def test_existing_sticky_comment_is_updated_in_place():
    context = make_context(
        comments=[{"id": 7, "body": f"{MARKER}\nold assessment", "author": BOT_AUTHOR}]
    )

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    comment = comment_action(plan)
    assert comment["comment_id"] == 7
    assert "old assessment" not in comment["body"]


def test_comment_ignores_comments_without_the_marker():
    context = make_context(
        comments=[
            {"id": 1, "body": "Looks good to me.", "author": BOT_AUTHOR},
            {"id": 7, "body": f"{MARKER}\nold assessment", "author": BOT_AUTHOR},
        ]
    )

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    assert comment_action(plan)["comment_id"] == 7


def test_a_human_comment_quoting_the_marker_is_never_overwritten():
    context = make_context(
        comments=[{"id": 3, "body": f"Why does it say {MARKER}?", "author": "someone-else"}]
    )

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    assert comment_action(plan)["comment_id"] is None, "a human comment is never edited"


def test_the_bot_comment_is_found_after_a_human_comment_quoting_the_marker():
    context = make_context(
        comments=[
            {"id": 3, "body": f"{MARKER} copied here", "author": "someone-else"},
            {"id": 7, "body": f"{MARKER}\nold assessment", "author": BOT_AUTHOR},
        ]
    )

    plan = pr_plan.plan_publish(context, make_assessment(), make_review())

    assert comment_action(plan)["comment_id"] == 7


def test_comment_body_does_not_depend_on_the_auto_merge_decision():
    quiet = pr_plan.plan_publish(make_context(), make_assessment(), make_review())
    merging = pr_plan.plan_publish(
        make_context(), make_assessment(), make_review(), auto_merge=True
    )

    assert comment_body(quiet) == comment_body(merging)
