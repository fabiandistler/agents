"""Shared pytest setup for every test under scripts/ and skills/."""

from __future__ import annotations

import os
import subprocess

import pytest

pytest_plugins = ["pytester"]

# Git exports these to hooks. From a linked worktree GIT_DIR is absolute, so a
# test's `git init` / `git config` in a tmp dir would act on the real repo
# instead (core.bare=true, a test user.name in the shared .git/config).
GIT_REPO_LOCATING_VARS = (
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)

# The Actions runner exports these, and the scripts read them (GITHUB_ACTIONS
# opens their write paths), so a test inherited whichever workflow ran it.
# A test that needs one sets it explicitly.
GITHUB_RUNNER_VARS = (
    "GITHUB_ACTIONS",
    "GITHUB_WORKFLOW_REF",
    "GITHUB_RUN_ID",
    "GITHUB_REPOSITORY",
    "GITHUB_EVENT_NAME",
    "GITHUB_EVENT_PATH",
    "GITHUB_STEP_SUMMARY",
    "GITHUB_OUTPUT",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "ACTIONS_READ_TOKEN",
    "RUNNER_TEMP",
)


def pytest_configure(config):
    # Process-wide before collection, not a function-scoped fixture, so
    # session fixtures and import-time code are covered too.
    for var in (*GIT_REPO_LOCATING_VARS, *GITHUB_RUNNER_VARS):
        os.environ.pop(var, None)


@pytest.fixture
def assert_exit_cause(capsys):
    """Assert that a failed run exited with ``code`` and wrote its cause to stderr.

    instructions/on-demand/85-agent-scripts.md asks every non-zero exit to name
    its cause on stderr, so a job log without the JSON output still says why
    (#1029). ``run`` is a CompletedProcess, or the int a script's ``main()``
    returned, whose output this reads from capsys. Returns ``(stdout, stderr)``
    for the test's own checks, since capsys hands each output out only once.
    """

    def check(run: subprocess.CompletedProcess | int, code: int) -> tuple[str, str]:
        if isinstance(run, int):
            returncode = run
            stdout, stderr = capsys.readouterr()
        else:
            returncode, stdout, stderr = run.returncode, run.stdout, run.stderr
        assert returncode == code, f"exit code {returncode}, expected {code}"
        assert stderr.strip(), f"exit code {code} wrote no cause to stderr"
        return stdout, stderr

    return check
