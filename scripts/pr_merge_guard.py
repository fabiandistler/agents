#!/usr/bin/env python3
"""Block coding agents from merging pull requests: a model-free pre-tool hook.

Agents act under the owner's GitHub account, so branch rules and required
approvals do not stop them from merging their own PRs. This script runs in
each harness's pre-tool-call hook (Claude Code and Codex CLI `PreToolUse`, the
opencode plugin `scripts/opencode/pr-merge-guard.js`), reads the pending tool call as JSON on
stdin and blocks it when it would merge a PR or turn on auto-merge. The block
reason tells the agent to hand the merge to the human.

Blocked: `gh pr merge`; `gh api` (or curl) writes to `repos/<o>/<r>/pulls/<n>/merge`
or `repos/<o>/<r>/merges`; the GraphQL mutations `mergePullRequest`,
`enablePullRequestAutoMerge` and `enqueuePullRequest`; and MCP tools named
`merge_pull_request` or `enable_pr_auto_merge`. GitHub has no REST endpoint for
auto-merge. Everything else passes, including `gh pr view` and a local `git merge`.

The module also owns the hook entry the harness configs carry (matcher and
command), so `scripts/build_project_claude.py` and `install.sh` write the same
entry. Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import NoReturn

EXIT_ALLOW = 0
EXIT_BLOCK = 2  # Claude Code and Codex both block a PreToolUse call on exit 2
EXIT_BAD_INPUT = 3
EXIT_USAGE = 4
HARNESSES = ("claude", "codex", "opencode")

HELP_EPILOG = """\
Input (stdin): claude, codex: the PreToolUse event, {"tool_name", "tool_input", "cwd"}.
  opencode: {"tool", "args", "cwd"}, as sent by scripts/opencode/pr-merge-guard.js.
Exit: 0 allowed, 2 blocked (reason on stderr), 3 stdin is not a tool call,
  4 usage error. Every exit but 2 lets the tool call run.
Examples:
  echo '{"tool_name":"Bash","tool_input":{"command":"gh pr merge 7"}}' \\
    | python3 scripts/pr_merge_guard.py --harness claude
  echo '{"tool":"github_merge_pull_request","args":{}}' \\
    | python3 scripts/pr_merge_guard.py --harness opencode
"""

REASON = (
    "Blocked by pr_merge_guard: {what}. Merging pull requests and enabling "
    "auto-merge are reserved for the human owner. Stop here, report the PR and "
    "its CI status, and ask the user to review and merge it. Do not retry or "
    "work around this check."
)

# Hook entry shared by every config writer. Both Claude Code and Codex read
# `matcher` as a regex on the tool name; the script decides the rest.
HOOK_MATCHER = "^(Bash|mcp__.*)$"
# Identifies our entry in a settings file that cannot carry marker comments.
HOOK_ID = "pr_merge_guard.py"

MERGE_MCP_TOOL = re.compile(r"(?:^|_)(merge_pull_request|enable_pr_auto_merge)$")
MERGE_MUTATION = re.compile(r"\b(mergePullRequest|enablePullRequestAutoMerge|enqueuePullRequest)\b")
PR_MERGE_PATH = re.compile(r"(?:^|/)repos/[^/\s]+/[^/\s]+/pulls/[^/\s]+/merge/?$")
BRANCH_MERGE_PATH = re.compile(r"(?:^|/)repos/[^/\s]+/[^/\s]+/merges/?$")
SEPARATORS = {";", "&", "&&", "|", "||", "|&", "\n", "(", ")", "`", "$", ";;"}
# Words that may precede the real command in a simple command.
PREFIX_WORDS = {"!", "{", "}", "then", "do", "else", "elif", "if", "while", "until"}
WRAPPERS = {
    "sudo",
    "env",
    "command",
    "exec",
    "time",
    "nohup",
    "nice",
    "xargs",
    "builtin",
    "timeout",
}
# Wrapper flags that take a value (`sudo -u root`, `xargs -I {}`, `nice -n 5`).
WRAPPER_VALUE_FLAGS = {"-u", "-g", "-C", "-I", "-n", "-P", "-L", "-s", "-E", "-d", "-k"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
SHELL_READS_STDIN = re.compile(r"^\s*(?:sudo\s+)?(?:\S*/)?(?:ba|z|da|k)?sh(?:\s+-s)?\s*$")
PIPED_TO_SHELL = re.compile(r"\|\s*(?:sudo\s+)?(?:\S*/)?(?:ba|z|da|k)?sh\b")
GH_VALUE_FLAGS = {"-R", "--repo", "--hostname"}
GH_API_VALUE_FLAGS = {
    "-X", "--method", "-H", "--header", "-f", "--raw-field", "-F", "--field",
    "--input", "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview",
}  # fmt: skip
GH_API_BODY_FLAGS = {"-f", "--raw-field", "-F", "--field", "--input"}
CURL_DATA_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--json"}


class UsageError(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"pr_merge_guard: {message}\n")
        sys.exit(EXIT_USAGE)


def split_simple_commands(command: str) -> list[list[str]]:
    """Tokenize shell text and split it at control operators and substitutions."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n`")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    commands: list[list[str]] = [[]]
    for token in lexer:
        if token in SEPARATORS or (token and set(token) <= set("();|&\n`")):
            commands.append([])
        else:
            commands[-1].append(token.removeprefix("$"))
    return [argv for argv in commands if argv]


