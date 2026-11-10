"""Fixture tests for release_state.py.

Run from the repo root with: uv run --with pytest pytest skills/release-pr/scripts/
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("release_state.py")

PYPROJECT = """\
[project]
name = "demo"
version = "{version}"
"""

CHANGELOG = """\
# Changelog

All notable changes to this project are documented here.

## [{heading}] - 2026-09-19

{body}

[{heading}]: https://example.com/compare/v1.3.0...v1.4.0
"""

DESCRIPTION = """\
Package: demo
Version: {version}
Title: Demo
Description: Demo package.
License: MIT
"""

NEWS = """\
# demo {heading}

{body}
"""

BULLET = "- Something (#1).\n"


def git(repo, *args):
    subprocess.run(  # noqa: S603 -- fixture Git commands use argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        check=True,
        capture_output=True,
        text=True,
    )


def make_repo(base, files, tag=None):
    base.mkdir(parents=True, exist_ok=True)
    git(base, "init", "-q")
    git(base, "config", "user.email", "test@example.com")
    git(base, "config", "user.name", "Test")
    for name, content in files.items():
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(base, "add", "-A")
    git(base, "-c", "commit.gpgsign=false", "commit", "-qm", "init")
    if tag:
        git(base, "tag", tag)
    return base


def run(repo, *args):
    return subprocess.run(  # noqa: S603 -- test invokes release_state.py with argv, no shell.
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def report(repo, *args):
    proc = run(repo, *args)
    return proc, json.loads(proc.stdout)


def python_files(version, heading, body):
    return {
        "pyproject.toml": PYPROJECT.format(version=version),
        "CHANGELOG.md": CHANGELOG.format(heading=heading, body=body),
    }


def r_files(version, heading, body):
    return {
        "DESCRIPTION": DESCRIPTION.format(version=version),
        "NEWS.md": NEWS.format(heading=heading, body=body),
    }


def test_python_consistent(tmp_path):
    repo = make_repo(tmp_path / "repo", python_files("1.4.0", "1.4.0", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "consistent"
    assert data["version"] == "1.4.0"


def test_python_released(tmp_path):
    repo = make_repo(tmp_path / "repo", python_files("1.4.0", "1.4.0", BULLET), tag="v1.4.0")
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "released"
    assert data["last_tag"] == "v1.4.0"


def test_python_development_unreleased_heading(tmp_path):
    repo = make_repo(tmp_path / "repo", python_files("1.4.0", "Unreleased", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "development"


def test_python_open_heading(tmp_path):
    repo = make_repo(tmp_path / "repo", python_files("1.4.0", "1.4.0", ""))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "open-heading"
    assert any("no entries" in p for p in data["problems"])


def test_python_mismatch(tmp_path):
    repo = make_repo(tmp_path / "repo", python_files("1.4.0", "1.3.0", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 3
    assert data["state"] == "mismatch"


def test_python_rc_suggests_final(tmp_path):
    repo = make_repo(tmp_path / "repo", python_files("1.3.0rc1", "1.3.0rc1", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["suggested_bump"] == "stable"
    assert data["suggested_version"] == "1.3.0"
    assert any("pre-release" in n for n in data["notes"])


def test_python_dev0_suggests_final(tmp_path):
    repo = make_repo(tmp_path / "repo", python_files("1.2.4.dev0", "1.2.4.dev0", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "development"
    assert data["suggested_version"] == "1.2.4"


def test_python_dynamic_version_uses_changelog(tmp_path):
    files = {
        "pyproject.toml": '[project]\nname = "demo"\ndynamic = ["version"]\n',
        "CHANGELOG.md": CHANGELOG.format(heading="1.2.0", body=BULLET),
    }
    repo = make_repo(tmp_path / "repo", files)
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["version"] == "1.2.0"
    assert data["version_source"] == "changelog heading (dynamic version)"
    assert any("dynamic" in p for p in data["problems"])


def test_python_section_extracts_entries(tmp_path):
    repo = make_repo(tmp_path / "repo", python_files("1.4.0", "1.4.0", BULLET))
    proc = run(repo, "--section", "1.4.0")
    assert proc.returncode == 0
    assert "Something (#1)." in proc.stdout


def test_r_consistent(tmp_path):
    repo = make_repo(tmp_path / "repo", r_files("1.4.0", "1.4.0", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "consistent"
    assert data["language"] == "r"


def test_r_released(tmp_path):
    repo = make_repo(tmp_path / "repo", r_files("1.4.0", "1.4.0", BULLET), tag="v1.4.0")
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "released"


def test_r_development_dev_suffix(tmp_path):
    repo = make_repo(tmp_path / "repo", r_files("1.4.0.9000", "1.4.0.9000", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "development"


def test_r_open_heading(tmp_path):
    repo = make_repo(tmp_path / "repo", r_files("1.4.0", "1.4.0", ""))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["state"] == "open-heading"


def test_r_mismatch(tmp_path):
    repo = make_repo(tmp_path / "repo", r_files("1.4.0", "1.3.0", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 3
    assert data["state"] == "mismatch"


def test_mentions_skip_longer_version(tmp_path):
    files = python_files("1.4.0", "1.4.0", BULLET)
    files["pins.txt"] = "foo>=11.4.0\n"
    files["exact.txt"] = "requires demo 1.4.0\n"
    repo = make_repo(tmp_path / "repo", files)
    _, data = report(repo)
    hit_files = [hit["file"] for hit in data["version_mentions"]]
    assert "exact.txt" in hit_files
    assert "pins.txt" not in hit_files
    assert data["mentions_truncated"] is False


def test_mentions_truncated_over_cap(tmp_path):
    files = python_files("1.4.0", "1.4.0", BULLET)
    for i in range(25):
        files[f"dep{i:02d}.txt"] = "pin 1.4.0\n"
    repo = make_repo(tmp_path / "repo", files)
    _, data = report(repo)
    assert len(data["version_mentions"]) == 20
    assert data["mentions_truncated"] is True


def test_mentions_none_found_is_empty(tmp_path):
    # The version appears only in the skipped manifest and changelog, so git grep's
    # hits are all filtered; a version absent everywhere makes git grep exit 1.
    repo = make_repo(tmp_path / "repo", python_files("1.4.0", "1.4.0", BULLET))
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["version_mentions"] == []
    assert data["mentions_truncated"] is False


def test_mentions_git_grep_no_match_exits_0(tmp_path):
    files = python_files("1.4.0", "1.4.0", BULLET)
    repo = make_repo(tmp_path / "repo", files)
    # Untrack both files that carry the version, so git grep itself finds nothing (exit 1).
    git(repo, "rm", "-q", "--cached", "pyproject.toml", "CHANGELOG.md")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-qm", "untrack")
    proc, data = report(repo)
    assert proc.returncode == 0
    assert data["version_mentions"] == []
    assert proc.stderr == ""


def test_mentions_git_grep_failure_exits_4(tmp_path):
    real_git = shutil.which("git")
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "git"
    stub.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '  if [ "$arg" = grep ]; then echo "fatal: stubbed grep failure" >&2; exit 2; fi\n'
        "done\n"
        f'exec "{real_git}" "$@"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    repo = make_repo(tmp_path / "repo", python_files("1.4.0", "1.4.0", BULLET))
    env = {**os.environ, "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}"}
    proc = subprocess.run(  # noqa: S603 -- test invokes release_state.py with argv, no shell.
        [sys.executable, str(SCRIPT), "--repo", str(repo)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 4
    assert proc.stdout == ""
    assert "git grep" in proc.stderr
    assert "stubbed grep failure" in proc.stderr
