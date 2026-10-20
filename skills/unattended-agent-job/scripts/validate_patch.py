#!/usr/bin/env python3
"""Model-free gate between an unattended LLM step and the step that publishes.

The LLM step emits a unified diff; the publisher runs this script on a clean
checkout of the base commit before it applies, commits or pushes anything.
The script never writes: `git apply --check` and `git apply --numstat` read the
patch against the working tree without changing it.

Changed paths are the patch's paths (both sides of a rename or delete) plus
untracked files already in the checkout (`git ls-files --others
--exclude-standard`): a stray file left next to the patch is what a later
`git add -A` would publish. Every changed path must match an allowlist pattern,
anchored at the repository root. Protected paths (the job's own prompt,
workflow, permission config) route the change to a human PR instead.

Allowlist file: one glob per line, `#` starts a comment. `*` and `?` stay
within one path segment, `**/` spans zero or more directories, a trailing
`/**` covers everything below a directory. Patterns match the whole path.

Stdlib only, Python 3.11+.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_APPLICABLE = 3
EXIT_OUTSIDE_ALLOWLIST = 4
EXIT_OVER_BUDGET = 5
EXIT_PROTECTED = 6

# Report at most this many violations; the counts stay exact.
MAX_REPORTED = 50

HELP = """\
usage: validate_patch.py --repo DIR --patch FILE --allowlist FILE
                         [--max-lines N] [--protected GLOB]...

Read-only gate for an LLM-emitted patch: it applies cleanly, every changed path
(incl. untracked files in DIR) matches the anchored allowlist, the added plus
deleted line count stays within budget, and no protected path is touched.
Prints one JSON object to stdout; diagnostics go to stderr.

  --repo DIR        clean checkout of the base commit (repository root)
  --patch FILE      unified diff produced by the LLM step
  --allowlist FILE  one glob per line, anchored at the repo root; # comments
  --max-lines N     added + deleted line budget (default 300)
  --protected GLOB  path that only a human PR may change; repeatable

exit: 0 ok | 2 usage | 3 patch does not apply | 4 path outside allowlist
      5 over line budget | 6 touches protected path (route to a human PR)
      (several failures: the lowest code from 3 to 6 wins; JSON lists all)

examples:
  python3 scripts/validate_patch.py --repo . --patch outputs/patch.diff \\
      --allowlist .agent/allowlist.txt
  python3 scripts/validate_patch.py --repo . --patch outputs/patch.diff \\
      --allowlist .agent/allowlist.txt --max-lines 200 \\
      --protected '.github/**' --protected 'docs/agents/skill-audit.md'
"""


class UsageError(Exception):
    """Bad or missing input; maps to exit 2."""


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile an anchored path glob (see module docstring) to a regex."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            out.append("/.+")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def read_allowlist(path: Path) -> list[str]:
    """Patterns from the allowlist file, comments and blank lines dropped."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise UsageError(f"--allowlist: cannot read file ({exc.strerror})") from exc
    patterns = [line.split("#", 1)[0].strip() for line in lines]
    patterns = [p for p in patterns if p]
    if not patterns:
        raise UsageError("--allowlist: file holds no pattern; an empty allowlist admits nothing")
    for pattern in patterns:
        if pattern.startswith("/") or ".." in pattern.split("/"):
            raise UsageError("--allowlist: patterns are repo-relative, without a leading / or ..")
    return patterns


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )


def repo_root(repo: Path) -> Path:
    if not repo.is_dir():
        raise UsageError("--repo: not a directory")
    proc = git(repo, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        raise UsageError("--repo: not inside a git work tree")
    return Path(proc.stdout.strip())


def parse_numstat(raw: str) -> list[tuple[str, int, int]]:
    """Parse `git apply --numstat -z` into (path, added, deleted) rows.

    A rename or copy yields both its old and its new path, each carrying the
    line counts once (the new path) or zero (the old path), so the budget
    counts the change once while the allowlist sees both sides. Binary files
    report `-` and count as zero lines.
    """
    rows: list[tuple[str, int, int]] = []
    fields = raw.split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        if not entry:
            i += 1
            continue
        added_s, deleted_s, path = entry.split("\t", 2)
        added = int(added_s) if added_s.isdigit() else 0
        deleted = int(deleted_s) if deleted_s.isdigit() else 0
        if path:
            rows.append((path, added, deleted))
            i += 1
        else:
            rows.append((fields[i + 1], 0, 0))
            rows.append((fields[i + 2], added, deleted))
            i += 3
    return rows


def validate(
    repo: Path, patch: Path, allowlist: list[str], max_lines: int, protected: list[str]
) -> tuple[int, dict[str, object]]:
    root = repo_root(repo)
    patch = patch.resolve()
    if not patch.is_file():
        raise UsageError("--patch: file not found")

    violations: list[dict[str, str]] = []
    check = git(root, "apply", "--check", str(patch))
    if check.returncode != 0:
        print(check.stderr.strip(), file=sys.stderr)
        violations.append({"kind": "not_applicable", "path": ""})

    stat = git(root, "apply", "--numstat", "-z", str(patch))
    if stat.returncode != 0:
        print(stat.stderr.strip(), file=sys.stderr)
        rows: list[tuple[str, int, int]] = []
        if not violations:
            violations.append({"kind": "not_applicable", "path": ""})
    else:
        rows = parse_numstat(stat.stdout)

    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    changed: dict[str, str] = {}
    for path, _, _ in rows:
        changed.setdefault(path, "patch")
    for path in filter(None, untracked.split("\0")):
        changed.setdefault(path, "untracked")

    allow_res = [glob_to_regex(p) for p in allowlist]
    protect_res = [glob_to_regex(p) for p in protected]
    for path, source in sorted(changed.items()):
        if not any(r.match(path) for r in allow_res):
            violations.append({"kind": "outside_allowlist", "path": path, "source": source})
        if any(r.match(path) for r in protect_res):
            violations.append({"kind": "protected", "path": path, "source": source})

    lines = sum(a + d for _, a, d in rows)
    if lines > max_lines:
        violations.append({"kind": "over_budget", "path": ""})

    order = {
        "not_applicable": EXIT_NOT_APPLICABLE,
        "outside_allowlist": EXIT_OUTSIDE_ALLOWLIST,
        "over_budget": EXIT_OVER_BUDGET,
        "protected": EXIT_PROTECTED,
    }
    code = min((order[v["kind"]] for v in violations), default=EXIT_OK)
    return code, {
        "ok": code == EXIT_OK,
        "exit": code,
        "changed_paths": len(changed),
        "untracked_paths": sum(1 for s in changed.values() if s == "untracked"),
        "lines": lines,
        "max_lines": max_lines,
        "violation_count": len(violations),
        "violations": violations[:MAX_REPORTED],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--allowlist", type=Path)
    parser.add_argument("--max-lines", type=int, default=300)
    parser.add_argument("--protected", action="append", default=[])
    parser.add_argument("-h", "--help", action="store_true")
    try:
        args, extra = parser.parse_known_args(argv)
    except SystemExit:
        return EXIT_USAGE
    if args.help:
        print(HELP, end="")
        return EXIT_OK
    try:
        if extra:
            raise UsageError(f"unknown argument: {extra[0]}")
        for flag in ("repo", "patch", "allowlist"):
            if getattr(args, flag) is None:
                raise UsageError(f"--{flag} is required")
        if args.max_lines < 0:
            raise UsageError("--max-lines: needs a non-negative integer")
        code, report = validate(
            args.repo, args.patch, read_allowlist(args.allowlist), args.max_lines, args.protected
        )
    except UsageError as exc:
        print(f"validate_patch: {exc} (see --help)", file=sys.stderr)
        return EXIT_USAGE
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
