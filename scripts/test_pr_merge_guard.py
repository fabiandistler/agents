"""Tests for scripts/pr_merge_guard.py and the opencode plugin that calls it."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pr_merge_guard as guard
import tomllib

SCRIPT = Path(__file__).resolve().parent / "pr_merge_guard.py"
PLUGIN = Path(__file__).resolve().parent / "opencode" / "pr-merge-guard.js"
MERGE_GUARD_PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "merge-guard"

BLOCKED_COMMANDS = [
    "gh pr merge 7 --squash",
    "gh pr merge --auto --merge",
    "gh -R fabiandistler/agents pr merge 7",
    "gh pr merge -R fabiandistler/agents 7 --delete-branch",
    "/usr/local/bin/gh pr merge 7",
    "cd /repo && gh pr checks 7 && gh pr merge 7",
    "git push origin HEAD; gh pr merge",
    "echo ok\ngh pr merge 7",
    "GH_TOKEN=x gh pr merge 7",
    "sudo -u me gh pr merge 7",
    "timeout 30 gh pr merge 7",
    "echo 7 | xargs -I {} gh pr merge {}",
    "bash -c 'gh pr merge 7 --rebase'",
    'eval "gh pr merge 7"',
    "echo $(gh pr merge 7)",
    "echo `gh pr merge 7`",
    "bash <<'EOF'\ngh pr merge 7\nEOF",
    "cat <<EOF | sh\ngh pr merge 7\nEOF",
    "gh api -X PUT repos/fabiandistler/agents/pulls/7/merge",
    "gh api --method PUT /repos/o/r/pulls/7/merge -f merge_method=squash",
    "gh api -XPUT repos/{owner}/{repo}/pulls/7/merge",
    "gh api repos/o/r/pulls/7/merge -f merge_method=squash",
    "gh api repos/o/r/merges -f base=main -f head=feature",
    "gh api graphql -f query='mutation { enablePullRequestAutoMerge(input: {}) { x } }'",
    "gh api graphql -f query='mutation { mergePullRequest(input: {}) { x } }'",
    "gh api graphql -f query='mutation { enqueuePullRequest(input: {}) { x } }'",
    'gh api graphql --input - <<\'EOF\'\n{"query": "mutation { mergePullRequest(input: {}) { x } }"}\nEOF',
    "curl -X PUT -H 'Authorization: token t' https://api.github.com/repos/o/r/pulls/7/merge",
    'curl -d \'{"query":"mutation { mergePullRequest(input:{}) {x} }"}\' https://api.github.com/graphql',
]

ALLOWED_COMMANDS = [
    "gh pr view 7",
    "gh pr checks 7 --watch",
    "gh pr create --title 'merge guard' --body 'blocks gh pr merge'",
    "gh pr list --search 'merge'",
    "gh pr view 7 --json mergeable,mergeStateStatus",
    "git merge origin/main",
    "git merge --no-ff feature",
    "git commit -m 'docs: explain why gh pr merge is blocked'",
    "echo 'gh pr merge 7'",
    "grep -rn 'gh pr merge' docs/",
    # Heredoc bodies are data, even with an unbalanced quote in them.
    "python3 - <<'EOF'\nprint(\"gh pr merge 7\")\nit's\nEOF",
    "git commit -F - <<EOF\nBlock gh pr merge\nEOF",
    "cat <<<'gh pr merge 7'",
    "gh api repos/o/r/pulls/7/merge",
    "gh api repos/o/r/pulls/7",
    "gh api graphql -f query='{ viewer { login } }'",
    "gh api repos/o/r/merges --method GET",
    "curl https://api.github.com/repos/o/r/pulls/7/merge",
    "python3 scripts/pr_merge_guard.py --help",
    "ls -la",
]

BLOCKED_TOOLS = [
    ("claude", {"tool_name": "mcp__github__merge_pull_request", "tool_input": {"pullNumber": 7}}),
    ("claude", {"tool_name": "mcp__plugin_x_github__enable_pr_auto_merge", "tool_input": {}}),
    ("codex", {"tool_name": "mcp__github__merge_pull_request", "tool_input": {"pullNumber": 7}}),
    ("codex", {"tool_name": "mcp__github__enable_pr_auto_merge", "tool_input": {}}),
    ("opencode", {"tool": "github_merge_pull_request", "args": {}}),
    ("opencode", {"tool": "github_enable_pr_auto_merge"}),
    # Any tool whose input carries a shell `command` is checked as a shell.
    ("claude", {"tool_name": "mcp__dc__start_process", "tool_input": {"command": "gh pr merge 7"}}),
    ("codex", {"tool_name": "Bash", "tool_input": {"command": ["gh", "pr", "merge", "7"]}}),
]

ALLOWED_TOOLS = [
    ("claude", {"tool_name": "mcp__github__pull_request_read", "tool_input": {"pullNumber": 7}}),
    ("claude", {"tool_name": "mcp__github__disable_pr_auto_merge", "tool_input": {}}),
    ("codex", {"tool_name": "mcp__github__update_pull_request_branch", "tool_input": {}}),
    ("codex", {"tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}}),
    ("opencode", {"tool": "github_create_pull_request", "args": {"title": "merge guard"}}),
    ("opencode", {"tool": "read", "args": {"filePath": "merge_pull_request.md"}}),
]


def claude_event(command: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def codex_event(command: str) -> dict:
    event = claude_event(command)
    event["turn_id"] = "t1"
    return event


def opencode_event(command: str) -> dict:
    return {"tool": "bash", "args": {"command": command, "description": "run"}}


EVENTS = {"claude": claude_event, "codex": codex_event, "opencode": opencode_event}


def run_guard(harness: str, event: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--harness", harness],
        input=event if isinstance(event, str) else json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
    )


def test_blocks_merge_commands() -> None:
    missed = [c for c in BLOCKED_COMMANDS if guard.check_shell(c, Path(".")) is None]
    assert missed == []


def test_allows_other_commands() -> None:
    blocked = [c for c in ALLOWED_COMMANDS if guard.check_shell(c, Path(".")) is not None]
    assert blocked == []


def test_graphql_query_from_file_is_read(tmp_path: Path) -> None:
    (tmp_path / "q.graphql").write_text("mutation { enablePullRequestAutoMerge(input: {}) { x } }")
    assert guard.check_shell("gh api graphql -F query=@q.graphql", tmp_path) is not None
    (tmp_path / "v.graphql").write_text("{ viewer { login } }")
    assert guard.check_shell("gh api graphql -F query=@v.graphql", tmp_path) is None


def test_cli_blocks_with_reason_per_harness() -> None:
    for harness, event in EVENTS.items():
        run = run_guard(harness, event("gh pr merge 7 --squash"))
        assert run.returncode == guard.EXIT_BLOCK, harness
        assert "ask the user" in run.stderr
        assert run.stdout == ""


def test_cli_allows_per_harness() -> None:
    for harness, event in EVENTS.items():
        run = run_guard(harness, event("gh pr view 7"))
        assert (run.returncode, run.stderr) == (guard.EXIT_ALLOW, ""), harness


def test_blocks_merge_tools() -> None:
    for harness, event in BLOCKED_TOOLS:
        assert run_guard(harness, event).returncode == guard.EXIT_BLOCK, event


def test_allows_other_tools() -> None:
    for harness, event in ALLOWED_TOOLS:
        assert run_guard(harness, event).returncode == guard.EXIT_ALLOW, event


def test_bad_input_exits_3() -> None:
    for harness, stdin in [("claude", "not json"), ("claude", "[]"), ("opencode", "{}")]:
        run = run_guard(harness, stdin)
        assert run.returncode == guard.EXIT_BAD_INPUT, stdin
        assert "stdin is not" in run.stderr


def test_usage_error_does_not_look_like_a_block() -> None:
    assert run_guard("cursor", claude_event("ls")).returncode == guard.EXIT_USAGE


def test_help_is_short_and_names_exit_codes() -> None:
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=True
    )
    assert "Exit:" in run.stdout and "Examples:" in run.stdout
    assert len(run.stdout.splitlines()) <= 25


def test_claude_settings_entry_is_idempotent_and_removable() -> None:
    settings = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "x"}]}]}}
    command = 'python3 "/repo/scripts/pr_merge_guard.py" --harness claude'
    once = guard.with_claude_hook(settings, command)
    assert guard.with_claude_hook(once, command) == once
    assert once["hooks"]["PreToolUse"] == [guard.claude_hook_entry(command)]
    moved = guard.with_claude_hook(once, command.replace("/repo", "/elsewhere"))
    assert len(moved["hooks"]["PreToolUse"]) == 1
    assert guard.without_claude_hook(once) == settings
    assert guard.without_claude_hook({"hooks": {"PreToolUse": once["hooks"]["PreToolUse"]}}) == {}


def test_codex_toml_parses() -> None:
    parsed = tomllib.loads(guard.codex_hook_toml('python3 "/r/pr_merge_guard.py" --harness codex'))
    entry = parsed["hooks"]["PreToolUse"][0]
    assert entry["matcher"] == guard.HOOK_MATCHER
    assert entry["hooks"][0]["command"].endswith("--harness codex")


def test_opencode_plugin_blocks_via_both_apis() -> None:
    if shutil.which("node") is None:
        return  # CI installs Node for the Mermaid check; locally it is optional
    probe = f"""
