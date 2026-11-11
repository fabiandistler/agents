"""Tests for scripts/skill_audit_select.py: per-run rotation and the change window."""

import datetime
import json
import os
import subprocess
import sys
from collections import Counter
from itertools import pairwise
from pathlib import Path

import pytest
import skill_audit_select

SCRIPT = Path(__file__).resolve().parent / "skill_audit_select.py"


def scheduled_dates(first: datetime.date, count: int) -> list[datetime.date]:
    """The audit's schedule from `first` on: the 8th and the 22nd of each month."""
    dates = []
    year, month = first.year, first.month
    while len(dates) < count:
        for day in (8, 22):
            date = datetime.date(year, month, day)
            if date >= first and len(dates) < count:
                dates.append(date)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return dates


@pytest.mark.parametrize(
    "first",
    [
        datetime.date(2026, 11, 8),
        datetime.date(2026, 12, 22),
        # The ISO-week rotation gave only slices 0 and 2 from here on.
        datetime.date(2027, 2, 8),
        datetime.date(2027, 10, 22),
    ],
)
def test_eight_consecutive_runs_cover_every_slice_twice(first):
    dates = scheduled_dates(first, 8)
    slices = Counter(skill_audit_select.run_number(d) % 4 for d in dates)
    assert slices == {0: 2, 1: 2, 2: 2, 3: 2}


def test_consecutive_scheduled_runs_differ_by_one():
    dates = scheduled_dates(datetime.date(2026, 1, 8), 48)
    runs = [skill_audit_select.run_number(d) for d in dates]
    assert [b - a for a, b in pairwise(runs)] == [1] * 47


def test_default_window_covers_longest_gap_between_runs():
    dates = scheduled_dates(datetime.date(2026, 1, 8), 48)
    longest_gap = max((b - a).days for a, b in pairwise(dates))
    assert longest_gap == 17
    start, _ = skill_audit_select.change_window(datetime.date(2027, 2, 8), 17)
    # Covers the whole previous run day (2027-01-22), whatever time it ran.
    assert start == datetime.datetime(2027, 1, 22, tzinfo=datetime.timezone.utc)


def _git(repo: Path, *args: str, when: datetime.datetime | None = None) -> None:
    env = dict(os.environ)
    if when is not None:
        stamp = when.isoformat()
        env.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    subprocess.run(  # noqa: S603 -- test drives a scratch repo with argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git resolves from PATH.
        check=True,
        capture_output=True,
        env=env,
    )


def _commit_skill(repo: Path, name: str, when: datetime.datetime) -> None:
    skill = repo / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", f"add {name}", when=when)


@pytest.fixture
def audit_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "build_manifest.py").write_text("")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    run_day = datetime.datetime(2027, 2, 8, 12, tzinfo=datetime.timezone.utc)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init", when=run_day - datetime.timedelta(days=60))
    _commit_skill(repo, "changed-20-days-ago", run_day - datetime.timedelta(days=20))
    _commit_skill(repo, "changed-10-days-ago", run_day - datetime.timedelta(days=10))
    return repo


def _select(repo: Path, *args: str) -> dict:
    out = subprocess.run(  # noqa: S603 -- test runs the script under test with argv.
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.stdout)


def test_changed_window_spans_the_gap_since_the_previous_run(audit_repo):
    picked = _select(audit_repo, "--date", "2027-02-08")
    assert picked["changed"] == ["changed-10-days-ago"]
    assert picked["date"] == "2027-02-08"
    assert picked["run"] == skill_audit_select.run_number(datetime.date(2027, 2, 8))
    assert picked["slice"] == picked["run"] % 4
    assert "week" not in picked


def test_help_describes_twice_monthly_run_not_weekly():
    text = subprocess.run(  # noqa: S603 -- test runs the script under test with argv.
        [sys.executable, str(SCRIPT), "--help"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    docstring = skill_audit_select.__doc__
    assert docstring is not None
    for wording in (text, docstring):
        assert "weekly" not in wording.replace("twice-monthly", "")
        assert "seven days" not in wording
        assert "twice-monthly" in wording
        assert "17" in wording
