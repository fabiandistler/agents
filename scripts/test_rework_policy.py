"""The Rework gate's decision: the proceed case, the cap, and every stop case."""

from __future__ import annotations

import pytest
import rework_policy
from rework_testkit import (
    HEAD,
    ISSUE,
    OTHER_HEAD,
    THIRD_HEAD,
    comment,
    context,
    facts,
    head,
    issue,
    marker,
    pull,
    review,
    run,
)


def test_a_non_pass_review_with_findings_proceeds_as_round_one():
    decision = rework_policy.decide(**facts())
    assert decision == rework_policy.Decision(
        rework_policy.PROCEED, "the review has findings to rework", ISSUE, 1, HEAD
    )


def test_a_block_verdict_proceeds_too():
    assert rework_policy.decide(**facts(review=review(verdict="block"))).action == "proceed"


def test_the_second_round_counts_the_first_marker():
    decision = rework_policy.decide(**facts(comments=[comment(marker(1, OTHER_HEAD))]))
    assert (decision.action, decision.round) == (rework_policy.PROCEED, 2)


STOP_CASES = {
    "run failed": {"run": run(conclusion="failure")},
    "run cancelled": {"run": run(conclusion="cancelled")},
    "run from a manual review": {"run": run(event="workflow_dispatch")},
    "run of another workflow": {"run": run(path=".github/workflows/ci.yml")},
    "run for another head": {"run": run(head_sha=OTHER_HEAD)},
    "run without a head": {"run": run(head_sha=None)},
    "pull request closed": {"pull": pull(state="closed")},
    "draft": {"pull": pull(draft=True)},
    "fork head": {"pull": pull(head=head(repo="x/y"))},
    "base not main": {"pull": pull(base={"ref": "release"})},
    "not an agent branch": {"pull": pull(head=head(ref="fix/x"))},
    "opened by a person": {"pull": pull(user={"login": "fabiandistler", "type": "User"})},
    "opened by another bot": {"pull": pull(user={"login": "dependabot[bot]", "type": "Bot"})},
    "do-not-merge": {"pull": pull(labels=[{"name": "do-not-merge"}])},
    "body closes another issue": {"pull": pull(body="Closes #13")},
    "body closes nothing": {"pull": pull(body=None)},
    "issue unreadable": {"issue": None},
    "issue is ready-for-human": {"issue": issue(labels=[{"name": "ready-for-human"}])},
    "linked number is a pull request": {"issue": issue(pull_request={})},
    "review unavailable": {"review": review(status="unavailable")},
    "review skipped": {"review": review(status="skipped")},
    "verdict pass": {"review": review(verdict="pass")},
    "no findings": {"review": review(findings=[])},
    "findings missing": {"review": review(findings=None)},
    "review without head": {"review": review(head_sha="abc")},
    "context for another head": {"context": context(head_sha=OTHER_HEAD)},
    "context for another pull request": {"context": context(number=7)},
    "head moved on": {"pull": pull(head=head(sha=OTHER_HEAD))},
    "round already ran for this head": {"comments": [comment(marker(1, HEAD))]},
    "handoff already made for this head": {
        "comments": [
            comment(marker(1, OTHER_HEAD)),
            comment(marker(2, THIRD_HEAD)),
            comment(rework_policy.handoff_comment(HEAD)),
        ]
    },
}


@pytest.mark.parametrize("overrides", STOP_CASES.values(), ids=STOP_CASES.keys())
def test_each_gate_condition_stops(overrides):
    decision = rework_policy.decide(**facts(**overrides))
    assert decision.action == rework_policy.STOP
    assert decision.round is None and decision.issue is None
    assert decision.reason


def test_two_markers_and_a_new_non_pass_verdict_hand_off():
    comments = [comment(marker(1, OTHER_HEAD)), comment(marker(2, THIRD_HEAD))]
    decision = rework_policy.decide(**facts(comments=comments))
    assert (decision.action, decision.issue, decision.round) == (rework_policy.HANDOFF, ISSUE, None)
    assert decision.head_sha == HEAD


def test_markers_by_other_authors_do_not_count():
    quoted = [
        comment(marker(1, OTHER_HEAD), author="fabiandistler"),
        comment(marker(2, THIRD_HEAD), author="claude[bot]"),
        comment(marker(1, HEAD), author="someone"),
    ]
    decision = rework_policy.decide(**facts(comments=quoted))
    assert (decision.action, decision.round) == (rework_policy.PROCEED, 1)


def test_a_handoff_quoted_by_a_person_does_not_count():
    comments = [
        comment(marker(1, OTHER_HEAD)),
        comment(marker(2, THIRD_HEAD)),
        comment(rework_policy.handoff_comment(HEAD), author="someone"),
    ]
    assert rework_policy.decide(**facts(comments=comments)).action == rework_policy.HANDOFF


def test_the_round_comment_records_round_and_head():
    body = rework_policy.round_comment(2, HEAD)
    assert body.startswith(f"<!-- rework-round:2 head:{HEAD} -->\n")
    assert rework_policy.round_heads([comment(body)]) == [HEAD]


def test_a_bot_comment_without_a_marker_counts_no_round():
    bot_comments = [
        comment("<!-- pr-review-bot -->\n## Automated PR review"),
        comment("Rework round 1 of 2 starts for commit `aaaaaaa`."),
        comment(rework_policy.handoff_comment(HEAD)),
    ]
    assert rework_policy.round_heads(bot_comments) == []
    assert not rework_policy.handed_off(bot_comments[:2], HEAD)
    assert rework_policy.ROUND_MARKER.startswith("<!-- rework-round:")
    assert rework_policy.HANDOFF_MARKER.startswith("<!-- rework-handoff head:")


def test_the_handoff_comment_starts_with_its_marker():
    assert rework_policy.handoff_comment(HEAD).startswith(f"<!-- rework-handoff head:{HEAD} -->")


def test_the_cap_is_two_rounds():
    assert rework_policy.MAX_REWORK_ROUNDS == 2
