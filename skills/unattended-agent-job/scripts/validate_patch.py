#!/usr/bin/env python3
"""Model-free gate between an unattended LLM step and the step that publishes.

The LLM step emits a unified diff; the publisher runs this script on a clean
checkout of the base commit before it applies, commits or pushes anything.
The script never writes: `git apply --check` and `git apply --numstat` read the
patch against the working tree without changing it. The patch file itself must
lie outside the checkout, so the job's downloaded outputs never count as
changes.

Changed paths are the patch's paths (both sides of a rename or delete) plus
untracked files already in the checkout (`git ls-files --others
--exclude-standard`): a stray file left next to the patch is what a later
`git add -A` would publish. A tracked file modified in the checkout fails the
run as `dirty_tree`: the gate only vouches for a clean base. Every changed path
must match an allowlist pattern, anchored at the repository root and matched
against the whole path. Protected paths (the job's own prompt, workflow,
permission config) route the change to a human PR instead.

Some changes are never admitted, whatever the allowlist says: symlinks
(mode 120000), submodules (mode 160000), binary patches, and paths that are
absolute, contain a `..` component or a `.git` component. Executable-bit
changes are admitted but listed under `mode_changes` in the report.

The checkout is assumed case-sensitive (Linux runners). Allowlist patterns
match case-sensitively; protected patterns match case-insensitively, so
`.GitHub/workflows/x.yml` cannot slip past a `.github/**` protection on a
checkout that is later read case-insensitively.

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
from dataclasses import dataclass, field
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_APPLICABLE = 3
EXIT_OUTSIDE_ALLOWLIST = 4
EXIT_OVER_BUDGET = 5
EXIT_PROTECTED = 6
EXIT_DIRTY_TREE = 7
EXIT_FORBIDDEN_CHANGE = 8

EXIT_BY_KIND = {
    "not_applicable": EXIT_NOT_APPLICABLE,
    "outside_allowlist": EXIT_OUTSIDE_ALLOWLIST,
    "over_budget": EXIT_OVER_BUDGET,
    "protected": EXIT_PROTECTED,
    "dirty_tree": EXIT_DIRTY_TREE,
    "unsafe_path": EXIT_FORBIDDEN_CHANGE,
    "symlink": EXIT_FORBIDDEN_CHANGE,
    "submodule": EXIT_FORBIDDEN_CHANGE,
    "binary": EXIT_FORBIDDEN_CHANGE,
}

# Report at most this many violations; the counts stay exact.
MAX_REPORTED = 50

SYMLINK_MODE = "120000"
SUBMODULE_MODE = "160000"

HELP = """\
usage: validate_patch.py --repo DIR --patch FILE --allowlist FILE
                         [--max-lines N] [--protected GLOB]...

Read-only gate for an LLM-emitted patch: it applies to the clean checkout, every
changed path (incl. untracked files) matches the anchored allowlist, nothing is
a symlink, submodule, binary or unsafe path (absolute, .., .git), the line budget
holds, no protected path is touched. JSON report on stdout. Linux checkout.

  --repo DIR        clean checkout of the base commit (repository root)
  --patch FILE      unified diff from the LLM step; must lie outside DIR
  --allowlist FILE  one glob per line, anchored at the repo root; # comments
  --max-lines N     added + deleted line budget (default 300)
  --protected GLOB  only a human PR may change it (case-insensitive); repeatable

exit: 0 ok | 2 usage | 3 patch does not apply | 4 path outside allowlist
      5 over line budget | 6 touches protected path (route to a human PR)
      7 tracked file modified in DIR | 8 symlink, submodule, binary, unsafe path
      (several failures: the lowest code wins, 6 only if nothing else failed)

examples:
  python3 scripts/validate_patch.py --repo . --allowlist .agent/allowlist.txt \\
      --patch "$RUNNER_TEMP/outputs/patch.diff"
  python3 scripts/validate_patch.py --repo . --allowlist .agent/allowlist.txt \\
      --patch "$RUNNER_TEMP/outputs/patch.diff" --protected '.github/**'
