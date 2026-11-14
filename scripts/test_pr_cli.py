"""Tests for the exit-code table every pr_* command line shares (scripts/pr_cli.py)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pr_cli
import pytest

SCRIPTS = Path(__file__).resolve().parent
CLIS = (
    "pr_github.py",
    "pr_risk.py",
    "pr_review.py",
    "pr_publish.py",
    "pr_apply.py",
    "pr_skip.py",
)


def test_every_failure_class_has_its_own_code():
    assert pr_cli.EXIT_CODES == {
        0: "success",
        1: "a write action failed",
        2: "usage",
        3: "bad input file",
        4: "GitHub fetch failed",
        5: "missing GITHUB_TOKEN",
        6: "output file not writable",
        7: "--write outside GitHub Actions",
        8: "review unavailable",
    }


def documented_exits(help_text: str) -> dict[int, str]:
    """Parse the `exit: 0 success | 2 usage | ...` block at the end of a --help text."""
    lines = help_text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.lower().startswith("exit:"))
    block = " ".join(line.strip() for line in lines[start:])[len("exit:") :]
    exits: dict[int, str] = {}
    for entry in block.split("|"):
        code, _, meaning = entry.strip().partition(" ")
        exits[int(code)] = meaning.strip()
    return exits


@pytest.mark.parametrize(
    ("script", "codes"),
    [
        ("pr_github.py", {0, 2, 4, 5, 6}),
        ("pr_risk.py", {0, 2, 3, 4, 5, 6}),
        ("pr_review.py", {0, 2, 3, 6}),
        ("pr_publish.py", {0, 1, 2, 3, 4, 5, 6, 7, 8}),
        ("pr_apply.py", {0, 1, 2, 3, 5, 7}),
        ("pr_skip.py", {0, 2, 3}),
    ],
)
def test_every_cli_documents_its_codes_with_the_shared_meanings(script, codes):
    run = subprocess.run(  # noqa: S603 -- fixed interpreter and script path, no shell
        [sys.executable, str(SCRIPTS / script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0
    assert len(run.stdout.splitlines()) <= 25
    assert documented_exits(run.stdout) == {code: pr_cli.EXIT_CODES[code] for code in codes}
