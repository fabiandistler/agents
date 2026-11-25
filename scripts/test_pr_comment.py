"""Tests for the sticky review comment (scripts/pr_comment.py).

The comment is asserted through the ``upsert_comment`` action of the plan.
"""

from __future__ import annotations

import pr_plan
import pytest
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
    assert "abc1234" in body


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
    # Partial covers both causes: cut to the limits, or hidden markup removed.
    assert "hidden markup" in comment_body(plan)
    assert actions_of(plan, "enable_auto_merge") == []


def omissions(**overrides: object) -> dict:
    record = {
        "diff_cut": False,
        "diff_markup_removed": False,
        "diff_last_full_file": None,
        "diff_files_not_in_full": [],
        "base_content_missing": [],
    }
    record.update(overrides)
    return record


def test_comment_names_the_files_sent_without_base_content_on_a_complete_review():
    missing = ["scripts/implementer_claim.py", "scripts/test_implementer_claim.py"]
    review = make_review(omissions=omissions(base_content_missing=missing))

    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), review))

    assert "Partial review" not in body
    assert (
        "> **Sent without base content:** `scripts/implementer_claim.py`, "
        "`scripts/test_implementer_claim.py`." in body
    )
    assert "The diff was reviewed in full." in body


def test_comment_names_the_last_file_shown_in_full_and_the_files_not_shown_on_a_diff_cut():
    review = make_review(
        partial=True,
        omissions=omissions(
            diff_cut=True,
            diff_last_full_file="scripts/b.py",
            diff_files_not_in_full=["scripts/c.py", "scripts/d.py"],
        ),
    )

    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), review))

    assert "> **Partial review.** Parts of the diff were not reviewed" in body
    assert "the last file shown in full is `scripts/b.py`" in body
    assert "not shown in full: `scripts/c.py`, `scripts/d.py`" in body
    assert "hidden markup" not in body


def test_comment_bounds_the_named_files_and_counts_the_rest():
    missing = [f"docs/page-{number:02d}.md" for number in range(25)]
    review = make_review(omissions=omissions(base_content_missing=missing))

    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), review))

    assert "`docs/page-19.md` and 5 more." in body
    assert "docs/page-20.md" not in body


def test_comment_names_removed_markup_as_the_cause_of_a_partial_review():
    review = make_review(partial=True, omissions=omissions(diff_markup_removed=True))

    body = comment_body(pr_plan.plan_publish(make_context(), make_assessment(), review))

    assert "not reviewed: hidden markup was removed from the diff." in body


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


@pytest.mark.parametrize(
    "record",
    [
        [],
        {"diff_cut": "yes"},
        {"diff_last_full_file": 3},
        {"diff_files_not_in_full": "scripts/a.py"},
        {"base_content_missing": [None]},
    ],
)
def test_a_malformed_omissions_record_is_bad_input(record):
    with pytest.raises(pr_plan.ArtifactError, match="omissions"):
        pr_plan.plan_publish(make_context(), make_assessment(), make_review(omissions=record))
