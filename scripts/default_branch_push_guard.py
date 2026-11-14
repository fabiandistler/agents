#!/usr/bin/env python3
"""Block agent runs from writing to the default branch: a model-free pre-tool hook.

An agent run in CI pushes with a token that may write to every branch, and not
every repository protects its default branch with a ruleset. This script runs in
the run's `PreToolUse` hook, reads the pending tool call as JSON on stdin and
blocks it when it would update the default branch on the remote. The block
reason tells the agent to push its own branch and open a pull request.

Blocked, for the branch named by `--default-branch` (read as git reads a
branch, so `refs/heads/main` is `main`; without it, or with an empty value or
an unfilled `{{...}}` placeholder: `main` and `master`):
- `git push` with a refspec or bare branch argument that resolves to the
  default branch, also `+`-forced, `refs/heads/` and wildcard forms, and with
  `--delete`; `git push --all`, `--branches` and `--mirror`.
- `git push` with an argument the parser cannot read (a shell variable, a
  command substitution, unbalanced quotes): it fails closed. So does a
  command the parser cannot split at all (bash accepts `$'it\\'s'`, shlex
  does not) when it holds `git push`, or `gh` or `curl` with one of the
  endpoints below, read or write.
- `gh api` or `curl` writes (POST, PATCH, PUT, DELETE) to
  `repos/<o>/<r>/git/refs/heads/<default>`, to `repos/<o>/<r>/contents/<path>`
  without a `branch` field naming another branch, and to `repos/<o>/<r>/merges`
  with base `<default>` or no base.
- MCP tools named `push_files`, `create_or_update_file` or `delete_file` whose
  `branch` is the default branch or missing.

Everything else passes, including `git push origin agent/issue-12`. The hook
cannot see which branch is checked out, so a bare `git push`, `git push origin`
and `git push -u origin HEAD` pass: on the default branch they would update it.

`scripts/agent_run_settings.json` is the Claude Code settings fragment that
loads this guard and the merge guard for an agent run.
`scripts/agent_run_settings.py` replaces `{{factory_dir}}` with the
shell-quoted absolute path of the factory checkout and `{{default_branch}}`
with the shell-quoted default branch. A branch given there
replaces the `main`/`master` fallback, so the workflow passes the repository's
real default branch. This repository's own `.claude/settings.json` does not
load the guard.

Reuses the merge guard's shell parser. Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from fnmatch import fnmatchcase
from pathlib import Path

from pr_merge_guard import (
    EXIT_ALLOW,
    EXIT_BAD_INPUT,
    EXIT_BLOCK,
    HARNESSES,
    SHELLS,
    UsageError,
    flag_values,
    parse_event,
    positionals,
    read_side_file,
    shell_script,
    split_heredocs,
    split_simple_commands,
    strip_prefixes,
)

HELP_EPILOG = """\
Input (stdin): claude, codex: the PreToolUse event, {"tool_name", "tool_input", "cwd"}.
  opencode: {"tool", "args", "cwd"}.
Exit: 0 allowed, 2 blocked (reason on stderr), 3 stdin is not a tool call,
  4 usage error. Every exit but 2 lets the tool call run.
Examples:
  echo '{"tool_name":"Bash","tool_input":{"command":"git push origin HEAD:main"}}' \\
    | python3 scripts/default_branch_push_guard.py --harness claude
  echo '{"tool_name":"Bash","tool_input":{"command":"git push origin trunk"}}' \\
    | python3 scripts/default_branch_push_guard.py --harness claude --default-branch trunk