def strip_prefixes(argv: list[str]) -> list[str]:
    """Drop variable assignments, shell keywords and wrappers before the command."""
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in PREFIX_WORDS or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
            i += 1
        elif Path(word).name in WRAPPERS:
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 2 if argv[i] in WRAPPER_VALUE_FLAGS else 1
            if Path(word).name == "timeout":
                i += 1  # the duration
        else:
            break
    return argv[i:]


def positionals(args: list[str], value_flags: set[str]) -> list[str]:
    found, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg in value_flags:
            skip = True
        elif not arg.startswith("-"):
            found.append(arg)
    return found


def flag_values(args: list[str], names: set[str]) -> list[str]:
    """Values of `--flag value`, `--flag=value` and `-Xvalue` occurrences."""
    values = []
    for i, arg in enumerate(args):
        for name in names:
            if arg == name and i + 1 < len(args):
                values.append(args[i + 1])
            elif name.startswith("--") and arg.startswith(name + "="):
                values.append(arg[len(name) + 1 :])
            elif len(name) == 2 and arg.startswith(name) and len(arg) > 2:
                values.append(arg[2:])
    return values


def read_side_file(value: str, cwd: Path) -> str:
    """Contents of an `@file` (or `--input file`) argument, if it is readable."""
    path = Path(value.removeprefix("@"))
    try:
        return (cwd / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check_gh_api(args: list[str], raw: str, cwd: Path) -> str | None:
    endpoints = positionals(args, GH_API_VALUE_FLAGS)
    if not endpoints:
        return None
    endpoint = endpoints[0].split("?", 1)[0].rstrip("/")
    methods = [m.upper() for m in flag_values(args, {"-X", "--method"})]
    sends_body = any(a in GH_API_BODY_FLAGS or a.startswith("--field=") for a in args)
    method = methods[-1] if methods else ("POST" if sends_body else "GET")
    if method not in {"GET", "HEAD"}:
        if PR_MERGE_PATH.search(endpoint):
            return "`gh api` merges a pull request (pulls/<n>/merge)"
        if BRANCH_MERGE_PATH.search(endpoint):
            return "`gh api` merges a branch (repos/<o>/<r>/merges)"
    if endpoint == "graphql":
        # The query may come from a file, a heredoc or a variable, so scan the
        # whole command text plus any file the call reads.
        texts = [raw]
        for value in flag_values(args, {"-f", "-F", "--field", "--raw-field"}):
            if "=@" in value:
                texts.append(read_side_file(value.split("=@", 1)[1], cwd))
        texts += [read_side_file(v, cwd) for v in flag_values(args, {"--input"}) if v != "-"]
        for text in texts:
            if match := MERGE_MUTATION.search(text):
                return f"`gh api graphql` runs the `{match.group(1)}` mutation"
    return None


def check_curl(args: list[str], raw: str) -> str | None:
    methods = [m.upper() for m in flag_values(args, {"-X", "--request"})]
    sends_body = any(a in CURL_DATA_FLAGS or a.split("=", 1)[0] in CURL_DATA_FLAGS for a in args)
    method = methods[-1] if methods else ("POST" if sends_body else "GET")
    for arg in args:
        path = re.sub(r"^https?://[^/]+", "", arg).split("?", 1)[0].rstrip("/")
        if method != "GET" and (PR_MERGE_PATH.search(path) or BRANCH_MERGE_PATH.search(path)):
            return "`curl` calls a GitHub merge endpoint"
        if path.endswith("/graphql") and (match := MERGE_MUTATION.search(raw)):
            return f"`curl` runs the `{match.group(1)}` GraphQL mutation"
    return None


def check_argv(argv: list[str], raw: str, cwd: Path, depth: int) -> str | None:
    argv = strip_prefixes(argv)
    if not argv:
        return None
    program, args = Path(argv[0]).name, argv[1:]
    if program in SHELLS and "-c" in args and args.index("-c") + 1 < len(args):
        return check_shell(args[args.index("-c") + 1], cwd, depth + 1)
    if program == "eval":
        return check_shell(" ".join(args), cwd, depth + 1)
    if program == "gh":
        words = positionals(args, GH_VALUE_FLAGS)
        if words[:2] == ["pr", "merge"]:
            return "`gh pr merge` merges a pull request or enables auto-merge"
        if words[:1] == ["api"]:
            return check_gh_api(args[args.index("api") + 1 :], raw, cwd)
    if program == "curl":
        return check_curl(args, raw)
    return None


def split_heredocs(command: str) -> tuple[str, list[str]]:
    """Command text without heredoc bodies, plus the bodies a shell would run.

    A heredoc body is data for the command that reads it (a Python script, a
    commit message), not shell code, so it is not parsed as commands. Only a
    body fed to a shell (`bash <<EOF`) is returned for checking.
    """
    lines = command.split("\n")
    kept: list[str] = []
    shell_bodies: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        for match in HEREDOC.finditer(line):
            end, body = match.group(2), []
            while i < len(lines) and lines[i].strip() != end:
                body.append(lines[i])
                i += 1
            i += 1  # the terminator line
            if SHELL_READS_STDIN.match(line[: match.start()]) or PIPED_TO_SHELL.search(
                line[match.end() :]
            ):
                shell_bodies.append("\n".join(body))
    return "\n".join(kept), shell_bodies


def check_shell(command: str, cwd: Path, depth: int = 0) -> str | None:
    """Return why a shell command merges a PR, or None when it does not."""
    if depth > 3:
        return None
    text, shell_bodies = split_heredocs(command)
    for body in shell_bodies:
        if reason := check_shell(body, cwd, depth + 1):
            return reason
    try:
        simple_commands = split_simple_commands(text)
    except ValueError:
        # Unbalanced quotes: the shell would reject the command too. Fall back
        # to a coarse scan of the text.
        if re.search(r"\bgh\b[^\n;|&]*\bpr\s+merge\b", text):
            return "`gh pr merge` merges a pull request or enables auto-merge"
        if "graphql" in command and (match := MERGE_MUTATION.search(command)):
            return f"a GraphQL call runs the `{match.group(1)}` mutation"
        return None
    for argv in simple_commands:
        # The full text, heredoc bodies included: a GraphQL query often comes
        # in through one.
        if reason := check_argv(argv, command, cwd, depth):
            return reason
    return None


def check_tool_call(tool: str, tool_input: object, cwd: Path) -> str | None:
    """Return why a tool call merges a PR, or None when it may run."""
    if MERGE_MCP_TOOL.search(tool):
        return f"the tool `{tool}` merges a pull request or enables auto-merge"
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, list) and all(isinstance(c, str) for c in command):
            command = shlex.join(command)
        if isinstance(command, str):
            return check_shell(command, cwd)
    return None


