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
import yaml

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
    # An empty project config stops ruff from falling back to a user-level
    # ruff.toml, so the fixtures meet ruff's default thresholds.
    (root / "ruff.toml").write_text("", encoding="utf-8")
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


def test_a_user_level_ruff_config_does_not_change_the_thresholds(
    repo, mapper, tmp_path, monkeypatch
):
    user_config = tmp_path / "xdg-config" / "ruff"
    user_config.mkdir(parents=True)
    (user_config / "ruff.toml").write_text(
        "[lint.pylint]\nmax-args = 6\n\n[lint.mccabe]\nmax-complexity = 12\n", encoding="utf-8"
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user_config.parent))
    (repo / "bill.py").write_text(MANY_PARAMETERS, encoding="utf-8")
    commit_all(repo, "add bill")

    completed = run_hook(repo)

    assert completed.returncode == 2
    assert "too-many-parameters" in mapper_smells(mapper)


def test_old_debt_in_a_renamed_file_stays_quiet(repo, mapper):
    git(repo, "mv", "legacy.py", "renamed.py")
    commit_all(repo, "rename")

    completed = run_hook(repo)

    assert (completed.returncode, completed.stderr) == (0, "")
    assert not mapper.exists()


def test_a_file_that_is_not_utf8_is_reported(repo, mapper):
    (repo / "latin1.py").write_bytes("NAME = 'Grüße'\n".encode("latin-1"))

    completed = run_hook(repo)

    assert completed.returncode == 2
    assert "habit-on-stop: latin1.py is not UTF-8" in completed.stderr


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


