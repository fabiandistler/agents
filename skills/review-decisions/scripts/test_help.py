"""The command-line contract every review-decisions script shares.

Run from the repo root with: uv run --with pytest pytest skills/review-decisions/scripts/
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = ["batches.py", "gather_inputs.py", "protocol.py", "skim_proof.py"]


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 -- test invokes a sibling script with argv, no shell.
        [sys.executable, str(Path(__file__).with_name(script)), *args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("script", SCRIPTS)
def test_help_fits_in_25_lines_with_exit_codes_and_examples(script):
    proc = run(script, "--help")

    assert proc.returncode == 0
    assert len(proc.stdout.splitlines()) <= 25
    assert "exit" in proc.stdout
    assert "example" in proc.stdout


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_usage_error_exits_1_and_names_the_script(script):
    proc = run(script, "--no-such-flag")

    assert proc.returncode == 1
    assert proc.stderr.startswith("usage:")
    assert f"{script}:" in proc.stderr
