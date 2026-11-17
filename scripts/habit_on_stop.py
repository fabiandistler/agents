#!/usr/bin/env python3
"""Coach the design smells a branch introduced: a Claude Code Stop hook.

Runs ruff with the design rules of Habit Hooks' python plugin (complexity,
parameter count, function length, broad except) on each Python file the branch
changed since it forked from the default branch. A finding the fork point
already had is dropped, so old debt in a touched file stays quiet; a finding
whose message changed (complexity 12 -> 14) counts as new. The rest goes to
`habit-mapper` (https://github.com/habit-hooks/habit-hooks), which replaces
each finding with a coaching guide that asks for the design fix instead of the
smallest change that silences the rule.

Both sides of the comparison run through the same ruff binary from stdin, so a
ruff upgrade shifts both sides alike.

Exit 0: stop_hook_active is set, no changed Python file, or nothing new.
Exit 1: no fork point (a checkout without the default branch, such as the
factory's depth-1 rework checkout); the reason on stderr. Claude Code shows it
as a hook error and lets the agent stop, since the agent cannot repair it.
Exit 2: the guides, or what broke, on stderr. Claude Code then keeps the agent
working; on its next stop stop_hook_active is set and the hook lets it go.

Source: forge pass 17.11.2026 on Thoughtworks Tech Radar Vol. 35, blip
"Habit Hooks" (Tools, Assess). Review: Todoist "Abbau-Review habit-on-stop",
28.12.2026.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

EXIT_PASS = 0
EXIT_SKIP = 1  # non-blocking: Claude Code shows the error and lets the agent stop
EXIT_COACH = 2  # a Stop hook exiting 2 shows stderr to the agent and keeps it working

# Ruff code -> Habit Hooks smell, as in the python plugin's ruff.jq (1.5.0).
# F401 and F841 stay with lint-on-edit.sh, which already reports them per edit.
SMELL_OF_CODE = {
    "C901": "high-complexity",
    "PLR0913": "too-many-parameters",
    "PLR0915": "oversized-function",
    "BLE001": "swallowed-exception",
}
DEFAULT_BRANCH_REFS = ("origin/HEAD", "origin/main", "main")
INSTALL_HINT = "python3 -m pip install -r scripts/check_all.requirements.txt"


class HookError(Exception):
    """A tool or git state the hook needs is missing; the message says which."""


class NoForkPoint(HookError):
    """The checkout has no default branch, or no common history with it."""


def run_tool(argv: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess:
    """argv run in cwd, output captured; the caller reads the exit code."""
    return subprocess.run(  # noqa: S603 -- fixed argv from this module, no shell
        argv, cwd=cwd, input=stdin, capture_output=True, text=True, check=False
    )


def git(repo: Path, *args: str) -> str:
    completed = run_tool(["git", *args], repo)
    if completed.returncode != 0:
        raise HookError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def fork_point(repo: Path) -> str:
    """The commit where HEAD left the default branch."""
    for ref in DEFAULT_BRANCH_REFS:
        exists = run_tool(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], repo)
        if exists.returncode == 0:
            merge_base = run_tool(["git", "merge-base", "HEAD", ref], repo)
            if merge_base.returncode != 0:
                raise NoForkPoint(f"HEAD and {ref} share no history in this checkout")
            return merge_base.stdout.strip()
    raise NoForkPoint(
        f"no default branch to compare against (tried {', '.join(DEFAULT_BRANCH_REFS)})"
    )


def changed_python_files(repo: Path, base: str) -> dict[str, str | None]:
    """Python files changed since base, each mapped to its path at base.

    A renamed file maps to its old path, so its old findings stay old; an added
    or untracked file maps to None.
    """
    status = git(repo, "diff", "--name-status", "-M", "--diff-filter=AMR", base, "--", "*.py")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "--", "*.py")
    path_at_base: dict[str, str | None] = dict.fromkeys(untracked.splitlines())
    for line in status.splitlines():
        kind, *paths = line.split("\t")
        path_at_base[paths[-1]] = None if kind == "A" else paths[0]
    return {
        path: before for path, before in sorted(path_at_base.items()) if (repo / path).is_file()
    }


def ruff_findings(repo: Path, path: str, source: str) -> list[dict]:
    """Ruff's design-rule findings for source, linted as if it lived at path."""
    completed = run_tool(
        [
            "ruff",
            "check",
            "--no-cache",
            "--no-fix",
            "--force-exclude",
            "--output-format=json",
            f"--select={','.join(SMELL_OF_CODE)}",
            f"--stdin-filename={path}",
            "-",
        ],
        repo,
        stdin=source,
    )
    if completed.returncode not in (0, 1):
        raise HookError(f"ruff failed on {path}: {completed.stderr.strip()}")
    try:
        return json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as error:
        raise HookError(f"ruff printed no JSON for {path}: {error}") from error


