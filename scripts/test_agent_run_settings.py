"""Tests for scripts/agent_run_settings.py: the guards a factory run loads."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import agent_run_settings
import pr_merge_guard
import pytest

SCRIPTS = Path(__file__).resolve().parent
SCRIPT = SCRIPTS / "agent_run_settings.py"


def bash_event(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def hook_commands(settings: dict) -> list[str]:
    return [hook["command"] for entry in settings["hooks"]["PreToolUse"] for hook in entry["hooks"]]


def run_hooks(settings: dict, event: str) -> list[int]:
    """Run every hook command as Claude Code does: through a shell, the event on stdin."""
    return [
        subprocess.run(  # noqa: S603 -- runs the rendered hook commands the test built.
            ["bash", "-c", command],  # noqa: S607 -- bash intentionally resolves from PATH.
            input=event,
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        for command in hook_commands(settings)
    ]


@pytest.fixture
def factory(tmp_path: Path) -> Path:
    """A factory checkout at a path with a space, as a copy of this repository's scripts."""
    checkout = tmp_path / "factory dir"
    shutil.copytree(SCRIPTS, checkout / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    return checkout


def test_rendered_settings_leave_no_placeholder(factory: Path) -> None:
    settings = agent_run_settings.render(str(factory), "trunk")
    for command in hook_commands(settings):
        assert "{{" not in command
        assert command.startswith("python3 ")


def test_rendered_hooks_block_a_merge_and_a_default_branch_push(factory: Path) -> None:
    settings = agent_run_settings.render(str(factory), "trunk")
    merge = run_hooks(settings, bash_event("gh pr merge 5 --squash"))
    assert pr_merge_guard.EXIT_BLOCK in merge, "the merge guard must run from the factory"
    push = run_hooks(settings, bash_event("git push origin trunk"))
    assert pr_merge_guard.EXIT_BLOCK in push, "the push guard must protect the default branch"
    assert run_hooks(settings, bash_event("git push origin agent/issue-7")) == [0, 0]


def test_a_hostile_default_branch_stays_one_argument(factory: Path, tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    branch = f"x'; touch {marker}; echo '"
    settings = agent_run_settings.render(str(factory), branch)
    run_hooks(settings, bash_event("git status"))
    assert not marker.exists(), "the default branch must reach the guard quoted"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd="/",
    )


def test_cli_writes_the_settings_file(factory: Path, tmp_path: Path) -> None:
    output = tmp_path / "settings.json"
    run = run_cli(
        "--factory-dir", str(factory), "--default-branch", "main", "--output", str(output)
    )
    assert run.returncode == agent_run_settings.EXIT_OK, run.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == agent_run_settings.render(
        str(factory), "main"
    )


@pytest.mark.parametrize(
    ("factory_dir", "branch"), [("relative/factory", "main"), ("/abs/factory", "")]
)
def test_cli_rejects_a_relative_factory_dir_or_an_empty_branch(
    factory_dir: str, branch: str, tmp_path: Path
) -> None:
    output = tmp_path / "settings.json"
    run = run_cli("--factory-dir", factory_dir, "--default-branch", branch, "--output", str(output))
    assert run.returncode == agent_run_settings.EXIT_USAGE
    assert not output.exists()
