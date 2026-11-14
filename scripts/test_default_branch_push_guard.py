"""Tests for scripts/default_branch_push_guard.py and the agent-run settings fragment."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import default_branch_push_guard as guard
import pr_merge_guard
import pytest

SCRIPTS = Path(__file__).resolve().parent
SCRIPT = SCRIPTS / "default_branch_push_guard.py"
FRAGMENT = SCRIPTS / "agent_run_settings.json"
PROJECT_SETTINGS = SCRIPTS.parent / ".claude" / "settings.json"
FALLBACK = guard.FALLBACK_DEFAULT_BRANCHES

BLOCKED_COMMANDS = [
    # Refspecs and bare branch arguments that resolve to the default branch.
    "git push origin main",
    "git push origin master",
    "git push origin HEAD:main",
    "git push origin +main",
    "git push origin refs/heads/main",
    "git push origin HEAD:refs/heads/main",
    "git push origin +HEAD:refs/heads/main",
    "git push origin feature:main",
    "git push -f origin main",
    "git push --force-with-lease origin HEAD:main",
    "git push -u origin agent/issue-12 main",
    "git push --repo origin origin main",
    "git -C /repo push origin HEAD:main",
    "git push origin 'refs/heads/*:refs/heads/*'",
    # Deleting the default branch.
    "git push --delete origin main",
    "git push origin --delete main",
    "git push -d origin main",
    "git push origin :main",
    # Every branch at once.
    "git push --all",
    "git push --all origin",
    "git push origin --branches",
    "git push --mirror",
    "git push --mirror origin",
    "git push --mirr origin",
    # Wrapped, chained or nested.
    "cd /repo && git push origin main",
    "GIT_TRACE=1 git push origin main",
    "bash -c 'git push origin HEAD:main'",
    'eval "git push origin main"',
    "bash <<'EOF'\ngit push origin main\nEOF",
    "git push origin main 2>&1 | tail -5",
    # Arguments the parser cannot read fail closed.
    'git push origin "$BRANCH"',
    "git push origin HEAD:$TARGET",
    "git push origin ${BRANCH}",
    "git push origin $(git branch --show-current)",
    "git push origin `git branch --show-current`",
    "git push $REMOTE HEAD",
    "git push origin 'main",
    # REST writes to the ref.
    "gh api -X PATCH repos/o/r/git/refs/heads/main -f sha=abc",
    "gh api --method DELETE repos/{owner}/{repo}/git/refs/heads/main",
    "gh api repos/o/r/git/refs/heads/main -f sha=abc -F force=true",
    "gh api -X PATCH repos/o/r/git/refs/heads/$B -f sha=abc",
    # REST writes to file contents on the default branch.
    "gh api -X PUT repos/o/r/contents/x",
    "gh api -X PUT repos/o/r/contents/x -f message=m -f content=Zm9v",
    "gh api -X PUT repos/o/r/contents/docs/x.md -f branch=main -f message=m",
    "gh api -X DELETE /repos/o/r/contents/x -f sha=abc -f message=m",
    ('gh api -X PUT repos/o/r/contents/x --input - <<\'EOF\'\n{"message": "m"}\nEOF'),
    # REST merge into the default branch.
    "gh api repos/o/r/merges -f base=main -f head=feature",
    "gh api -X POST repos/o/r/merges -f head=feature",
    # curl writes.
    (
        "curl -X PUT -H 'Authorization: token t' https://api.github.com/repos/o/r/contents/x"
        ' -d \'{"message":"m","content":"Zm9v"}\''
    ),
    'curl -X PATCH https://api.github.com/repos/o/r/git/refs/heads/main -d \'{"sha":"abc"}\'',
    'curl -d \'{"base":"main","head":"f"}\' https://api.github.com/repos/o/r/merges',
]

ALLOWED_COMMANDS = [
    "git push origin agent/issue-12",
    "git push -u origin agent/issue-12",
    "git push -u origin HEAD",
    "git push origin HEAD",
    "git push",
    "git push origin",
    "git push origin HEAD:refs/heads/agent/issue-12",
    "git push origin main:agent/issue-12",
    "git push origin --delete agent/issue-12",
    "git push origin v1.2.0",
    "git push --tags origin",
    "git push --atomic origin feature",
    "git pull origin main",
    "git fetch origin main",
    "git checkout main",
    "git log origin/main",
    "git commit -m 'git push origin main'",
    'echo "$BRANCH" && git push origin feature',
    "git push origin feature > push.log",
    "gh api repos/o/r/git/refs/heads/main",
    "gh api repos/o/r/contents/x",
    "gh api repos/o/r/contents/x?ref=main",
    "gh api -X PUT repos/o/r/contents/x -f branch=feature",
    "gh api -X PUT repos/o/r/contents/x -f message=m -f branch=agent/issue-12",
    "gh api -X PATCH repos/o/r/git/refs/heads/feature -f sha=abc",
    ('gh api -X PUT repos/o/r/contents/x --input - <<\'EOF\'\n{"branch": "feature"}\nEOF'),
    "gh api repos/o/r/merges -f base=feature -f head=main",
    "gh pr create --base main --head agent/issue-12 --title t --body b",
    "curl https://api.github.com/repos/o/r/contents/x",
    'curl -X PUT https://api.github.com/repos/o/r/contents/x -d \'{"branch":"feature"}\'',
]

BLOCKED_TOOLS = [
    ("mcp__github__push_files", {"branch": "main", "files": []}),
    ("mcp__github__push_files", {"files": []}),
    ("mcp__github__create_or_update_file", {"branch": "refs/heads/main", "path": "x"}),
    ("mcp__github__create_or_update_file", {"path": "x"}),
    ("mcp__github__delete_file", {"branch": "master", "path": "x"}),
    ("mcp__github__delete_file", {"branch": "", "path": "x"}),
]

ALLOWED_TOOLS = [
    ("mcp__github__push_files", {"branch": "agent/issue-12", "files": []}),
    ("mcp__github__create_or_update_file", {"branch": "feature", "path": "x"}),
    ("mcp__github__delete_file", {"branch": "feature", "path": "x"}),
    ("mcp__github__get_file_contents", {"path": "x"}),
    ("Read", {"file_path": "/repo/README.md"}),
]


def bash(command: str) -> str | None:
    return guard.check_tool_call("Bash", {"command": command}, Path("."), FALLBACK)


@pytest.mark.parametrize("command", BLOCKED_COMMANDS)
def test_blocks_writes_to_the_default_branch(command: str) -> None:
    assert bash(command), command


@pytest.mark.parametrize("command", ALLOWED_COMMANDS)
def test_allows_other_commands(command: str) -> None:
    assert bash(command) is None


@pytest.mark.parametrize(("tool", "tool_input"), BLOCKED_TOOLS)
def test_blocks_mcp_writes_to_the_default_branch(tool: str, tool_input: dict) -> None:
    assert guard.check_tool_call(tool, tool_input, Path("."), FALLBACK)


@pytest.mark.parametrize(("tool", "tool_input"), ALLOWED_TOOLS)
def test_allows_other_tools(tool: str, tool_input: dict) -> None:
    assert guard.check_tool_call(tool, tool_input, Path("."), FALLBACK) is None


@pytest.mark.parametrize(
    "command", ["git push origin $REF", "git push origin HEAD:$(cat target)", "git push origin 'x"]
)
def test_unreadable_refspec_blocks(command: str) -> None:
    reason = bash(command)
    assert reason
    assert "cannot" in reason


def test_contents_branch_from_input_file(tmp_path: Path) -> None:
    (tmp_path / "body.json").write_text('{"message": "m", "branch": "feature"}')
    (tmp_path / "main.json").write_text('{"message": "m", "branch": "main"}')

    def put(body: str) -> str | None:
        command = f"gh api -X PUT repos/o/r/contents/x --input {body}"
        return guard.check_tool_call("Bash", {"command": command}, tmp_path, FALLBACK)

    ok, blocked = put("body.json"), put("main.json")
    assert ok is None
    assert blocked


def run_guard(event: object, *options: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), "--harness", "claude", *options],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
    )


def push(refspec: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": f"git push origin {refspec}"}}


def test_default_branch_option_names_the_protected_branch() -> None:
    blocked = run_guard(push("trunk"), "--default-branch", "trunk")
    assert blocked.returncode == guard.EXIT_BLOCK
    assert "default_branch_push_guard" in blocked.stderr
    assert "trunk" in blocked.stderr
    assert run_guard(push("main"), "--default-branch", "trunk").returncode == guard.EXIT_ALLOW
    assert run_guard(push("HEAD:master"), "--default-branch", "trunk").returncode == 0


def test_without_option_main_and_master_are_protected() -> None:
    assert run_guard(push("main")).returncode == guard.EXIT_BLOCK
    assert run_guard(push("master")).returncode == guard.EXIT_BLOCK
    assert run_guard(push("trunk")).returncode == guard.EXIT_ALLOW


def test_codex_and_opencode_input() -> None:
    event = {"tool": "bash", "args": {"command": "git push origin main"}}
    run = subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), "--harness", "opencode"],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == guard.EXIT_BLOCK
    codex = {"tool_name": "Bash", "tool_input": {"command": ["git", "push", "origin", "main"]}}
    assert run_guard(codex).returncode == guard.EXIT_BLOCK


def test_bad_input_and_usage_errors_do_not_look_like_a_block() -> None:
    run = subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), "--harness", "claude"],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == guard.EXIT_BAD_INPUT
    assert run_guard(push("main"), "--default-branch", "").returncode == pr_merge_guard.EXIT_USAGE


def test_help_names_exit_codes() -> None:
    run = subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=True
    )
    assert "Exit: 0 allowed, 2 blocked" in run.stdout
    assert "--default-branch" in run.stdout


def fragment_commands() -> list[str]:
    settings = json.loads(FRAGMENT.read_text(encoding="utf-8"))
    entries = settings["hooks"]["PreToolUse"]
    assert all(entry["matcher"] == pr_merge_guard.HOOK_MATCHER for entry in entries)
    return [hook["command"] for entry in entries for hook in entry["hooks"]]


def test_settings_fragment_names_both_guards() -> None:
    commands = fragment_commands()
    assert any("/scripts/pr_merge_guard.py --harness claude" in c for c in commands)
    assert any(
        "/scripts/default_branch_push_guard.py --harness claude --default-branch "
        "{{default_branch}}" in c
        for c in commands
    )
    assert all("{{factory_dir}}/scripts/" in c for c in commands)


def test_project_settings_do_not_load_the_push_guard() -> None:
    assert "default_branch_push_guard" not in PROJECT_SETTINGS.read_text(encoding="utf-8")


def test_merge_guard_tokenizer_keeps_expansions_only_on_request() -> None:
    split = pr_merge_guard.split_simple_commands
    assert split('git push origin "$B"') == [["git", "push", "origin", "B"]]
    assert split('git push origin "$B"', keep_expansions=True) == [["git", "push", "origin", "$B"]]
    assert split("git push origin $(x) y", keep_expansions=True)[0] == [
        "git", "push", "origin", pr_merge_guard.SUBSTITUTION,
    ]  # fmt: skip
    assert split("echo `x`; git push o f", keep_expansions=True) == [
        ["echo", pr_merge_guard.SUBSTITUTION], ["x"], ["git", "push", "o", "f"],
    ]  # fmt: skip
