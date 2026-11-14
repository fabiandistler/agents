"""Tests for the publisher options a calling repository sets (#792).

The reusable workflow `factory-pr-review.yml` passes them from its inputs:
`skip_head_prefixes` (PR_SKIP_HEAD_PREFIXES), `fail_on_unavailable`
(--fail-on-unavailable) and `quiet_logs` (--quiet). Each is tested against the
fake GitHub, so a skipped pull request is shown to get no write at all.
"""

from __future__ import annotations

import json

import pr_cli
import pr_plan
import pr_publish
import pr_summary
import pytest
from pr_publish_testkit import (
    ACTIVE_AUTO_MERGE,
    REPO,
    FakeGitHub,
    live_args,
    make_assessment,
    make_context,
    make_review,
    run_cli,
    write_calls,
    write_json,
)

# The fake pull request's head branch is `fix/x`.
SKIPPING = "maintenance/, fix/"
UNAVAILABLE = {"status": "unavailable", "risk": "high", "verdict": None, "findings": []}


@pytest.fixture
def in_actions(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")


def args_with_review(tmp_path, **review: object) -> list[str]:
    arguments = live_args(tmp_path)
    review_path = write_json(tmp_path, "review.json", make_review(**review))
    arguments[arguments.index("--review") + 1] = str(review_path)
    return arguments


# --- skip_head_prefixes -------------------------------------------------------


def test_a_skipped_head_gets_no_labels_no_comment_and_no_status(
    monkeypatch, tmp_path, in_actions, capsys
):
    monkeypatch.setenv("PR_SKIP_HEAD_PREFIXES", SKIPPING)
    fake = FakeGitHub(["abc1234", "abc1234"])

    code = pr_publish.main([*live_args(tmp_path), "--write"], client=fake)

    assert code == pr_cli.EXIT_OK
    plan = json.loads(capsys.readouterr().out)
    assert plan["status"] == "aborted"
    assert plan["abort_reason"] == "head_skipped"
    assert plan["actions"] == []
    assert write_calls(fake) == []


def test_a_skipped_head_gets_no_hold_write(monkeypatch, in_actions, capsys):
    monkeypatch.setenv("PR_SKIP_HEAD_PREFIXES", SKIPPING)
    fake = FakeGitHub(["abc1234"], labels=["auto-merge:bot"])
    fake.pull_overrides = {"auto_merge": ACTIVE_AUTO_MERGE}

    code = pr_publish.main(
        ["--hold", "--live", "--repo", REPO, "--pr", "42", "--write"], client=fake
    )

    assert code == pr_cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["abort_reason"] == "head_skipped"
    assert write_calls(fake) == []


def test_a_skipped_head_never_fails_the_run_on_an_unavailable_review(
    monkeypatch, tmp_path, in_actions
):
    monkeypatch.setenv("PR_SKIP_HEAD_PREFIXES", SKIPPING)
    fake = FakeGitHub(["abc1234", "abc1234"])

    arguments = [*args_with_review(tmp_path, **UNAVAILABLE), "--write", "--fail-on-unavailable"]

    assert pr_publish.main(arguments, client=fake) == pr_cli.EXIT_OK


@pytest.mark.parametrize("prefixes", [None, "", " , ", "maintenance/", "x/"])
def test_other_heads_are_published_as_before(monkeypatch, tmp_path, in_actions, prefixes):
    if prefixes is None:
        monkeypatch.delenv("PR_SKIP_HEAD_PREFIXES", raising=False)
    else:
        monkeypatch.setenv("PR_SKIP_HEAD_PREFIXES", prefixes)
    fake = FakeGitHub(["abc1234", "abc1234"])

    assert pr_publish.main([*live_args(tmp_path), "--write"], client=fake) == pr_cli.EXIT_OK
    assert write_calls(fake), "a head outside the prefixes is published"


def test_the_offline_plan_honours_the_prefixes_too():
    plan = pr_plan.plan_publish(
        make_context(head_ref="maintenance/weekly"),
        make_assessment(),
        make_review(),
        skip_prefixes=("maintenance/",),
    )

    assert (plan["status"], plan["abort_reason"]) == ("aborted", "head_skipped")


# --- fail_on_unavailable ------------------------------------------------------


def test_an_unavailable_review_is_published_and_then_fails_the_run(tmp_path, in_actions, capsys):
    fake = FakeGitHub(["abc1234", "abc1234"])
    arguments = [*args_with_review(tmp_path, **UNAVAILABLE), "--write", "--fail-on-unavailable"]

    code = pr_publish.main(arguments, client=fake)

    assert code == pr_cli.EXIT_REVIEW_UNAVAILABLE
    captured = capsys.readouterr()
    assert json.loads(captured.out)["ok"] is True
    assert "review:unavailable" in json.dumps(write_calls(fake))
    assert "--fail-on-unavailable" in captured.err


def test_without_the_flag_an_unavailable_review_stays_green(tmp_path, in_actions):
    fake = FakeGitHub(["abc1234", "abc1234"])
    arguments = [*args_with_review(tmp_path, **UNAVAILABLE), "--write"]

    assert pr_publish.main(arguments, client=fake) == pr_cli.EXIT_OK


@pytest.mark.parametrize(
    "review",
    [{}, {"status": "skipped", "risk": None, "verdict": None, "findings": []}],
    ids=["ok", "skipped draft or fork"],
)
def test_the_flag_fails_only_an_unavailable_review(tmp_path, in_actions, review):
    fake = FakeGitHub(["abc1234", "abc1234"])
    arguments = [*args_with_review(tmp_path, **review), "--write", "--fail-on-unavailable"]

    assert pr_publish.main(arguments, client=fake) == pr_cli.EXIT_OK


def test_a_dry_run_fails_on_an_unavailable_review_too(tmp_path):
    fake = FakeGitHub(["abc1234"])
    arguments = [*args_with_review(tmp_path, **UNAVAILABLE), "--fail-on-unavailable"]

    assert pr_publish.main(arguments, client=fake) == pr_cli.EXIT_REVIEW_UNAVAILABLE
    assert write_calls(fake) == []


def test_a_failed_write_keeps_its_own_exit_code(tmp_path, in_actions):
    fake = FakeGitHub(["abc1234", "abc1234"])
    fake.fail_paths.add(f"/repos/{REPO}/issues/42/comments")
    arguments = [*args_with_review(tmp_path, **UNAVAILABLE), "--write", "--fail-on-unavailable"]

    assert pr_publish.main(arguments, client=fake) == pr_cli.EXIT_ACTION_FAILED


# --- quiet_logs ---------------------------------------------------------------

# Text only the model writes: the review summary and a finding.
MODEL_TEXT = ("The documentation change is accurate", "The heading could name the command")


def test_the_quiet_summary_holds_no_model_text_and_no_json():
    review = make_review()
    plan = pr_plan.plan_publish(make_context(), make_assessment(), review)

    loud = pr_summary.render_summary(plan, review)
    quiet = pr_summary.render_summary(plan, review, quiet=True)

    assert all(text in loud for text in MODEL_TEXT), "the fixture must carry model text"
    assert not any(text in quiet for text in MODEL_TEXT)
    assert "```json" not in quiet
    assert "- verdict: pass" in quiet


def test_quiet_writes_a_summary_without_model_text(tmp_path, in_actions):
    fake = FakeGitHub(["abc1234", "abc1234"])
    summary = tmp_path / "summary.md"

    code = pr_publish.main(
        [*live_args(tmp_path), "--write", "--summary", str(summary), "--quiet"], client=fake
    )

    assert code == pr_cli.EXIT_OK
    text = summary.read_text(encoding="utf-8")
    assert "- labels applied: +risk:low, +review:pass" in text
    assert not any(model_text in text for model_text in MODEL_TEXT)


@pytest.mark.parametrize("flag", ["--quiet", "--fail-on-unavailable"])
def test_the_hold_takes_neither_option(flag):
    run = run_cli("--hold", "--live", "--repo", REPO, "--pr", "1", flag)

    assert run.returncode == pr_cli.EXIT_USAGE
    assert run.stdout == ""
