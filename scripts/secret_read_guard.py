#!/usr/bin/env python3
"""Block coding agents from reading credential files: a model-free pre-tool hook.

Whatever a tool call prints lands in the agent's context and transcript, so a
`cat .env` hands every secret in it to the model and the session log. This
script runs in each harness's pre-tool-call hook (Claude Code and Codex CLI
`PreToolUse`, the opencode plugin `scripts/opencode/secret-read-guard.js`),
reads the pending tool call as JSON on stdin and blocks it when it would read a
credential file or dump the environment. The block reason tells the agent to
ask the user instead.

Blocked: reading dotenv files (`.env`, `.env.*`, `*.env`, but not their
`example`, `sample` and `template` variants), `.Renviron`, `.git-credentials`,
`.netrc`, `.npmrc`, `.pypirc`, `.envrc`, `.claude.json` and its copies,
`gh/hosts.yml`, `.aws/credentials`, `.docker/config.json`, `.kube/config`,
`rclone/rclone.conf*`, private SSH keys, pyicloud sessions, the Claude, Codex,
opencode, Gemini, Azure, Kaggle and Todoist CLI credential files, the `pass`
store and gpg secret keys (also via `gopass`, `sops -d`), through a shell
command or a file tool (Read, Edit, Grep, MCP tools with a path); dumping the
environment with bare `env`, `printenv`,
`export -p`, `declare -x`/`-p`, bare `set` or `/proc/<pid>/environ`.
Allowed: `env FOO=bar cmd` (a launcher), `printenv NAME` for a name that does
not look secret, commands that only name a file (`ls`, `rm`, `git add`,
`source`, `--env-file`), and writing one (`cp .env.example .env`).

Reuses the merge guard's shell parser. Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from pr_merge_guard import (
    EXIT_ALLOW,
    EXIT_BAD_INPUT,
    EXIT_BLOCK,
    HARNESSES,
    SHELLS,
    UsageError,
    parse_event,
    positionals,
    split_heredocs,
    split_simple_commands,
    strip_prefixes,
)

HELP_EPILOG = """\
Input (stdin): claude, codex: the PreToolUse event, {"tool_name", "tool_input", "cwd"}.
  opencode: {"tool", "args", "cwd"}, as sent by scripts/opencode/secret-read-guard.js.
Exit: 0 allowed, 2 blocked (reason on stderr), 3 stdin is not a tool call,
  4 usage error. Every exit but 2 lets the tool call run.
Examples:
  echo '{"tool_name":"Bash","tool_input":{"command":"cat .env"}}' \\
    | python3 scripts/secret_read_guard.py --harness claude
  echo '{"tool":"read","args":{"filePath":"/home/me/.ssh/id_ed25519"}}' \\
    | python3 scripts/secret_read_guard.py --harness opencode
