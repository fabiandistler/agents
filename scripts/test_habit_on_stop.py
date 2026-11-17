"""Tests for scripts/habit_on_stop.py, the Stop hook that coaches new design smells.

The tests run the real ruff from PATH against throwaway git repos and put a stub
habit-mapper first on PATH, which records its stdin and answers with
$STUB_MAPPER_EXIT, so they stay offline and do not depend on the guide texts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import habit_on_stop
import pytest

SCRIPT = Path(__file__).resolve().parent / "habit_on_stop.py"
REPO_ROOT = SCRIPT.parent.parent

MANY_PARAMETERS = "def bill(a, b, c, d, e, f):\n    return a + b + c + d + e + f\n"


def complex_function(branches: int) -> str:
    """A function whose McCabe complexity is branches + 1."""
    body = "".join(f"    if x == {n}:\n        return {n}\n" for n in range(branches))
    return f"def pick(x):\n{body}    return -1\n"


def run(argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- test runs fixed argv, no shell
        argv, capture_output=True, text=True, check=False, **kwargs
    )


def git(repo: Path, *args: str) -> str:
    completed = run(["git", "-C", str(repo), *args])
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo whose main holds legacy.py with a complexity-12 function; HEAD is a branch off it."""
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "legacy.py").write_text(complex_function(11) + "\n\nVALUE = 1\n", encoding="utf-8")
    commit_all(root, "base")
    git(root, "switch", "-qc", "work")
    return root


