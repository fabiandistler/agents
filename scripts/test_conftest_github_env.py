"""Regression test: tests must not inherit the GitHub Actions runner's environment."""

import site
from pathlib import Path

ROOT_CONFTEST = Path(__file__).resolve().parent.parent / "conftest.py"
# Read at import, before pytester points HOME at its tmp dir: a pytest
# installed with `pip --user` lives under the real HOME.
OUTER_USER_BASE = site.getuserbase()

READS_THE_RUNNER_ENV = """
import os

def test_sees_no_runner_env():
    assert "GITHUB_ACTIONS" not in os.environ
    assert "GITHUB_WORKFLOW_REF" not in os.environ

def test_sees_what_it_sets(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert os.environ["GITHUB_ACTIONS"] == "true"
"""


def _run_inner_session(pytester, monkeypatch):
    pytester.makepyfile(test_runner_env=READS_THE_RUNNER_ENV)
    # What ci.yml exports to every step.
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv(
        "GITHUB_WORKFLOW_REF", "fabiandistler/agents/.github/workflows/ci.yml@refs/heads/main"
    )
    # Without it the child looks for its pytest under pytester's HOME.
    monkeypatch.setenv("PYTHONUSERBASE", OUTER_USER_BASE)
    return pytester.runpytest_subprocess("-p", "no:cacheprovider")


def test_root_conftest_unsets_runner_vars_unless_the_test_sets_them(pytester, monkeypatch):
    pytester.makeconftest(ROOT_CONFTEST.read_text())

    _run_inner_session(pytester, monkeypatch).assert_outcomes(passed=2)


def test_without_root_conftest_the_runner_vars_leak(pytester, monkeypatch):
    # Proves the scenario above can go red, so its pass is not vacuous.
    _run_inner_session(pytester, monkeypatch).assert_outcomes(passed=1, failed=1)
