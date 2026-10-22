"""Tests for scripts/secret_read_guard.py and the opencode plugin that calls it."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pr_merge_guard
import secret_read_guard as guard
import tomllib

SCRIPT = Path(__file__).resolve().parent / "secret_read_guard.py"
PLUGIN = Path(__file__).resolve().parent / "opencode" / "secret-read-guard.js"
SECRET_GUARD_PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "secret-guard"

BLOCKED_COMMANDS = [
    "cat .env",
    "cat ./config/.env.production",
    "less .env.local",
    "grep TOKEN .env",
    "head -n 3 .env",
    "grep KEY < .env",
    "cp .env /tmp/copy",
    "cat .env*",
    "cat ~/.Renviron",
    "cat ~/.git-credentials",
    "cat $HOME/.netrc",
    "cat .npmrc ~/.pypirc",
    "cat ~/.aws/credentials",
    "cat ~/.aws/*",
    "cat ~/.docker/config.json",
    "kubectl config view --raw < ~/.kube/config",
    "cat ~/.ssh/id_ed25519",
    "cat ~/.ssh/*",
    "cat ~/.claude/.credentials.json",
    "jq . ~/.codex/auth.json",
    "cat ~/.local/share/opencode/auth.json",
    "cat ~/.password-store/github.gpg",
    "pass show github/token",
    "pass github/token",
    "gpg --decrypt secret.gpg",
    "gpg2 --export-secret-keys me",
    "cat /proc/self/environ",
    "tr '\\0' '\\n' < /proc/1/environ",
    "env",
    "env | grep -i token",
    "sudo env",
    "env -0",
    "printenv",
    "printenv GITHUB_TOKEN",
    "printenv OPENAI_API_KEY",
    "export",
    "export -p",
    "declare -x",
    "declare -p",
    "declare -p AWS_SECRET_ACCESS_KEY",
    "typeset -x",
    "set",
    "(set -o posix; set)",
    "echo ok && cat .env",
    "echo $(cat .env)",
    "bash -c 'cat .env'",
    'eval "printenv"',
    "bash <<'EOF'\ncat .env\nEOF",
    "env FOO=bar cat .env",
    "timeout 5 cat ~/.netrc",
    "cat ~/.config/gh/hosts.yml",
    "cat .envrc",
    "jq .oauthAccount ~/.claude.json",
    "cat ~/.claude.json",
    "gopass show github/token",
    "gopass github/token",
    "sops -d secrets.enc.yaml",
    "sops --decrypt secrets.enc.yaml",
    "sops decrypt secrets.enc.yaml",
    # Over-blocked on purpose: these files often hold no secret, but may.
    "cat .npmrc",
    "kubectl --kubeconfig ~/.kube/config get pods",
    "kubectl --kubeconfig=/home/me/.kube/config get pods",
]

ALLOWED_COMMANDS = [
    "cat .env.example",
    "cp .env.example .env",
    "cat .env.sample .env.template",
    "cat .env.example > .env",
    "printf 'FOO=1\\n' >> .env",
    "ls -la .env",
    "test -f .env && echo present",
    "[ -f .env ] || touch .env",
    "rm .env",
    "git add .env.example",
    "git check-ignore -v .env",
    "git rm --cached .env",
    "find . -name '.env*'",
    "source .venv/bin/activate",
    "set -a; source .env; set +a",
    "uv run --env-file .env pytest",
    "docker compose --env-file=.env up -d",
    "echo 'see .env.example'",
    "git commit -m 'docs: never commit .env'",
    "gh pr create --body 'blocks cat ~/.aws/credentials'",
    "cat ~/.ssh/id_ed25519.pub",
    "ls ~/.ssh",
    "ssh -i ~/.ssh/id_ed25519 host true",
    "ssh-keygen -y -f ~/.ssh/id_ed25519",
    "cat *",
    "cat README.md",
    "env FOO=bar python3 script.py",
    "env -u PYTHONPATH pytest",
    "printenv PATH",
    "printenv HOME SHELL",
    "export PATH=$PATH:/opt/bin",
    "export FOO",
    "declare -a items",
    "declare -f",
    "set -euo pipefail",
    "set -- a b",
    "pass",
    "pass ls",
    "pass find github",
    "gopass ls",
    "gopass find github",
    "sops -e -i secrets.yaml",
    "sops exec-env secrets.enc.yaml ./deploy.sh",
    "ls ~/.config/gh",
    "cat ~/.config/gh/config.yml",
    "direnv allow .",
    "gpg --list-keys",
    "python3 - <<'EOF'\nprint(open('.env.example').read())\nEOF",
    "git commit -F - <<EOF\nIgnore .env\nEOF",
    "cat .venv/pyvenv.cfg",
]

BLOCKED_TOOLS = [
    ("claude", {"tool_name": "Read", "tool_input": {"file_path": "/repo/.env"}}),
    ("claude", {"tool_name": "Read", "tool_input": {"file_path": "/home/me/.ssh/id_rsa"}}),
    ("claude", {"tool_name": "Edit", "tool_input": {"file_path": ".env.local"}}),
    ("claude", {"tool_name": "Grep", "tool_input": {"pattern": "KEY", "path": "/repo/.env"}}),
    ("claude", {"tool_name": "Grep", "tool_input": {"pattern": "KEY", "glob": ".env*"}}),
    ("claude", {"tool_name": "mcp__fs__read_text_file", "tool_input": {"path": "~/.netrc"}}),
    ("codex", {"tool_name": "Bash", "tool_input": {"command": ["cat", ".env"]}}),
    ("codex", {"tool_name": "Bash", "tool_input": {"command": "printenv"}}),
    ("opencode", {"tool": "read", "args": {"filePath": "/home/me/.aws/credentials"}}),
    ("opencode", {"tool": "grep", "args": {"pattern": "x", "include": ".env.*"}}),
    ("claude", {"tool_name": "Read", "tool_input": {"file_path": "/home/me/.claude.json"}}),
    ("opencode", {"tool": "read", "args": {"filePath": "/home/me/.config/gh/hosts.yml"}}),
    ("claude", {"tool_name": "Read", "tool_input": {"file_path": "/repo/.envrc"}}),
    ("opencode", {"tool": "bash", "args": {"command": "env"}}),
]

ALLOWED_TOOLS = [
    ("claude", {"tool_name": "Read", "tool_input": {"file_path": "/repo/.env.example"}}),
    ("claude", {"tool_name": "Write", "tool_input": {"file_path": ".env", "content": "A=1"}}),
    ("claude", {"tool_name": "Glob", "tool_input": {"pattern": "**/.env*"}}),
    ("claude", {"tool_name": "Grep", "tool_input": {"pattern": "KEY", "glob": "*.py"}}),
    ("codex", {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}),
    ("opencode", {"tool": "read", "args": {"filePath": "/repo/README.md"}}),
    ("opencode", {"tool": "glob", "args": {"pattern": ".env*"}}),
]


def claude_event(command: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def codex_event(command: str) -> dict:
    return {**claude_event(command), "turn_id": "t1"}


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


def test_blocks_secret_reads() -> None:
    missed = [c for c in BLOCKED_COMMANDS if guard.check_shell(c, Path(".")) is None]
    assert missed == []


def test_allows_other_commands() -> None:
    blocked = {c: guard.check_shell(c, Path(".")) for c in ALLOWED_COMMANDS}
    assert {c: why for c, why in blocked.items() if why} == {}


def test_unbalanced_quotes_fall_back_to_a_word_scan() -> None:
    assert guard.check_shell("cat .env 'oops", Path(".")) is not None
    assert guard.check_shell("echo 'oops", Path(".")) is None


def test_cli_blocks_with_one_reason_line_per_harness() -> None:
    for harness, event in EVENTS.items():
        run = run_guard(harness, event("cat .env"))
        assert run.returncode == guard.EXIT_BLOCK, harness
        assert "ask the user" in run.stderr.lower()
        assert len(run.stderr.strip().splitlines()) == 1
        assert run.stdout == ""


def test_cli_allows_per_harness() -> None:
    for harness, event in EVENTS.items():
        run = run_guard(harness, event("cat .env.example"))
        assert (run.returncode, run.stderr) == (guard.EXIT_ALLOW, ""), harness


def test_blocks_secret_tools() -> None:
    for harness, event in BLOCKED_TOOLS:
        assert run_guard(harness, event).returncode == guard.EXIT_BLOCK, event


def test_allows_other_tools() -> None:
    for harness, event in ALLOWED_TOOLS:
        assert run_guard(harness, event).returncode == guard.EXIT_ALLOW, event


def test_bad_input_fails_open_with_exit_3() -> None:
    for harness, stdin in [("claude", "not json"), ("claude", "[]"), ("opencode", "{}")]:
        run = run_guard(harness, stdin)
        assert run.returncode == guard.EXIT_BAD_INPUT, stdin
        assert "stdin is not" in run.stderr


def test_usage_error_does_not_look_like_a_block() -> None:
    run = run_guard("cursor", claude_event("cat .env"))
    assert run.returncode == pr_merge_guard.EXIT_USAGE
    assert run.stderr.strip().endswith("'opencode')") and "secret_read_guard:" in run.stderr


def test_help_is_short_and_names_exit_codes() -> None:
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=True
    )
    assert "Exit:" in run.stdout and "Examples:" in run.stdout
    assert len(run.stdout.splitlines()) <= 25


def test_codex_toml_parses_next_to_the_merge_guard() -> None:
    secret = pr_merge_guard.codex_hook_toml(
        'python3 "/r/secret_read_guard.py" --harness codex', guard.HOOK_MATCHER, guard.HOOK_STATUS
    )
    merge = pr_merge_guard.codex_hook_toml('python3 "/r/pr_merge_guard.py" --harness codex')
    entries = tomllib.loads(f"{merge}\n\n{secret}")["hooks"]["PreToolUse"]
    assert [e["matcher"] for e in entries] == [pr_merge_guard.HOOK_MATCHER, guard.HOOK_MATCHER]
    assert entries[1]["hooks"][0]["statusMessage"] == guard.HOOK_STATUS


def test_opencode_plugin_blocks_via_both_apis() -> None:
    if shutil.which("node") is None:
        return  # CI installs Node for the Mermaid check; locally it is optional
    probe = f"""
