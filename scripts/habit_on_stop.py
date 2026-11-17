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
            return git(repo, "merge-base", "HEAD", ref).strip()
    raise HookError(
        f"no default branch to compare against (tried {', '.join(DEFAULT_BRANCH_REFS)})"
    )


def changed_python_files(repo: Path, base: str) -> list[str]:
    """Python files added, modified or renamed since base, plus untracked ones."""
    changed = git(repo, "diff", "--name-only", "--diff-filter=AMR", base, "--", "*.py")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "--", "*.py")
    paths = {line for line in (changed + untracked).splitlines() if line}
    return sorted(path for path in paths if (repo / path).is_file())


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
    return json.loads(completed.stdout or "[]")


def base_source(repo: Path, base: str, path: str) -> str | None:
    """path's content at base, or None when the branch added it."""
    completed = run_tool(["git", "show", f"{base}:{path}"], repo)
    return completed.stdout if completed.returncode == 0 else None


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
    for path in changed_python_files(repo, base):
        head = ruff_findings(repo, path, (repo / path).read_text(encoding="utf-8"))
        if not head:
            continue
        before = base_source(repo, base, path)
        found += introduced(head, ruff_findings(repo, path, before) if before else [])
    return found


def coaching(repo: Path, findings: list[dict]) -> str | None:
    """habit-mapper's guides for findings, or None when it lets them pass."""
    completed = run_tool(
        ["habit-mapper"], repo, stdin=json.dumps(as_habit_findings(repo, findings))
    )
    if completed.returncode == 0:
        return None
    if completed.returncode == 1:
        return completed.stdout
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
    repo = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or Path.cwd()).resolve()
    code, message = run(event, repo)
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