@pytest.fixture
def mapper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stub habit-mapper first on PATH; returns the file its stdin lands in."""
    stub_bin = tmp_path / "stub-bin"
    stub_bin.mkdir()
    received = tmp_path / "mapper-stdin.json"
    stub = stub_bin / "habit-mapper"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f"cat > '{received}'\n"
        'echo "GUIDE for $(pwd)"\n'
        'echo "mapper broke" >&2\n'
        'exit "${STUB_MAPPER_EXIT:-1}"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_bin}{os.pathsep}{os.environ['PATH']}")
    return received


def run_hook(
    repo: Path, event: dict | None = None, path: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    if path is not None:
        env["PATH"] = path
    return run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(event or {"hook_event_name": "Stop", "stop_hook_active": False}),
        env=env,
    )


def mapper_smells(received: Path) -> dict[str, list[dict]]:
    findings = json.loads(received.read_text(encoding="utf-8"))
    assert {finding["language"] for finding in findings} == {"python"}
    return {finding["smell"]: finding["issues"] for finding in findings}


def test_a_second_stop_passes_without_running_anything(repo, mapper):
    (repo / "new.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo, {"hook_event_name": "Stop", "stop_hook_active": True})

    assert (completed.returncode, completed.stderr) == (0, "")
    assert not mapper.exists()


def test_a_branch_without_python_changes_passes(repo, mapper):
    (repo / "README.md").write_text("notes\n", encoding="utf-8")
    commit_all(repo, "docs")

    completed = run_hook(repo)

    assert (completed.returncode, completed.stderr) == (0, "")
    assert not mapper.exists()


def test_old_debt_in_a_touched_file_stays_quiet(repo, mapper):
    legacy = repo / "legacy.py"
    legacy.write_text(legacy.read_text(encoding="utf-8").replace("VALUE = 1", "VALUE = 2"))
    commit_all(repo, "touch legacy")

    completed = run_hook(repo)

    assert (completed.returncode, completed.stderr) == (0, "")
    assert not mapper.exists()


def test_old_debt_stays_quiet_when_the_function_moves_down(repo, mapper):
    legacy = repo / "legacy.py"
    legacy.write_text("import os\n\n\n" + legacy.read_text(encoding="utf-8"), encoding="utf-8")

    completed = run_hook(repo)

    assert (completed.returncode, completed.stderr) == (0, "")


def test_a_new_function_with_too_many_parameters_is_coached(repo, mapper):
    legacy = repo / "legacy.py"
    legacy.write_text(legacy.read_text(encoding="utf-8") + "\n\n" + MANY_PARAMETERS)
    commit_all(repo, "add bill")

    completed = run_hook(repo)

    assert completed.returncode == 2
    assert f"GUIDE for {repo}" in completed.stderr
    assert "do not silence the rule with noqa" in completed.stderr
    (issue,) = mapper_smells(mapper)["too-many-parameters"]
    assert issue["details"]["file"] == "legacy.py"
    assert issue["details"]["source"] == "ruff:PLR0913"
    assert (
        issue["details"]["line"]
        == legacy.read_text().splitlines().index("def bill(a, b, c, d, e, f):") + 1
    )


def test_complexity_that_grows_in_an_old_function_counts_as_new(repo, mapper):
    (repo / "legacy.py").write_text(complex_function(13) + "\n\nVALUE = 1\n", encoding="utf-8")

    completed = run_hook(repo)

    assert completed.returncode == 2
    (issue,) = mapper_smells(mapper)["high-complexity"]
    assert re.search(r"`pick` is too complex \(14 > 10\)", issue["details"]["message"])


def test_an_untracked_file_is_checked(repo, mapper):
    (repo / "pkg").mkdir()
    (repo / "pkg" / "fresh.py").write_text(
        "def load():\n    try:\n        return 1\n    except Exception:\n        return None\n",
        encoding="utf-8",
    )

    completed = run_hook(repo)

    assert completed.returncode == 2
    (issue,) = mapper_smells(mapper)["swallowed-exception"]
    assert issue["details"]["file"] == "pkg/fresh.py"


def test_a_file_ruff_excludes_is_not_checked(repo, mapper):
    (repo / "ruff.toml").write_text('extend-exclude = ["vendored.py"]\n', encoding="utf-8")
    (repo / "vendored.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo)

    assert (completed.returncode, completed.stderr) == (0, "")


def test_smells_the_mapper_only_suggests_let_the_agent_stop(repo, mapper, monkeypatch):
    monkeypatch.setenv("STUB_MAPPER_EXIT", "0")
    (repo / "new.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo)

    assert (completed.returncode, completed.stderr) == (0, "")
    assert mapper.exists()


def test_a_broken_mapper_is_reported_not_passed(repo, mapper, monkeypatch):
    monkeypatch.setenv("STUB_MAPPER_EXIT", "2")
    (repo / "new.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo)

    assert completed.returncode == 2
    assert "habit-on-stop: habit-mapper failed: mapper broke" in completed.stderr


def test_a_missing_mapper_is_reported_with_the_install_line(repo, tmp_path):
    ruff_only = tmp_path / "ruff-only"
    ruff_only.mkdir()
    (ruff_only / "ruff").symlink_to(shutil.which("ruff"))
    (repo / "new.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo, path=f"{ruff_only}{os.pathsep}/usr/bin{os.pathsep}/bin")

    assert completed.returncode == 2
    assert completed.stderr.strip() == (
        "habit-on-stop: MISSING habit-mapper: "
        "python3 -m pip install -r scripts/check_all.requirements.txt"
    )


def test_a_repo_without_a_default_branch_is_reported(tmp_path, mapper):
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    git(lonely, "init", "-q", "-b", "trunk")
    (lonely / "a.py").write_text("A = 1\n", encoding="utf-8")
    commit_all(lonely, "base")

    completed = run_hook(lonely)

    assert completed.returncode == 2
    assert "no default branch to compare against" in completed.stderr


def test_identical_findings_are_matched_one_for_one():
    finding = {"code": "PLR0913", "message": "Too many arguments in function definition (6 > 5)"}

    assert habit_on_stop.introduced([finding, finding], [finding]) == [finding]


def test_the_committed_settings_run_the_hook_once_on_stop():
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))

    (entry,) = settings["hooks"]["Stop"]
    (hook,) = entry["hooks"]
    assert hook["command"] == 'python3 "$CLAUDE_PROJECT_DIR"/scripts/habit_on_stop.py'
    assert 0 < hook["timeout"] < 600


def test_the_ruff_pin_matches_the_pre_commit_pin():
    """The hook's ruff and the commit hooks' ruff are one version, pinned twice."""
    requirements = (REPO_ROOT / "scripts" / "check_all.requirements.txt").read_text(
        encoding="utf-8"
    )
    pre_commit = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    pinned = re.search(r"^ruff==(\S+)$", requirements, re.MULTILINE)
    rev = re.search(r"astral-sh/ruff-pre-commit\n\s+rev: v(\S+)", pre_commit)
    assert pinned and rev
    assert pinned.group(1) == rev.group(1)
