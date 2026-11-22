"""Tests for scripts/skill_audit_gate.py: one audit per half-month, manual runs always."""

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest
import skill_audit_gate
from pr_github_client import FetchError, Response

SCRIPT = Path(__file__).resolve().parent / "skill_audit_gate.py"
REPO = "fabiandistler/agents"
RUNS_PATH = f"/repos/{REPO}/actions/workflows/skill-audit.yml/runs"


class FakeRuns:
    """Answers the runs query with a fixed total and records what was asked."""

    def __init__(self, total: object) -> None:
        self.total = total
        self.calls: list[tuple[str, dict]] = []

    def get(self, path, params=None, accept=None):
        self.calls.append((path, dict(params or {})))
        return Response(status=200, body=json.dumps({"total_count": self.total}).encode())


def test_first_scheduled_run_of_the_half_month_is_due():
    client = FakeRuns(0)
    decision = skill_audit_gate.decide(client, REPO, "schedule", datetime.date(2026, 11, 22))
    assert decision.due is True
    assert decision.since == "2026-11-15"
    ((path, params),) = client.calls
    assert path == RUNS_PATH
    assert params["status"] == "success"
    assert params["created"] == ">=2026-11-15"


@pytest.mark.parametrize("today", [datetime.date(2026, 11, 23), datetime.date(2026, 11, 24)])
def test_catch_up_day_after_a_successful_run_is_not_due(today):
    decision = skill_audit_gate.decide(FakeRuns(1), REPO, "schedule", today)
    assert decision.due is False
    assert decision.successful_runs == 1


def test_first_half_counts_from_the_first_of_the_month():
    client = FakeRuns(0)
    decision = skill_audit_gate.decide(client, REPO, "schedule", datetime.date(2026, 12, 10))
    assert decision.since == "2026-12-01"
    assert client.calls[0][1]["created"] == ">=2026-12-01"


def test_manual_run_is_due_without_asking_github():
    client = FakeRuns(5)
    decision = skill_audit_gate.decide(
        client, REPO, "workflow_dispatch", datetime.date(2026, 11, 22)
    )
    assert decision.due is True
    assert client.calls == []


def test_unexpected_payload_raises():
    with pytest.raises(FetchError):
        skill_audit_gate.decide(FakeRuns("many"), REPO, "schedule", datetime.date(2026, 11, 22))


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 -- test runs the script under test with argv.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_cli_without_token_exits_3():
    result = _run("--repo", REPO, "--event", "schedule", env={"PATH": "/usr/bin:/bin"})
    assert result.returncode == skill_audit_gate.EXIT_MISSING_TOKEN
    assert "GITHUB_TOKEN" in result.stderr


def test_cli_rejects_a_bad_repo():
    result = _run("--repo", "not a repo", "--event", "schedule")
    assert result.returncode == skill_audit_gate.EXIT_USAGE


def test_help_stays_short():
    result = _run("--help")
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) <= 25