def test_a_syntax_error_is_left_to_lint_on_edit(repo, mapper):
    """Ruff reports invalid-syntax whatever --select says; it is no design smell."""
    (repo / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    completed = run_hook(repo)

    assert (completed.returncode, completed.stderr) == (0, "")
    assert not mapper.exists()


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


def test_missing_tools_do_not_block_a_branch_without_python_changes(repo, tmp_path):
    (repo / "README.md").write_text("notes\n", encoding="utf-8")

    completed = run_hook(repo, path=f"{tmp_path}{os.pathsep}/usr/bin{os.pathsep}/bin")

    assert (completed.returncode, completed.stderr) == (0, "")


def pinned(package: str) -> str:
    """The version scripts/check_all.requirements.txt pins package to."""
    requirements = (REPO_ROOT / "scripts" / "check_all.requirements.txt").read_text("utf-8")
    match = re.search(rf"^{re.escape(package)}==(\S+)$", requirements, re.MULTILINE)
    assert match, f"no {package} pin"
    return match.group(1)


def tool_path(tmp_path: Path, *tools: str) -> str:
    """A PATH with git and only the named tools: the real ruff, a uv stub the hook never runs.

    /usr/bin may hold uv, so the hook's PATH leaves the system directories out.
    """
    tool_bin = tmp_path / "tool-bin"
    tool_bin.mkdir()
    for real_tool in ("git", "ruff") if "ruff" in tools else ("git",):
        real_path = shutil.which(real_tool)
        assert real_path, f"{real_tool} is not on PATH"
        (tool_bin / real_tool).symlink_to(real_path)
    if "uv" in tools:
        (tool_bin / "uv").write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        (tool_bin / "uv").chmod(0o755)
    return str(tool_bin)


def test_a_missing_mapper_without_uv_is_reported_with_the_pip_line(repo, tmp_path):
    (repo / "new.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo, path=tool_path(tmp_path, "ruff"))

    assert completed.returncode == 2
    assert completed.stderr.strip() == (
        "habit-on-stop: MISSING habit-mapper: "
        "python3 -m pip install -r scripts/check_all.requirements.txt"
    )


def test_a_missing_mapper_with_uv_is_reported_with_its_pinned_tool_install(repo, tmp_path):
    (repo / "new.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo, path=tool_path(tmp_path, "ruff", "uv"))

    assert completed.returncode == 2
    assert completed.stderr.strip() == (
        "habit-on-stop: MISSING habit-mapper: "
        f"uv tool install 'habit-hooks[python]=={pinned('habit-hooks[python]')}'"
    )


def test_both_missing_tools_with_uv_are_reported_with_both_pinned_installs(repo, tmp_path):
    (repo / "new.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo, path=tool_path(tmp_path, "uv"))

    assert completed.returncode == 2
    assert completed.stderr.strip() == (
        "habit-on-stop: MISSING ruff, habit-mapper: "
        f"uv tool install ruff=={pinned('ruff')} && "
        f"uv tool install 'habit-hooks[python]=={pinned('habit-hooks[python]')}'"
    )


def test_a_requirements_file_without_the_pin_is_reported(tmp_path, monkeypatch):
    unpinned = tmp_path / "check_all.requirements.txt"
    unpinned.write_text("ruff>=0.17\n", encoding="utf-8")
    monkeypatch.setattr(habit_on_stop, "REQUIREMENTS", unpinned)
    monkeypatch.setenv("PATH", tool_path(tmp_path, "uv"))

    with pytest.raises(habit_on_stop.HookError, match="has no single ruff== pin"):
        habit_on_stop.install_hint(["ruff"])


def test_a_checkout_without_a_default_branch_is_skipped_without_blocking(tmp_path, mapper):
    """Like the factory's depth-1 rework checkout of agent/issue-<n> alone."""
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    git(lonely, "init", "-q", "-b", "agent/issue-1")
    (lonely / "a.py").write_text(MANY_PARAMETERS, encoding="utf-8")
    commit_all(lonely, "base")

    completed = run_hook(lonely)

    assert completed.returncode == 1
    assert "habit-on-stop: skipped: no default branch to compare against" in completed.stderr
    assert not mapper.exists()


def test_a_branch_without_history_in_common_is_skipped_without_blocking(repo, mapper):
    git(repo, "switch", "-q", "--orphan", "unrelated")
    (repo / "new.py").write_text(MANY_PARAMETERS, encoding="utf-8")
    commit_all(repo, "unrelated root")

    completed = run_hook(repo)

    assert completed.returncode == 1
    assert "habit-on-stop: skipped: HEAD and main share no history" in completed.stderr


def test_a_project_dir_below_the_repo_root_checks_the_whole_repo(repo, mapper):
    (repo / "pkg").mkdir()
    (repo / "pkg" / "inner.py").write_text(MANY_PARAMETERS, encoding="utf-8")

    completed = run_hook(repo / "pkg")

    assert completed.returncode == 2
    (issue,) = mapper_smells(mapper)["too-many-parameters"]
    assert issue["details"]["file"] == "pkg/inner.py"


@pytest.mark.skipif(
    shutil.which("habit-mapper") is None and not os.environ.get("CI"),
    reason="habit-mapper not installed; CI installs it and never skips this test",
)
def test_the_real_mapper_reads_our_findings_and_blocks_with_a_guide(tmp_path):
    """Contract with habit-hooks 1.5.0: the finding shape, exit 1 and guides on stdout."""
    project = tmp_path / "project"
    (project / ".habit-hooks").mkdir(parents=True)
    shutil.copy(REPO_ROOT / ".habit-hooks" / "config.toml", project / ".habit-hooks")
    finding = {
        "filename": str(project / "billing.py"),
        "code": "PLR0913",
        "message": "Too many arguments in function definition (6 > 5)",
        "location": {"row": 7, "column": 5},
    }

    guides = habit_on_stop.coaching(project, [finding])

    assert guides is not None
    assert "too-many-parameters (1 issue)" in guides
    assert "billing.py:7" in guides


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
    pre_commit = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text("utf-8"))

    (rev,) = [
        entry["rev"]
        for entry in pre_commit["repos"]
        if entry["repo"] == "https://github.com/astral-sh/ruff-pre-commit"
    ]
    assert f"v{pinned('ruff')}" == rev