def head_source(repo: Path, path: str) -> str:
    try:
        return (repo / path).read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise HookError(f"{path} is not UTF-8, so ruff cannot check it") from error


def introduced(head: list[dict], base: list[dict]) -> list[dict]:
    """Findings in head that base did not have, matched by rule and message.

    Line numbers move with every edit above a function, so they do not take
    part in the match; the message names the function (C901) or the count.
    """
    remaining = Counter((finding["code"], finding["message"]) for finding in base)
    new = []
    for finding in head:
        key = (finding["code"], finding["message"])
        if remaining[key]:
            remaining[key] -= 1
        else:
            new.append(finding)
    return new


def as_habit_findings(repo: Path, findings: list[dict]) -> list[dict]:
    """Ruff findings grouped into the findings array habit-mapper reads."""
    by_smell: dict[str, list[dict]] = {}
    for finding in findings:
        file = os.path.relpath(finding["filename"], repo)
        by_smell.setdefault(SMELL_OF_CODE[finding["code"]], []).append(
            {
                "key": file,
                "details": {
                    "file": file,
                    "line": finding["location"]["row"],
                    "column": finding["location"]["column"],
                    "message": finding["message"],
                    "source": f"ruff:{finding['code']}",
                },
            }
        )
    return [
        {"smell": smell, "language": "python", "details": {}, "issues": issues}
        for smell, issues in sorted(by_smell.items())
    ]


def new_findings(repo: Path) -> list[dict]:
    base = fork_point(repo)
    found = []
    for path, path_at_base in changed_python_files(repo, base).items():
        head = ruff_findings(repo, path, head_source(repo, path))
        if not head:
            continue
        before = (
            []
            if path_at_base is None
            else ruff_findings(repo, path, git(repo, "show", f"{base}:{path_at_base}"))
        )
        found += introduced(head, before)
    return found


def coaching(repo: Path, findings: list[dict]) -> str | None:
    """habit-mapper's guides for findings, or None when it lets them pass."""
    completed = run_tool(
        ["habit-mapper"], repo, stdin=json.dumps(as_habit_findings(repo, findings))
    )
    if completed.returncode == 0:
        return None
    if completed.returncode == 1:
        return completed.stdout.strip() or completed.stderr.strip()
    raise HookError(f"habit-mapper failed: {completed.stderr.strip() or completed.stdout.strip()}")


def run(event: dict, repo: Path) -> tuple[int, str]:
    if event.get("stop_hook_active"):
        return EXIT_PASS, ""
    missing = [tool for tool in ("ruff", "habit-mapper") if shutil.which(tool) is None]
    if missing:
        return EXIT_COACH, f"habit-on-stop: MISSING {', '.join(missing)}: {INSTALL_HINT}"
    try:
        findings = new_findings(repo)
        guides = coaching(repo, findings) if findings else None
    except NoForkPoint as error:
        return EXIT_SKIP, f"habit-on-stop: skipped: {error}"
    except HookError as error:
        return EXIT_COACH, f"habit-on-stop: {error}"
    if guides is None:
        return EXIT_PASS, ""
    return EXIT_COACH, (
        "habit-on-stop: this branch added design smells. Fix the design each "
        "guide describes; do not silence the rule with noqa.\n\n" + guides
    )


def main() -> int:
    event = json.load(sys.stdin)
    start = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or Path.cwd())
    try:
        repo = Path(git(start, "rev-parse", "--show-toplevel").strip())
    except HookError as error:
        print(f"habit-on-stop: skipped: {error}", file=sys.stderr)
        return EXIT_SKIP
    code, message = run(event, repo)
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
