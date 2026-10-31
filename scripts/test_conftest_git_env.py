"""Regression test: tests that set up git repos must not reach the repo a hook runs in."""

import site
import subprocess
from pathlib import Path

ROOT_CONFTEST = Path(__file__).resolve().parent.parent / "conftest.py"
# Read at import, before pytester points HOME at its tmp dir: a pytest
# installed with `pip --user` lives under the real HOME.
OUTER_USER_BASE = site.getuserbase()

FIXTURE_STYLE_GIT_SETUP = """
import subprocess

def test_sets_up_a_scratch_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True
    )
"""


def _config_listing(git_dir: Path) -> str:
    return subprocess.run(  # noqa: S603 -- test reads a scratch repo with argv; no shell.
        [  # noqa: S607 -- Git intentionally resolves from PATH.
            "git",
            "config",
            "--file",
            str(git_dir / "config"),
            "--list",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _run_inner_session(pytester, monkeypatch, decoy_git_dir: Path):
    pytester.makepyfile(test_scratch_repo=FIXTURE_STYLE_GIT_SETUP)
    # What a pre-push hook in a linked worktree hands its children.
    monkeypatch.setenv("GIT_DIR", str(decoy_git_dir))
    # Without it the child looks for its pytest under pytester's HOME.
    monkeypatch.setenv("PYTHONUSERBASE", OUTER_USER_BASE)
    return pytester.runpytest_subprocess("-p", "no:cacheprovider")


def _make_decoy(tmp_path: Path) -> Path:
    decoy = tmp_path / "decoy"
    subprocess.run(  # noqa: S603 -- test initializes a temporary repository with argv.
        [  # noqa: S607 -- Git intentionally resolves from PATH.
            "git",
            "init",
            "-q",
            str(decoy),
        ],
        check=True,
    )
    return decoy / ".git"


def test_root_conftest_keeps_scratch_repo_setup_off_the_hook_repo(pytester, monkeypatch, tmp_path):
    decoy_git_dir = _make_decoy(tmp_path)
    before = _config_listing(decoy_git_dir)
    pytester.makeconftest(ROOT_CONFTEST.read_text())

    _run_inner_session(pytester, monkeypatch, decoy_git_dir).assert_outcomes(passed=1)

    assert _config_listing(decoy_git_dir) == before


def test_without_root_conftest_the_decoy_is_damaged(pytester, monkeypatch, tmp_path):
    # Proves the scenario above can go red, so its pass is not vacuous.
    decoy_git_dir = _make_decoy(tmp_path)
    before = _config_listing(decoy_git_dir)

    _run_inner_session(pytester, monkeypatch, decoy_git_dir).assert_outcomes(passed=1)

    assert _config_listing(decoy_git_dir) != before
