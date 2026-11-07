"""Tests for the command line of scripts/pr_publish.py, offline and write paths."""

from __future__ import annotations

import json

import pr_github
import pr_publish
import pytest
from pr_publish_testkit import (
    COMMENTS_PATH,
    FakeGitHub,
    live_args,
    make_assessment,
    make_context,
    make_review,
    offline_args,
    run_cli,
    write_calls,
    write_json,
)

# --- CLI ---------------------------------------------------------------------


def test_cli_prints_the_plan_json(tmp_path):
    run = run_cli(*offline_args(tmp_path))

    assert run.returncode == 0, run.stderr
    assert run.stderr == ""
    plan = json.loads(run.stdout)
    assert plan["status"] == "planned"
    assert plan["number"] == 42
    assert plan["head_sha"] == "abc123"
    assert [action["kind"] for action in plan["actions"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]


def test_cli_prints_an_aborted_plan_and_still_exits_zero(tmp_path):
    assessment = write_json(tmp_path, "assessment.json", make_assessment(head_sha="stale"))
    run = run_cli(
        "--context",
        str(write_json(tmp_path, "context.json", make_context())),
        "--assessment",
        str(assessment),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    )

    assert run.returncode == 0, run.stderr
    plan = json.loads(run.stdout)
    assert plan["status"] == "aborted"
    assert plan["actions"] == []


def test_cli_help_is_short_and_documents_exit_codes():
    run = run_cli("--help")

    assert run.returncode == 0
    assert run.stderr == ""
    assert len(run.stdout.splitlines()) < 25
    assert "usage:" in run.stdout
    assert "exit:" in run.stdout
    assert "1 a write action failed" in run.stdout
    assert "--write" in run.stdout
    assert run.stdout.count("python3 scripts/pr_publish.py") == 2


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--live"],
        ["--assessment", "a.json", "--review", "r.json"],
        ["--context", "c.json", "--assessment", "a.json"],
        ["--context", "c.json", "--review", "r.json"],
        ["--context", "c.json", "--live", "--repo", "o/r", "--pr", "1", "--assessment", "a"],
        ["--live", "--repo", "o/r", "--assessment", "a", "--review", "r"],
        ["--live", "--pr", "1", "--assessment", "a", "--review", "r"],
        ["--context", "c.json", "--pr", "1", "--assessment", "a", "--review", "r"],
        ["--context", "c.json", "--assessment", "a", "--review", "r", "--unknown"],
        ["--context", "c.json", "--assessment", "a", "--review", "r", "--live"],
    ],
)
def test_cli_usage_errors_exit_two(arguments):
    run = run_cli(*arguments)

    assert run.returncode == 2
    assert run.stdout == ""
    assert "usage:" in run.stderr


def test_cli_unreadable_context_exits_three(tmp_path):
    run = run_cli(
        "--context",
        str(tmp_path / "missing.json"),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    )

    assert run.returncode == 3
    assert "--context" in run.stderr


def test_cli_invalid_json_exits_three(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    run = run_cli(
        "--context",
        str(bad),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    )

    assert run.returncode == 3


def test_cli_malformed_artifact_exits_three(tmp_path):
    run = run_cli(
        "--context",
        str(write_json(tmp_path, "context.json", make_context())),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", {"schema_version": 1})),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    )

    assert run.returncode == 3
    assert "--assessment" in run.stderr or "assessment" in run.stderr


def test_cli_live_fetch_failure_exits_four(monkeypatch, tmp_path):
    def fail(repo, number, token=None):
        raise pr_github.FetchError("boom")

    monkeypatch.setattr(pr_publish.pr_github, "fetch_context", fail)

    code = pr_publish.main(
        [
            "--live",
            "--repo",
            "fabiandistler/agents",
            "--pr",
            "42",
            "--assessment",
            str(write_json(tmp_path, "assessment.json", make_assessment())),
            "--review",
            str(write_json(tmp_path, "review.json", make_review())),
        ]
    )

    assert code == 4


def test_cli_live_plan_uses_the_fetched_context(monkeypatch, tmp_path, capsys):
    fetched = make_context(head_sha="fresh456", labels=["risk:high"])

    def fetch(repo, number, token=None):
        assert (repo, number) == ("fabiandistler/agents", 42)
        return fetched

    monkeypatch.setattr(pr_publish.pr_github, "fetch_context", fetch)
    assessment = write_json(tmp_path, "assessment.json", make_assessment(head_sha="fresh456"))

    code = pr_publish.main(
        [
            "--live",
            "--repo",
            "fabiandistler/agents",
            "--pr",
            "42",
            "--assessment",
            str(assessment),
            "--review",
            str(write_json(tmp_path, "review.json", make_review(head_sha="fresh456"))),
        ]
    )

    assert code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["head_sha"] == "fresh456"
    assert plan["status"] == "planned"


def test_cli_reads_auto_merge_from_the_environment(tmp_path):
    args = offline_args(tmp_path)

    enabled = run_cli(*args, PR_AUTO_MERGE="true")
    assert "enable_auto_merge" in enabled.stdout

    disabled = run_cli(*args, PR_AUTO_MERGE="TRUE")
    assert "enable_auto_merge" not in disabled.stdout


# --- CLI write path ----------------------------------------------------------


def test_cli_write_requires_live(tmp_path):
    code = pr_publish.main([*offline_args(tmp_path), "--write"])

    assert code == 2


def test_cli_write_outside_github_actions_exits_five(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    code = pr_publish.main([*live_args(tmp_path), "--write"])

    assert code == 5


def test_cli_write_inside_actions_without_a_token_exits_four(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    code = pr_publish.main([*live_args(tmp_path), "--write"])

    assert code == 4


def test_cli_write_applies_the_plan_and_prints_the_results(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(["abc123", "abc123"])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_publish.main([*live_args(tmp_path), "--write"], client=fake)

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["ok"] is True
    assert payload["plan"]["status"] == "planned"
    assert [result["kind"] for result in payload["results"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]


def test_cli_write_exits_one_when_an_action_failed(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(["abc123", "abc123"])
    fake.fail_paths.add(COMMENTS_PATH)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_publish.main([*live_args(tmp_path), "--write"], client=fake)

    assert code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert [result["kind"] for result in payload["results"]] == [
        "set_labels",
        "upsert_comment",
        "request_reviewer",
    ]
    failed = [result for result in payload["results"] if not result["ok"]]
    assert [result["kind"] for result in failed] == ["upsert_comment"]
    assert failed[0]["detail"], "a failed action must say what went wrong"


def test_cli_write_prints_an_aborted_plan_when_the_head_changed(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(["abc123", "def456"])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    code = pr_publish.main([*live_args(tmp_path), "--write"], client=fake)

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "aborted"
    assert payload["abort_reason"] == "head_sha_changed"
    assert payload["actions"] == []
    assert "results" not in payload
    assert write_calls(fake) == []