def parse_event(harness: str, event: object) -> tuple[str, object, Path]:
    if not isinstance(event, dict):
        raise TypeError("stdin JSON is not an object")
    name_key, input_key = ("tool", "args") if harness == "opencode" else ("tool_name", "tool_input")
    tool = event.get(name_key)
    if not isinstance(tool, str):
        raise TypeError(f"field {name_key!r} is missing or not a string")
    cwd = event.get("cwd")
    return tool, event.get(input_key), Path(cwd if isinstance(cwd, str) else ".")


# --- Hook entry for the harness configs --------------------------------------


def claude_hook_entry(command: str) -> dict:
    return {"matcher": HOOK_MATCHER, "hooks": [{"type": "command", "command": command}]}


def is_guard_entry(entry: object) -> bool:
    hooks = entry.get("hooks") if isinstance(entry, dict) else None
    return isinstance(hooks, list) and any(
        isinstance(h, dict) and HOOK_ID in str(h.get("command", "")) for h in hooks
    )


def without_claude_hook(settings: dict) -> dict:
    """Settings with every guard entry removed from hooks.PreToolUse."""
    settings = json.loads(json.dumps(settings))
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict) or not isinstance(hooks.get("PreToolUse"), list):
        return settings
    hooks["PreToolUse"] = [e for e in hooks["PreToolUse"] if not is_guard_entry(e)]
    if not hooks["PreToolUse"]:
        del hooks["PreToolUse"]
    if not hooks:
        del settings["hooks"]
    return settings


def with_claude_hook(settings: dict, command: str) -> dict:
    """Settings whose hooks.PreToolUse holds exactly one guard entry for `command`."""
    settings = without_claude_hook(settings)
    hooks = settings.setdefault("hooks", {})
    hooks.setdefault("PreToolUse", []).append(claude_hook_entry(command))
    return settings


def codex_hook_toml(command: str) -> str:
    """Inline `[hooks]` tables for ~/.codex/config.toml."""
    if "'" in command:
        raise ValueError("command must not contain a single quote")
    return (
        f'[[hooks.PreToolUse]]\nmatcher = "{HOOK_MATCHER}"\n\n'
        f"[[hooks.PreToolUse.hooks]]\ntype = \"command\"\ncommand = '{command}'\n"
        'statusMessage = "Checking for PR merges"'
    )


def main(argv: list[str] | None = None) -> int:
    parser = UsageError(
        prog="pr_merge_guard.py",
        description="Block coding agents from merging pull requests (pre-tool hook).",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--harness", required=True, choices=HARNESSES, help="input format")
    args = parser.parse_args(argv)
    try:
        tool, tool_input, cwd = parse_event(args.harness, json.loads(sys.stdin.read()))
    except (ValueError, TypeError) as err:
        sys.stderr.write(f"pr_merge_guard: stdin is not a {args.harness} tool call: {err}\n")
        return EXIT_BAD_INPUT
    reason = check_tool_call(tool, tool_input, cwd)
    if reason is None:
        return EXIT_ALLOW
    sys.stderr.write(REASON.format(what=reason) + "\n")
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