"""


class UsageError(Exception):
    """Bad or missing input; maps to exit 2."""


def glob_to_regex(pattern: str, flags: int = 0) -> re.Pattern[str]:
    """Compile a path glob (see module docstring); use it with `fullmatch`."""
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
    return re.compile("".join(out), flags | re.DOTALL)


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
    return Path(proc.stdout.strip()).resolve()


@dataclass
class FileChange:
    """One file section of the patch: its path(s), line counts and modes."""

    paths: list[str]
    added: int
    deleted: int
    binary: bool
    modes: set[str] = field(default_factory=set)
    old_mode: str = ""
    new_mode: str = ""


def parse_numstat(raw: str) -> list[FileChange]:
    """Parse `git apply --numstat -z` into one FileChange per patch section.

    A rename or copy carries its old and its new path; both go through the
    allowlist, the line counts once. Binary files report `-` as counts.
    """
    changes: list[FileChange] = []
    fields = raw.split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        if not entry:
            i += 1
            continue
        added_s, deleted_s, path = entry.split("\t", 2)
        binary = added_s == "-" or deleted_s == "-"
        added = int(added_s) if added_s.isdigit() else 0
        deleted = int(deleted_s) if deleted_s.isdigit() else 0
        if path:
            paths = [path]
            i += 1
        else:
            paths = [fields[i + 1], fields[i + 2]]
            i += 3
        changes.append(FileChange(paths, added, deleted, binary))
    return changes


HEADER_MODE_RE = re.compile(r"(new file mode|deleted file mode|old mode|new mode) ([0-7]{6})")
INDEX_MODE_RE = re.compile(r"index [0-9a-f]+\.\.[0-9a-f]+ ([0-7]{6})")


def read_section_headers(patch_text: str) -> list[list[str]]:
    """Extended header lines of each `diff --git` section, in patch order."""
    sections: list[list[str]] = []
    in_header = False
    for line in patch_text.split("\n"):
        if line.startswith("diff --git "):
            sections.append([])
            in_header = True
        elif in_header:
            if line.startswith(("@@", "--- ")):
                in_header = False
                continue
            sections[-1].append(line)
            if line == "GIT binary patch":
                in_header = False
    return sections


def attach_modes(changes: list[FileChange], patch_text: str) -> None:
    """Copy file modes and binary markers from the patch headers onto `changes`.

    `git apply --numstat` keeps patch order, so section i is change i. Should
    the counts ever differ, every change gets the union of all sections'
    markers: a forbidden mode anywhere still fails the run.
    """
    sections = read_section_headers(patch_text)
    if len(sections) != len(changes):
        sections = [[line for section in sections for line in section]] * len(changes)
    for change, header in zip(changes, sections, strict=True):
        for line in header:
            if line == "GIT binary patch" or line.startswith("Binary files "):
                change.binary = True
            if m := HEADER_MODE_RE.fullmatch(line):
                change.modes.add(m.group(2))
                if m.group(1) in ("old mode", "deleted file mode"):
                    change.old_mode = m.group(2)
                else:
                    change.new_mode = m.group(2)
            elif m := INDEX_MODE_RE.fullmatch(line):
                change.modes.add(m.group(1))


def is_unsafe_path(path: str) -> bool:
    """Absolute, escaping (`..`) or inside a `.git` directory."""
    parts = path.split("/")
    return path.startswith("/") or ".." in parts or any(p.lower() == ".git" for p in parts)


def is_executable(mode: str) -> bool:
    return bool(mode) and int(mode, 8) & 0o111 != 0


def dirty_paths(root: Path) -> list[str]:
    """Tracked paths whose working-tree or index state differs from HEAD."""
    raw = git(root, "status", "--porcelain", "-z", "--untracked-files=no").stdout
    fields = raw.split("\0")
    paths: list[str] = []
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if not entry:
            continue
        paths.append(entry[3:])
        if entry[0] in "RC":
            paths.append(fields[i])
            i += 1
    return paths


def exit_code(violations: list[dict[str, str]]) -> int:
    """Lowest failure code wins; protected (6) only when nothing else failed."""
    codes = {EXIT_BY_KIND[v["kind"]] for v in violations}
    others = codes - {EXIT_PROTECTED}
    if others:
        return min(others)
    return EXIT_PROTECTED if codes else EXIT_OK


def validate(
    repo: Path, patch: Path, allowlist: list[str], max_lines: int, protected: list[str]
) -> tuple[int, dict[str, object]]:
    root = repo_root(repo)
    patch = patch.resolve()
    if not patch.is_file():
        raise UsageError("--patch: file not found")
    if patch.is_relative_to(root):
        raise UsageError(
            "--patch: file lies inside --repo, where it counts as an untracked change; "
            "download the outputs outside the checkout (e.g. $RUNNER_TEMP/outputs/)"
        )

    violations: list[dict[str, str]] = []
    for path in dirty_paths(root):
        violations.append({"kind": "dirty_tree", "path": path, "source": "worktree"})

    check = git(root, "apply", "--check", str(patch))
    if check.returncode != 0:
        print(check.stderr.strip(), file=sys.stderr)
        violations.append({"kind": "not_applicable", "path": ""})

    stat = git(root, "apply", "--numstat", "-z", str(patch))
    if stat.returncode != 0:
        print(stat.stderr.strip(), file=sys.stderr)
        changes: list[FileChange] = []
        if not any(v["kind"] == "not_applicable" for v in violations):
            violations.append({"kind": "not_applicable", "path": ""})
    else:
        changes = parse_numstat(stat.stdout)
        attach_modes(changes, patch.read_text(encoding="utf-8", errors="replace"))

    mode_changes: list[dict[str, str]] = []
    for change in changes:
        path = change.paths[-1]
        if change.binary:
            violations.append({"kind": "binary", "path": path, "source": "patch"})
        if SYMLINK_MODE in change.modes:
            violations.append({"kind": "symlink", "path": path, "source": "patch"})
        if SUBMODULE_MODE in change.modes:
            violations.append({"kind": "submodule", "path": path, "source": "patch"})
        if change.new_mode and is_executable(change.old_mode) != is_executable(change.new_mode):
            mode_changes.append(
                {"path": path, "old_mode": change.old_mode, "new_mode": change.new_mode}
            )

    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    changed: dict[str, str] = {}
    for change in changes:
        for path in change.paths:
            changed.setdefault(path, "patch")
    for path in filter(None, untracked.split("\0")):
        changed.setdefault(path, "untracked")

    allow_res = [glob_to_regex(p) for p in allowlist]
    protect_res = [glob_to_regex(p, re.IGNORECASE) for p in protected]
    for path, source in sorted(changed.items()):
        if is_unsafe_path(path):
            violations.append({"kind": "unsafe_path", "path": path, "source": source})
        if not any(r.fullmatch(path) for r in allow_res):
            violations.append({"kind": "outside_allowlist", "path": path, "source": source})
        if any(r.fullmatch(path) for r in protect_res):
            violations.append({"kind": "protected", "path": path, "source": source})

    lines = sum(c.added + c.deleted for c in changes)
    if lines > max_lines:
        violations.append({"kind": "over_budget", "path": ""})

    code = exit_code(violations)
    return code, {
        "ok": code == EXIT_OK,
        "exit": code,
        "changed_paths": len(changed),
        "untracked_paths": sum(1 for s in changed.values() if s == "untracked"),
        "lines": lines,
        "max_lines": max_lines,
        "mode_changes": mode_changes,
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