"""

REASON = (
    "Blocked by default_branch_push_guard: {what}. Agent runs must not write to "
    "the default branch ({branches}). Push your own branch and open a pull "
    "request instead. Do not retry or work around this check."
)

FALLBACK_DEFAULT_BRANCHES = ("main", "master")

PUSH_MCP_TOOL = re.compile(r"(?:^|_)(push_files|create_or_update_file|delete_file)$")
REPO = r"(?:^|/)repos/[^/\s]+/[^/\s]+"
REF_PATH = re.compile(REPO + r"/git/refs/heads/(.+)$")
CONTENTS_PATH = re.compile(REPO + r"/contents(?:/.*)?$")
MERGES_PATH = re.compile(REPO + r"/merges$")
READ_METHODS = {"GET", "HEAD"}
# The endpoints above, matched in raw text when the command cannot be parsed.
UNPARSED_BRANCH_WRITE = re.compile(r"repos/[^/\s]+/[^/\s]+/(?:git/refs|contents|merges)\b")

# git options before the subcommand that take a separate value (`git -C dir push`).
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
PUSH_VALUE_OPTIONS = {"--repo", "-o", "--push-option", "--receive-pack", "--exec"}
# git accepts any unambiguous prefix of a long option, so `--mir` is `--mirror`.
PUSH_ALL_OPTIONS = ("--all", "--branches", "--mirror")
REDIRECTION = re.compile(r"^\d*[<>&]+$")

GH_API_VALUE_FLAGS = {
    "-X", "--method", "-H", "--header", "-f", "--raw-field", "-F", "--field",
    "--input", "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview",
}  # fmt: skip
GH_API_FIELD_FLAGS = {"-f", "--raw-field", "-F", "--field"}
GH_API_BODY_FLAGS = GH_API_FIELD_FLAGS | {"--input"}
CURL_DATA_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--json"}


def branch_name(ref: str) -> str:
    """A branch as git resolves a push destination: `refs/heads/x` and `heads/x` are `x`."""
    return ref.removeprefix("refs/").removeprefix("heads/")


def protected_branches(option: str | None) -> tuple[str, ...]:
    """The branches to protect, read from `--default-branch` as git reads a branch.

    Unset, empty or an unfilled `{{...}}` placeholder protects `main` and
    `master`: a workflow that fails to fill the option must not turn the brake off.
    """
    value = (option or "").strip()
    if not value or "{{" in value or "}}" in value:
        return FALLBACK_DEFAULT_BRANCHES
    return (branch_name(value),)


def names_default(ref: str, defaults: tuple[str, ...]) -> bool:
    name = branch_name(ref)
    return any(fnmatchcase(default, name) for default in defaults)


def unreadable(word: str) -> bool:
    """A word the shell would expand before git sees it."""
    return "$" in word or "`" in word


def git_subcommand(args: list[str]) -> tuple[str, list[str]] | None:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_VALUE_OPTIONS else 1
    return (args[i], args[i + 1 :]) if i < len(args) else None


def check_git_push(args: list[str], defaults: tuple[str, ...]) -> str | None:
    words: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
        elif REDIRECTION.match(arg):
            skip = True  # the redirection target
        elif unreadable(arg):
            return f"`git push` has an argument the guard cannot read ({arg!r})"
        elif arg in PUSH_VALUE_OPTIONS:
            skip = True
        elif arg.startswith("--") and len(arg) > 2:
            if any(option.startswith(arg) for option in PUSH_ALL_OPTIONS):
                return f"`git push {arg}` pushes every branch, the default branch included"
        elif not arg.startswith("-"):
            words.append(arg)
    for refspec in words[1:]:  # words[0] is the remote
        source, _, destination = refspec.removeprefix("+").partition(":")
        if names_default(destination or source, defaults):
            return f"`git push` refspec {refspec!r} updates the default branch"
    return None


def body_text(value: str, cwd: Path) -> str:
    return read_side_file(value, cwd) if value.startswith("@") else value


def gh_api_field(args: list[str], name: str, raw: str, cwd: Path) -> list[str]:
    """Values of body field `name` in a `gh api` call: `-f name=x` or a JSON `--input`."""
    found = []
    for field in flag_values(args, GH_API_FIELD_FLAGS):
        key, _, value = field.partition("=")
        if key == name:
            found.append(body_text(value, cwd))
    for source in flag_values(args, {"--input"}):
        text = raw if source == "-" else read_side_file(source, cwd)
        found += json_field(text, name)
    return found


def json_field(text: str, name: str) -> list[str]:
    return re.findall(rf'"{re.escape(name)}"\s*:\s*"([^"]*)"', text)


def check_endpoint(path: str, method: str, field, defaults: tuple[str, ...]) -> str | None:
    """Why a REST write to `path` updates the default branch; `field(name)` reads the body."""
    if method in READ_METHODS:
        return None
    if match := REF_PATH.search(path):
        ref = match.group(1)
        if unreadable(ref) or names_default(ref, defaults):
            return f"{method} {path} updates the default branch ref"
    if CONTENTS_PATH.search(path):
        branches = field("branch")
        if not branches or any(names_default(b, defaults) or unreadable(b) for b in branches):
            return f"{method} {path} writes a file without a `branch` other than the default"
    if MERGES_PATH.search(path):
        bases = field("base")
        if not bases or any(names_default(b, defaults) or unreadable(b) for b in bases):
            return f"{method} {path} merges into the default branch"
    return None


def api_path(url: str) -> str:
    return re.sub(r"^https?://[^/]+", "", url).split("?", 1)[0].rstrip("/")


def check_gh_api(args: list[str], raw: str, cwd: Path, defaults: tuple[str, ...]) -> str | None:
    endpoints = positionals(args, GH_API_VALUE_FLAGS)
    if not endpoints:
        return None
    methods = [m.upper() for m in flag_values(args, {"-X", "--method"})]
    sends_body = any(a in GH_API_BODY_FLAGS or a.startswith("--field=") for a in args)
    method = methods[-1] if methods else ("POST" if sends_body else "GET")
    reason = check_endpoint(
        api_path(endpoints[0]), method, lambda name: gh_api_field(args, name, raw, cwd), defaults
    )
    return f"`gh api` {reason}" if reason else None


def check_curl(args: list[str], cwd: Path, defaults: tuple[str, ...]) -> str | None:
    methods = [m.upper() for m in flag_values(args, {"-X", "--request"})]
    data = [body_text(v, cwd) for v in flag_values(args, CURL_DATA_FLAGS)]
    method = methods[-1] if methods else ("POST" if data else "GET")

    def field(name: str) -> list[str]:
        return [value for text in data for value in json_field(text, name)]

    for arg in args:
        if reason := check_endpoint(api_path(arg), method, field, defaults):
            return f"`curl` {reason}"
    return None


def check_argv(
    argv: list[str], raw: str, cwd: Path, defaults: tuple[str, ...], depth: int
) -> str | None:
    argv = strip_prefixes(argv)
    if not argv:
        return None
    program, args = Path(argv[0]).name, argv[1:]
    if program in SHELLS and (script := shell_script(args)) is not None:
        return check_shell(script, cwd, defaults, depth + 1)
    if program == "eval":
        return check_shell(" ".join(args), cwd, defaults, depth + 1)
    if program == "git" and (sub := git_subcommand(args)) and sub[0] == "push":
        return check_git_push(sub[1], defaults)
    if program == "gh":
        words = positionals(args, {"-R", "--repo", "--hostname"})
        if words[:1] == ["api"]:
            return check_gh_api(args[args.index("api") + 1 :], raw, cwd, defaults)
    if program == "curl":
        return check_curl(args, cwd, defaults)
    return None


def check_shell(command: str, cwd: Path, defaults: tuple[str, ...], depth: int = 0) -> str | None:
    """Return why a shell command writes to the default branch, or None."""
    if depth > 3:
        return None
    text, shell_bodies = split_heredocs(command)
    for body in shell_bodies:
        if reason := check_shell(body, cwd, defaults, depth + 1):
            return reason
    try:
        simple_commands = split_simple_commands(text, keep_expansions=True)
    except ValueError:
        # shlex rejects some text bash runs (`$'it\'s'`), so fail closed coarsely.
        if re.search(r"\bgit\b.*\bpush\b", text, re.DOTALL):
            return "`git push` in a command the guard cannot parse"
        if re.search(r"\b(?:gh|curl)\b", text) and UNPARSED_BRANCH_WRITE.search(text):
            return "a `gh api` or `curl` call to a branch-writing endpoint the guard cannot parse"
        return None
    for argv in simple_commands:
        if reason := check_argv(argv, command, cwd, defaults, depth):
            return reason
    return None


def check_tool_call(
    tool: str, tool_input: object, cwd: Path, defaults: tuple[str, ...]
) -> str | None:
    """Return why a tool call writes to the default branch, or None when it may run."""
    if PUSH_MCP_TOOL.search(tool):
        branch = tool_input.get("branch") if isinstance(tool_input, dict) else None
        if not isinstance(branch, str) or not branch or names_default(branch, defaults):
            return f"the tool `{tool}` writes to the default branch or names no branch"
        return None
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, list) and all(isinstance(c, str) for c in command):
            command = shlex.join(command)
        if isinstance(command, str):
            return check_shell(command, cwd, defaults)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = UsageError(
        prog="default_branch_push_guard.py",
        description="Block agent runs from writing to the default branch (pre-tool hook).",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--harness", required=True, choices=HARNESSES, help="input format")
    parser.add_argument(
        "--default-branch",
        help="the repository's default branch; unset, empty or an unfilled {{...}} "
        "placeholder blocks both main and master",
    )
    args = parser.parse_args(argv)
    defaults = protected_branches(args.default_branch)
    try:
        tool, tool_input, cwd = parse_event(args.harness, json.loads(sys.stdin.read()))
    except (ValueError, TypeError) as err:
        sys.stderr.write(
            f"default_branch_push_guard: stdin is not a {args.harness} tool call: {err}\n"
        )
        return EXIT_BAD_INPUT
    reason = check_tool_call(tool, tool_input, cwd, defaults)
    if reason is None:
        return EXIT_ALLOW
    sys.stderr.write(REASON.format(what=reason, branches=", ".join(defaults)) + "\n")
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