"""

REASON = (
    "Blocked by secret_read_guard: {what}. Secret values must not enter the "
    "agent's context, so ask the user to run the command themselves or to provide "
    "a sanitized value. Do not retry or work around this check."
)

HOOK_MATCHER = "^(Bash|Read|Edit|Grep|mcp__.*)$"
HOOK_STATUS = "Checking for secret reads"

DOTENV_TEMPLATES = {"example", "sample", "template"}
# Blocked even where a copy holds no secret (a registry-only .npmrc, a local
# kubeconfig): an over-block costs one question, a leaked token a rotation.
SECRET_NAMES = {
    ".Renviron", ".git-credentials", ".netrc", ".npmrc", ".pypirc", ".envrc", ".claude.json",
}  # fmt: skip
# (parent directory, file name) pairs.
SECRET_FILES = {
    ("gh", "hosts.yml"): "GitHub CLI credentials",
    (".aws", "credentials"): "AWS credentials",
    (".docker", "config.json"): "Docker registry credentials",
    (".kube", "config"): "a kubeconfig",
    (".claude", ".credentials.json"): "Claude Code credentials",
    (".codex", "auth.json"): "Codex credentials",
    ("opencode", "auth.json"): "opencode credentials",
    ("opencode", "mcp-auth.json"): "opencode MCP credentials",
    (".gemini", "oauth_creds.json"): "Gemini CLI credentials",
    (".gemini", "gemini-credentials.json"): "Gemini CLI credentials",
    (".azure", "msal_token_cache.json"): "Azure CLI tokens",
    (".azure", "msal_http_cache.bin"): "Azure CLI tokens",
    # The Kaggle CLI uses $XDG_CONFIG_HOME/kaggle where ~/.kaggle does not exist.
    (".kaggle", "kaggle.json"): "Kaggle credentials",
    (".kaggle", "access_token"): "Kaggle credentials",
    ("kaggle", "kaggle.json"): "Kaggle credentials",
    ("kaggle", "access_token"): "Kaggle credentials",
    ("todoist-cli", "config.json"): "Todoist CLI credentials",
}
# Names a glob is tried against, so `cat ~/.ssh/*` counts as reading id_rsa.
# The last three stand for the names that secret_file() matches by prefix.
GLOB_PROBES = (
    [".env", ".env.local", "id_rsa", "id_ed25519", *SECRET_NAMES]
    + [name for _, name in SECRET_FILES]
    + [".claude.json.backup", "rclone.conf", "rclone.conf.backup"]
)
PROC_ENVIRON = re.compile(r"(?:^|/)proc/[^/]+/environ$")
GLOB_CHARS = re.compile(r"[*?\[]")

# Commands that take a secret file's name without printing its contents.
NAME_ONLY_COMMANDS = {
    "ls", "rm", "touch", "stat", "test", "[", "chmod", "chown", "mkdir", "unlink",
    "realpath", "readlink", "basename", "dirname", "file", "echo", "printf", "cd",
    "find", "source", ".", "ssh", "ssh-add", "ssh-keygen",
}  # fmt: skip
GIT_NAME_ONLY = {"add", "rm", "mv", "check-ignore", "ls-files", "status"}
# Tools that only list or write files, so a secret path in them reveals nothing.
NAME_ONLY_TOOLS = {"write", "glob", "list", "ls"}
PATH_KEYS = ("file_path", "filePath", "path", "notebook_path")
GREP_FILTER_KEYS = ("glob", "include")
PASS_LISTING = {"find", "search", "help", "version", "git", "init", "sync"}
PASS_STORES = {"pass", "gopass"}
SOPS_DECRYPT = {"-d", "--decrypt", "decrypt"}
GPG_SECRET_FLAGS = {"-d", "--decrypt", "--decrypt-files"}
SECRET_VAR_PARTS = (
    "TOKEN", "SECRET", "KEY", "PASSWORD", "PASSWD", "PASS", "PAT", "CREDENTIAL",
    "CREDENTIALS", "AUTH", "COOKIE",
)  # fmt: skip


def secret_file(path: str) -> str | None:
    """Name the kind of credential file `path` points at, or None."""
    if not path or any(c.isspace() for c in path):
        return None  # prose (a commit message, a PR body), not a path
    if PROC_ENVIRON.search(path):
        return "a process environment (/proc/<pid>/environ)"
    parts = PurePosixPath(path).parts
    if not parts:
        return None  # "."
    # Every file under these directories is secret, so a glob in the name changes nothing.
    if ".password-store" in parts:
        return "the pass password store"
    if ".gnupg" in parts and "private-keys-v1.d" in parts:
        return "a gpg secret key"
    if any(part.startswith(".pyicloud") for part in parts):
        return "a pyicloud session file"
    name, parent = parts[-1], parts[-2] if len(parts) > 1 else ""
    if GLOB_CHARS.search(name):
        if name.endswith(".env"):
            # No probe stands for every `*.env` name, such as secrets.env.
            return "a dotenv file"
        # A shell glob skips dotfiles unless the pattern starts with a dot.
        probes = [p for p in GLOB_PROBES if name.startswith(".") or not p.startswith(".")]
        hits = (secret_file(f"{parent}/{p}") for p in probes if fnmatch(p, name))
        return next((hit for hit in hits if hit), None)
    if name.endswith(".env") and name.removesuffix(".env") not in DOTENV_TEMPLATES:
        return "a dotenv file"
    if name.startswith(".env.") and name.removeprefix(".env.") not in DOTENV_TEMPLATES:
        return "a dotenv file"
    if name in SECRET_NAMES:
        return f"`{name}`"
    if name.startswith(".claude.json"):
        return "a copy of Claude Code's `.claude.json`"
    if parent == "rclone" and name.startswith("rclone.conf"):
        return "rclone remote credentials"
    if (parent, name) in SECRET_FILES:
        return SECRET_FILES[(parent, name)]
    if parent == ".ssh" and name.startswith("id_") and not name.endswith(".pub"):
        return "an SSH private key"
    if ".gnupg" in parts and name == "secring.gpg":
        return "a gpg secret key"
    return None


def secret_var(name: str) -> bool:
    """Whether an environment variable name looks like it holds a secret."""
    return any(p.endswith(SECRET_VAR_PARTS) for p in re.split(r"[^A-Z0-9]+", name.upper()))


def check_env_dump(program: str, args: list[str]) -> str | None:
    names = [a for a in args if not a.startswith(("-", "+"))]
    if program == "printenv":
        if not names:
            return "`printenv` without a name dumps the environment"
        if any(secret_var(n) for n in names):
            return "`printenv` prints a variable whose name looks secret"
    if program == "export" and not names:
        return "`export` without a name lists the exported environment"
    if program in {"declare", "typeset"} and not any(re.match(r"-\w*[fF]", a) for a in args):
        if not names:
            return f"`{program}` without a name lists the environment"
        if any(secret_var(n) for n in names if "=" not in n):
            return f"`{program}` prints a variable whose name looks secret"
    if program == "set" and not args:
        return "`set` without arguments lists every shell variable"
    return None


def check_secret_store(program: str, args: list[str]) -> str | None:
    names = [a for a in args if not a.startswith("-")]
    listing = not names or names in (["ls"], ["list"]) or names[0] in PASS_LISTING
    if program in PASS_STORES and not listing:
        return f"`{program}` decrypts an entry of the password store"
    if program == "sops" and (SOPS_DECRYPT & set(args)):
        return "`sops` decrypts a file"
    if program in {"gpg", "gpg2"} and any(
        a in GPG_SECRET_FLAGS or a.startswith("--export-secret") for a in args
    ):
        return f"`{program}` decrypts data or exports a secret key"
    return None


def check_file_args(program: str, args: list[str]) -> str | None:
    if program in NAME_ONLY_COMMANDS:
        return None
    subcommand = positionals(args, {"-C", "-c"})[:1] if program == "git" else []
    if subcommand and subcommand[0] in GIT_NAME_ONLY:
        return None
    if program in {"cp", "mv"} and args:
        args = args[:-1]  # the destination is written, not read
    skip = False
    for word in args:
        if skip:
            skip = False
        elif word.endswith(">") or word == "--env-file":
            skip = True  # a redirect target or a file the program loads
        elif word.startswith("--env-file="):
            continue
        elif word.startswith("-") and "=" in word:
            # `--kubeconfig=~/.kube/config` names the file as an option value.
            if kind := secret_file(word.split("=", 1)[1]):
                return f"the command reads {kind}"
        elif not word.startswith("-") and (kind := secret_file(word)):
            return f"the command reads {kind}"
    return None


def check_argv(argv: list[str], cwd: Path, depth: int) -> str | None:
    words = strip_prefixes(argv)
    if not words:
        if any(Path(w).name == "env" for w in argv):
            return "`env` without a command dumps the environment"
        return None
    program, args = Path(words[0]).name, words[1:]
    if program in SHELLS and "-c" in args and args.index("-c") + 1 < len(args):
        return check_shell(args[args.index("-c") + 1], cwd, depth + 1)
    if program == "eval":
        return check_shell(" ".join(args), cwd, depth + 1)
    return (
        check_env_dump(program, args)
        or check_secret_store(program, args)
        or check_file_args(program, args)
    )


def check_shell(command: str, cwd: Path, depth: int = 0) -> str | None:
    """Return why a shell command reads a secret, or None when it does not."""
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
        # to a coarse scan of the words.
        words = re.split(r"[\s;|&()<>`'\"]+", text)
        kinds = (secret_file(w.removeprefix("$")) for w in words)
        return next((f"the command names {k}" for k in kinds if k), None)
    for argv in simple_commands:
        if reason := check_argv(argv, cwd, depth):
            return reason
    return None


def check_tool_call(tool: str, tool_input: object, cwd: Path) -> str | None:
    """Return why a tool call reads a secret, or None when it may run."""
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if isinstance(command, list) and all(isinstance(c, str) for c in command):
        command = shlex.join(command)
    if isinstance(command, str) and (reason := check_shell(command, cwd)):
        return reason
    if tool.rsplit("__", 1)[-1].lower() in NAME_ONLY_TOOLS:
        return None
    for key in PATH_KEYS + GREP_FILTER_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and (kind := secret_file(value)):
            return f"the tool `{tool}` reads {kind}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = UsageError(
        prog="secret_read_guard.py",
        description="Block coding agents from reading credential files (pre-tool hook).",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--harness", required=True, choices=HARNESSES, help="input format")
    args = parser.parse_args(argv)
    try:
        tool, tool_input, cwd = parse_event(args.harness, json.loads(sys.stdin.read()))
    except (ValueError, TypeError) as err:
        sys.stderr.write(f"secret_read_guard: stdin is not a {args.harness} tool call: {err}\n")
        return EXIT_BAD_INPUT
    reason = check_tool_call(tool, tool_input, cwd)
    if reason is None:
        return EXIT_ALLOW
    sys.stderr.write(REASON.format(what=reason) + "\n")
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