import plugin from {json.dumps(PLUGIN.as_uri())};
const results = [];
const v1 = await plugin.server({{ directory: process.cwd() }});
for (const [tool, args] of [["bash", {{ command: "gh pr merge 7" }}],
                            ["github_merge_pull_request", {{}}],
                            ["bash", {{ command: "gh pr view 7" }}]]) {{
  try {{ await v1["tool.execute.before"]({{ tool }}, {{ args }}); results.push("allow"); }}
  catch (e) {{ results.push(e.message.includes("ask the user") ? "block" : "error"); }}
}}
let hook;
await plugin.setup({{ directory: process.cwd(), tool: {{ hook: async (name, cb) => {{ hook = cb; }} }} }});
try {{ await hook({{ tool: "bash", input: {{ command: "gh pr merge 7" }} }}); results.push("allow"); }}
catch (e) {{ results.push("block"); }}
console.log(JSON.stringify([plugin.id, results]));
"""
    run = subprocess.run(
        ["node", "--input-type=module", "-e", probe], capture_output=True, text=True, check=True
    )
    plugin_id, results = json.loads(run.stdout)
    assert plugin_id
    assert results == ["block", "block", "allow", "block"]


def test_plugin_hooks_json_carries_the_guard_entry() -> None:
    hooks = json.loads((MERGE_GUARD_PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr_merge_guard.py" --harness claude'
    assert hooks == {"hooks": {"PreToolUse": [guard.claude_hook_entry(command)]}}


def test_plugin_hook_command_blocks_from_the_plugin_root() -> None:
    # Claude copies the plugin into its cache and dereferences this symlink,
    # so ${CLAUDE_PLUGIN_ROOT} must reach the script through it.
    assert (MERGE_GUARD_PLUGIN / "scripts" / "pr_merge_guard.py").resolve() == SCRIPT
    hooks = json.loads((MERGE_GUARD_PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    command = command.replace("python3", shlex.quote(sys.executable), 1)
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(MERGE_GUARD_PLUGIN)}
    for shell_command, expected in [("gh pr merge 7", guard.EXIT_BLOCK), ("ls", guard.EXIT_ALLOW)]:
        run = subprocess.run(
            ["sh", "-c", command],
            input=json.dumps(claude_event(shell_command)),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == expected, (shell_command, run.stderr)
