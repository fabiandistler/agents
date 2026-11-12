"""Tests for the publish step summary (scripts/pr_summary.py).

The summary is read on the workflow run page: it must show the decision, what
the review covered, and the labels the run actually wrote, not only planned.
"""

from __future__ import annotations

import pr_github_client
import pr_plan
import pr_publish
import pr_summary
from pr_publish_testkit import (
    REPO,
    FakeGitHub,
    live_args,
    make_assessment,
    make_context,
    make_review,
    run_cli,
    write_json,
)


def test_a_dry_run_shows_the_decision_and_the_planned_labels():
    plan = pr_plan.plan_publish(make_context(), make_assessment(), make_review())

    summary = pr_summary.render_summary(plan, make_review())

    assert "- risk: low" in summary
    assert "- verdict: pass" in summary
    assert "- auto-merge: off" in summary
    assert "- labels planned (dry run, nothing written): +risk:low, +review:pass" in summary
    assert "labels applied" not in summary


def test_the_review_coverage_stands_in_for_a_confidence_value():
    full = pr_summary.render_summary(
        pr_plan.plan_publish(make_context(), make_assessment(), make_review()), make_review()
    )
    partial_review = make_review(partial=True)
    partial = pr_summary.render_summary(
        pr_plan.plan_publish(make_context(), make_assessment(), partial_review), partial_review
    )

    assert "- confidence: full review of the diff" in full
    assert "- confidence: partial review, the input was truncated" in partial


def test_an_unavailable_review_has_no_confidence():
    review = make_review(status="unavailable", risk=None, verdict=None, findings=[])
    plan = pr_plan.plan_publish(make_context(), make_assessment(), review)

    summary = pr_summary.render_summary(plan, review)

    assert "- confidence: none, the review is unavailable" in summary


def test_a_write_shows_the_labels_it_applied_and_each_action():
    fake = FakeGitHub(["abc1234", "abc1234"], labels=["risk:high"])
    fake.fail_paths = {f"/repos/{REPO}/issues/42/labels/risk%3Ahigh"}
    payload = pr_publish.publish_live(
        REPO, 42, make_assessment(), make_review(), write=True, client=fake
    )

    summary = pr_summary.render_summary(payload, make_review())

    assert "- labels applied: +risk:low, +review:pass" in summary
    assert "risk:high" not in summary.split("- labels applied:")[1].splitlines()[0]
    assert "- set_labels: failed" in summary
    assert "- upsert_comment: ok" in summary


def test_an_aborted_plan_names_its_reason():
    plan = pr_plan.plan_publish(make_context(), make_assessment(head_sha="old"), make_review())

    summary = pr_summary.render_summary(plan, make_review())

    assert "- aborted: head_sha_changed" in summary
    assert "labels" not in summary.split("```")[0]


def test_the_cli_appends_the_summary_to_the_given_file(tmp_path):
    summary_file = tmp_path / "summary.md"
    summary_file.write_text("earlier step\n", encoding="utf-8")
    arguments = [
        "--context",
        str(write_json(tmp_path, "context.json", make_context())),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
        "--summary",
        str(summary_file),
    ]

    result = run_cli(*arguments)

    assert result.returncode == 0, result.stderr
    text = summary_file.read_text(encoding="utf-8")
    assert text.startswith("earlier step\n")
    assert "### PR review decision" in text


def test_the_cli_reports_an_unwritable_summary_with_its_own_exit_code(tmp_path):
    arguments = [
        "--context",
        str(write_json(tmp_path, "context.json", make_context())),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
        "--summary",
        str(tmp_path / "missing-dir" / "summary.md"),
    ]

    result = run_cli(*arguments)

    assert result.returncode == 6
    assert '"status": "planned"' in result.stdout, "the plan is still printed"


def test_a_failed_live_fetch_still_leaves_a_summary(monkeypatch, tmp_path):
    def fail(*_arguments, **_keywords):
        raise pr_github_client.FetchError("GitHub API returned 502 for /repos/o/r/pulls/42")

    monkeypatch.setattr(pr_publish.pr_github, "fetch_context", fail)
    summary_file = tmp_path / "summary.md"

    status = pr_publish.main([*live_args(tmp_path), "--summary", str(summary_file)])

    assert status == 4
    assert "- live fetch failed: GitHub API returned 502" in summary_file.read_text("utf-8")