import plugin from {json.dumps(PLUGIN.as_uri())};
const results = [];
const v1 = await plugin.server({{ directory: process.cwd() }});
for (const [tool, args] of [["bash", {{ command: "cat .env" }}],
                            ["read", {{ filePath: "/home/me/.netrc" }}],
                            ["bash", {{ command: "cat .env.example" }}]]) {{
  try {{ await v1["tool.execute.before"]({{ tool }}, {{ args }}); results.push("allow"); }}
  catch (e) {{ results.push(e.message.includes("ask the user") ? "block" : "error"); }}
}}
let hook;
await plugin.setup({{ directory: process.cwd(), tool: {{ hook: async (name, cb) => {{ hook = cb; }} }} }});
try {{ await hook({{ tool: "bash", input: {{ command: "printenv" }} }}); results.push("allow"); }}
catch (e) {{ results.push("block"); }}
console.log(JSON.stringify([plugin.id, results]));
"""
    run = subprocess.run(
        ["node", "--input-type=module", "-e", probe], capture_output=True, text=True, check=True
    )
    plugin_id, results = json.loads(run.stdout)
    assert plugin_id.endswith("secret-read-guard")
    assert results == ["block", "block", "allow", "block"]


def test_plugin_hooks_json_carries_the_guard_entry() -> None:
    hooks = json.loads((SECRET_GUARD_PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/secret_read_guard.py" --harness claude'
    entry = pr_merge_guard.claude_hook_entry(command, guard.HOOK_MATCHER)
    assert hooks == {"hooks": {"PreToolUse": [entry]}}


def test_plugin_hook_command_blocks_from_the_plugin_root() -> None:
    # Claude copies the plugin into its cache and dereferences these symlinks,
    # so the plugin must carry the merge guard module the script imports.
    scripts = SECRET_GUARD_PLUGIN / "scripts"
    assert (scripts / "secret_read_guard.py").resolve() == SCRIPT
    assert (scripts / "pr_merge_guard.py").resolve() == SCRIPT.parent / "pr_merge_guard.py"
    hooks = json.loads((SECRET_GUARD_PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    command = command.replace("python3", shlex.quote(sys.executable), 1)
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(SECRET_GUARD_PLUGIN)}
    for shell_command, expected in [("cat .env", guard.EXIT_BLOCK), ("ls", guard.EXIT_ALLOW)]:
        run = subprocess.run(
            ["sh", "-c", command],
            input=json.dumps(claude_event(shell_command)),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == expected, (shell_command, run.stderr)
