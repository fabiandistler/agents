"""The Rework gate's writes against a routed fake API: marker, findings file, handoff, stops."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import rework_gate
import rework_policy
from pr_github_client import FetchError, GitHubClient
from rework_testkit import (
    HEAD,
    ISSUE,
    ISSUE_PATH,
    OTHER_HEAD,
    OWN_RUN,
    PR,
    PR_COMMENTS,
    REPO,
    REVIEW_RUN,
    THIRD_HEAD,
    FakeGitHub,
    context,
    gate_job,
    marker,
    rest_comment,
    review,
)
from test_rework_policy import STOP_CASES


def gate(fake: FakeGitHub, tmp_path: Path, review_payload: dict | None = None, **kwargs):
    return rework_gate.decide_rework(
        cast(GitHubClient, fake),
        REPO,
        REVIEW_RUN,
        review_payload or review(),
        kwargs.pop("context_payload", context()),
        own_run_id=OWN_RUN,
        findings_path=tmp_path / "rework" / "findings.json",
        write=kwargs.pop("write", True),
    )


def test_proceed_posts_the_round_marker_and_writes_the_findings_file(tmp_path):
    fake = FakeGitHub()
    decision = gate(fake, tmp_path)
    assert (decision.action, decision.round) == (rework_policy.PROCEED, 1)
    assert fake.writes == [("POST", PR_COMMENTS, {"body": rework_policy.round_comment(1, HEAD)})]
    handed = json.loads((tmp_path / "rework" / "findings.json").read_text(encoding="utf-8"))
    assert handed["findings"] == review()["findings"]
    assert handed["head_sha"] == HEAD and handed["branch"] == f"agent/issue-{ISSUE}"
    assert (handed["pull_request"], handed["issue"], handed["round"]) == (PR, ISSUE, 1)


def test_a_dry_run_plans_without_writing(tmp_path):
    fake = FakeGitHub()
    assert gate(fake, tmp_path, write=False).action == rework_policy.PROCEED
    assert fake.writes == []


def _fake_for(overrides: dict) -> tuple[FakeGitHub, dict, dict]:
    fake = FakeGitHub()
    for name in ("run", "pull", "issue"):
        if name in overrides:
            setattr(fake, name, overrides[name])
    fake.comments = [
        rest_comment(entry["body"], entry["author"]) for entry in overrides.get("comments", [])
    ]
    return fake, overrides.get("review", review()), overrides.get("context", context())


GATE_STOPS = {key: value for key, value in STOP_CASES.items() if value.get("issue", 0) is not None}


@pytest.mark.parametrize("overrides", GATE_STOPS.values(), ids=GATE_STOPS.keys())
def test_each_stop_writes_nothing(tmp_path, overrides):
    fake, review_payload, context_payload = _fake_for(overrides)
    decision = gate(fake, tmp_path, review_payload, context_payload=context_payload)
    assert decision.action == rework_policy.STOP
    assert fake.writes == []
    assert not (tmp_path / "rework" / "findings.json").exists()


def test_a_verdict_without_findings_posts_no_marker(tmp_path):
    fake = FakeGitHub()
    decision = gate(fake, tmp_path, review(findings=[]))
    assert decision.action == rework_policy.STOP
    assert fake.writes == []


def test_another_working_rework_run_stops_the_gate_without_writes(tmp_path):
    fake = FakeGitHub()
    # An earlier run whose gate finished and whose model job still works.
    fake.jobs[OWN_RUN - 1] = [
        gate_job(status="completed", started="2026-11-14T09:00:00Z"),
        gate_job("rework", status="in_progress"),
    ]
    decision = gate(fake, tmp_path)
    assert (decision.action, decision.reason) == (
        rework_policy.STOP,
        "another rework run is working",
    )
    assert fake.writes == []


def test_a_finished_or_skipped_earlier_run_does_not_hold_capacity(tmp_path):
    fake = FakeGitHub()
    fake.jobs[OWN_RUN - 1] = [
        gate_job(status="completed", started="2026-11-14T09:00:00Z"),
        gate_job("rework", status="completed"),
    ]
    assert gate(fake, tmp_path).action == rework_policy.PROCEED


def _two_rounds() -> list[dict]:
    return [rest_comment(marker(1, OTHER_HEAD)), rest_comment(marker(2, THIRD_HEAD))]


def test_two_markers_hand_off_once_with_the_issue_swap(tmp_path):
    fake = FakeGitHub(comments=_two_rounds())
    decision = gate(fake, tmp_path)
    assert decision.action == rework_policy.HANDOFF
    assert fake.writes == [
        ("POST", f"{ISSUE_PATH}/labels", {"labels": ["ready-for-human"]}),
        ("DELETE", f"{ISSUE_PATH}/labels/ready-for-agent", None),
        ("POST", PR_COMMENTS, {"body": rework_policy.handoff_comment(HEAD)}),
    ]
    assert not (tmp_path / "rework" / "findings.json").exists()


def test_a_failed_issue_swap_leaves_no_handoff_marker_so_a_rerun_hands_off(tmp_path):
    # The handoff marker makes a repeat a no-op, so it may only land once the
    # issue waits for a person; otherwise the issue would keep ready-for-agent.
    fake = FakeGitHub(comments=_two_rounds(), failing_label_add=True)
    with pytest.raises(FetchError):
        gate(fake, tmp_path)
    assert [path for _, path, _ in fake.writes] == [f"{ISSUE_PATH}/labels"]
    fake.failing_label_add = False
    fake.writes.clear()
    assert gate(fake, tmp_path).action == rework_policy.HANDOFF
    assert ("POST", f"{ISSUE_PATH}/labels", {"labels": ["ready-for-human"]}) in fake.writes


def test_a_repeat_handoff_for_the_same_head_writes_nothing(tmp_path):
    fake = FakeGitHub(comments=_two_rounds())
    gate(fake, tmp_path)
    # Even with the label removed again by hand, the head's handoff marker holds.
    fake.writes.clear()
    decision = gate(fake, tmp_path)
    assert decision.action == rework_policy.STOP
    assert fake.writes == []


def test_a_handoff_tolerates_a_ready_label_that_is_already_gone(tmp_path):
    fake = FakeGitHub(comments=_two_rounds(), missing_label=True)
    assert gate(fake, tmp_path).action == rework_policy.HANDOFF


def test_a_second_run_for_the_same_head_writes_nothing(tmp_path):
    fake = FakeGitHub()
    gate(fake, tmp_path)
    fake.writes.clear()
    assert gate(fake, tmp_path).action == rework_policy.STOP
    assert fake.writes == []


def test_locate_takes_the_latest_successful_review_of_the_live_head():
    runs = [
        {"id": 5, "conclusion": "success"},
        {"id": 8, "conclusion": "success"},
        {"id": 6, "conclusion": "success"},
    ]
    fake = FakeGitHub(review_runs=runs)
    assert rework_gate.locate_run(cast(GitHubClient, fake), REPO, PR) == 8


def test_locate_skips_a_newer_failed_or_cancelled_review():
    runs = [
        {"id": 5, "conclusion": "success"},
        {"id": 8, "conclusion": "failure"},
        {"id": 9, "conclusion": "cancelled"},
    ]
    fake = FakeGitHub(review_runs=runs)
    assert rework_gate.locate_run(cast(GitHubClient, fake), REPO, PR) == 5


def test_cli_decide_reports_and_writes_outputs(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub()
    monkeypatch.setattr(rework_gate, "GitHubClient", lambda token: fake)
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_RUN_ID", str(OWN_RUN))
    (tmp_path / "review.json").write_text(json.dumps(review()), encoding="utf-8")
    (tmp_path / "context.json").write_text(json.dumps(context()), encoding="utf-8")
    outputs = tmp_path / "outputs"
    code = rework_gate.main(
        [
            "decide",
            "--repo", REPO,
            "--run-id", str(REVIEW_RUN),
            "--review", str(tmp_path / "review.json"),
            "--context", str(tmp_path / "context.json"),
            "--findings", str(tmp_path / "findings.json"),
            "--outputs", str(outputs),
            "--write",
        ]
    )  # fmt: skip
    assert code == rework_gate.EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert (report["action"], report["pull_request"], report["issue"], report["round"]) == (
        "proceed",
        PR,
        ISSUE,
        1,
    )
    lines = outputs.read_text(encoding="utf-8").splitlines()
    assert {"action=proceed", f"pull_request={PR}", f"issue={ISSUE}", "round=1"} <= set(lines)


def test_cli_stops_when_the_review_job_did_not_run(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub()
    monkeypatch.setattr(rework_gate, "GitHubClient", lambda token: fake)
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_RUN_ID", str(OWN_RUN))
    code = rework_gate.main(
        [
            "decide",
            "--repo", REPO,
            "--run-id", str(REVIEW_RUN),
            "--review", str(tmp_path / "absent.json"),
            "--context", str(tmp_path / "absent.json"),
            "--findings", str(tmp_path / "findings.json"),
        ]
    )  # fmt: skip
    assert code == rework_gate.EXIT_OK
    assert json.loads(capsys.readouterr().out)["action"] == "stop"
    assert fake.writes == []


def test_cli_fails_on_a_malformed_artifact_without_writes(monkeypatch, tmp_path, capsys):
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    fake = FakeGitHub()
    monkeypatch.setattr(rework_gate, "GitHubClient", lambda token: fake)
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_RUN_ID", str(OWN_RUN))
    code = rework_gate.main(
        [
            "decide",
            "--repo", REPO,
            "--run-id", str(REVIEW_RUN),
            "--review", str(tmp_path / "broken.json"),
            "--context", str(tmp_path / "absent.json"),
            "--findings", str(tmp_path / "findings.json"),
        ]
    )  # fmt: skip
    assert code == rework_gate.EXIT_FAILED
    assert json.loads(capsys.readouterr().out)["action"] == "failed"
    assert fake.writes == []


@pytest.mark.parametrize(
    "arguments",
    [["locate", "--repo", REPO], ["locate", "--repo", "bad", "--pr", "1"], ["decide"]],
)
def test_cli_rejects_bad_usage(arguments):
    with pytest.raises(SystemExit) as stopped:
        rework_gate.main(arguments)
    assert stopped.value.code == rework_gate.EXIT_USAGE
