"""Tests for scripts/pr_skip.py, the head-branch skip of the PR review."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pr_skip
import pytest

SCRIPT = Path(__file__).resolve().parent / "pr_skip.py"


@pytest.mark.parametrize(
    ("prefixes", "expected"),
    [
        ("", ()),
        ("maintenance/", ("maintenance/",)),
        (" maintenance/ , release/,, ", ("maintenance/", "release/")),
    ],
)
def test_prefixes_come_from_the_environment(monkeypatch, prefixes, expected):
    monkeypatch.setenv(pr_skip.PREFIXES_ENV, prefixes)

    assert pr_skip.prefixes_from_env() == expected


def test_no_environment_means_no_prefixes(monkeypatch):
    monkeypatch.delenv(pr_skip.PREFIXES_ENV, raising=False)

    assert pr_skip.prefixes_from_env() == ()


@pytest.mark.parametrize(
    ("context", "skipped"),
    [
        ({"head_ref": "maintenance/weekly"}, True),
        ({"head_ref": "agent/issue-1"}, False),
        ({"head_ref": "my-maintenance/x"}, False),
        ({"head_ref": ""}, False),
        ({}, False),
        ({"head_ref": None}, False),
    ],
)
def test_only_a_head_branch_with_a_prefix_is_skipped(context, skipped):
    assert pr_skip.head_skipped(context, ("maintenance/",)) is skipped


def test_no_prefixes_skip_nothing():
    assert pr_skip.head_skipped({"head_ref": "maintenance/weekly"}, ()) is False


def run_cli(*args: str, prefixes: str | None = None) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if key != pr_skip.PREFIXES_ENV}
    if prefixes is not None:
        env[pr_skip.PREFIXES_ENV] = prefixes
    return subprocess.run(  # noqa: S603 -- the test runs its own script with argv, no shell
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.parametrize(
    ("prefixes", "expected"),
    [("maintenance/", "skip=true"), ("release/", "skip=false"), (None, "skip=false")],
)
def test_cli_prints_the_github_output_line(tmp_path, prefixes, expected):
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"head_ref": "maintenance/weekly"}), encoding="utf-8")

    run = run_cli("--context", str(context), prefixes=prefixes)

    assert run.returncode == 0, run.stderr
    assert run.stdout == f"{expected}\n"


def test_cli_without_a_context_is_a_usage_error():
    run = run_cli()

    assert run.returncode == 2
    assert run.stdout == ""


def test_cli_with_an_unreadable_context_exits_three(tmp_path):
    run = run_cli("--context", str(tmp_path / "missing.json"))

    assert run.returncode == 3
    assert run.stdout == ""
