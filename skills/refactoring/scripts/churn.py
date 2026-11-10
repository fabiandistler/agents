#!/usr/bin/env python3
"""Rank files by git churn to suggest where a refactor might be worth starting.

Answers "what should we look at first?" in a codebase nobody in the room knows
well, using the one source of evidence every repo already has: its history.

Each surviving file gets five numbers and one derived score:

  * COMMITS -- how many non-merge commits touched the file inside the window.
    Change frequency. The core signal: code that never changes costs nothing to
    leave alone, however ugly it is.

  * AUTHORS -- how many distinct authors touched it. A high count on a small
    file often means a coordination point rather than a mess; a high count on a
    large one means nobody owns it.

  * LINES   -- current line count, used as a stand-in for complexity. It is a
    crude one. A long file of flat data is not complex; a short file of dense
    conditionals is. Treat it as a first cut, not a measurement.

  * LAST    -- how long ago the most recent commit in the window touched it.
    Recency separates "actively churning" from "churned last spring, settled
    since".

  * SCORE   -- normalized COMMITS x normalized LINES: each column is divided by
    the largest value in the result set, then the two are multiplied. This is
    Tornhill's hotspot heuristic (change frequency x size): the intersection is
    where change is both frequent and expensive.

    The scale is relative, and 1.00 is a ceiling almost nothing reaches -- it
    requires one file to hold BOTH the most commits and the most lines. Usually
    the busiest file and the biggest file are different files, so a real top
    score of 0.3 is ordinary and means nothing on its own. Read the column as a
    ranking, never as a percentage of some ideal. The raw columns are what you
    actually reason about -- a 0.31 and a 0.29 are the same answer.

This script is a reducer, not a judge. It sorts what git already recorded; it
has no idea whether any of it should change. High churn is often perfectly
healthy -- a config file, a route table, a well-tested integration point that
grows an entry per feature. A hotspot is a place to go read, and the reading is
where the finding comes from. Nothing here justifies a refactor on its own.

It also lies in three specific situations, all worth checking before trusting a
ranking: a repo younger than the window (everything looks hot because everything
is new), a bulk reformat or license-header sweep inside the window (one commit
touching every file flattens the ranking), and a shallow clone (history is cut
off at the clone depth -- the script warns when it detects one).

Renames are mapped through `git log -M --name-status`: each `R old new` edge
resolves along the chain to its current path, so history accrues to the path
in the working tree. Paths that are no longer regular files in the working tree --
deleted, or tracked symlinks pointing at directories -- are counted in the
summary but dropped from the ranking; there is nothing left to refactor.

COMMITS counts every non-merge commit that touched the file, both sides of a
merge included, renames counted under the current path. Cross-checking a row
with `git log -- <file>` will read lower, because that applies history
simplification and stops at renames; `git log --follow --no-merges
--since=<window> -- <file>` is the equivalent command.

--include narrows the set to matching paths; --exclude subtracts from whatever
survives. Passing --include also drops the built-in exclusions below, on the
assumption that naming paths explicitly is the stronger signal:

    */node_modules/*  */vendor/*  */dist/*  */build/*  */.venv/*  */venv/*
    *.min.js  *.min.css  *.lock  *-lock.json  *.sum  *.map  *.snap

Usage:
    python churn.py [PATH] [--since '12 months ago'] [--top N] [--min-commits N]
                    [--include GLOB]... [--exclude GLOB]... [--json] [--output FILE]

--top caps the JSON file list too (0 = all); --since takes an ISO date or
'<N> <unit> ago'. Exit codes: 0 ok, 1 git or path error, 2 bad usage.

Stdlib only; runs on any Python 3.9+.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from git_history import (
    FileChurn,
    GitError,
    collect,
    has_commits,
    is_shallow,
    repo_root,
    valid_since,
)

DEFAULT_EXCLUDES = (
    "*/node_modules/*",
    "*/vendor/*",
    "*/dist/*",
    "*/build/*",
    "*/.venv/*",
    "*/venv/*",
    "*.min.js",
    "*.min.css",
    "*.lock",
    "*-lock.json",
    "*.sum",
    "*.map",
    "*.snap",
)

BINARY_SNIFF_BYTES = 8192


def matches(path: str, globs: list[str]) -> bool:
    """fnmatch the repo-relative path against globs, anchored at any path segment."""
    probe = f"/{path}"
    return any(fnmatch.fnmatch(probe, f"*{g}") for g in globs)


def keep(path: str, includes: list[str], excludes: list[str]) -> bool:
    """--include narrows the set; --exclude subtracts from whatever survives."""
    if includes and not matches(path, includes):
        return False
    return not matches(path, excludes)


def measure(root: Path, entry: FileChurn) -> None:
    """Fill in `exists`, `binary` and `lines` from the working tree."""
    target = root / entry.path
    try:
        if not target.is_file():
            return
        data = target.read_bytes()
    except OSError:
        return
    entry.exists = True
    if b"\0" in data[:BINARY_SNIFF_BYTES]:
        entry.binary = True
        return
    entry.lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def rank(entries: list[FileChurn]) -> list[FileChurn]:
    """Score = norm(commits) * norm(lines), each normalized against the set maximum."""
    max_commits = max((e.commits for e in entries), default=0)
    max_lines = max((e.lines for e in entries), default=0)
    for e in entries:
        c = e.commits / max_commits if max_commits else 0.0
        ln = e.lines / max_lines if max_lines else 0.0
        e.score = c * ln
    return sorted(entries, key=lambda e: (-e.score, -e.commits, e.path))


def ago(when: datetime | None, now: datetime) -> str:
    if when is None:
        return "-"
    days = max((now - when).days, 0)
    if days == 0:
        return "today"
    if days < 14:
        return f"{days}d"
    if days < 60:
        return f"{days // 7}w"
    if days < 730:
        return f"{days // 30}mo"
    return f"{days // 365}y"


def elide(path: str, width: int) -> str:
    """Truncate from the left -- the tail of a path carries more information."""
    return path if len(path) <= width else "..." + path[-(width - 3) :]


def render(
    entries: list[FileChurn],
    *,
    since: str,
    top: int,
    dropped_missing: int,
    dropped_min: int,
    now: datetime,
) -> str:
    shown = entries[:top] if top > 0 else entries
    notes = []
    if dropped_missing:
        notes.append(f"{dropped_missing} gone from the tree")
    if dropped_min:
        notes.append(f"{dropped_min} below --min-commits")
    suffix = f" ({', '.join(notes)}, not shown)" if notes else ""
    head = f"{len(entries)} files ranked since {since}{suffix}"

    width = max([28, *(min(len(e.path), 60) for e in shown)])
    lines = [
        head,
        "",
        (
            f"{'FILE':<{width}}  {'COMMITS':>7}  {'AUTHORS':>7}  "
            f"{'LINES':>6}  {'LAST':>5}  {'SCORE':>5}"
        ),
    ]
    for e in shown:
        size = "binary" if e.binary else str(e.lines)
        lines.append(
            f"{elide(e.path, width):<{width}}  {e.commits:>7}  {len(e.authors):>7}  "
            f"{size:>6}  {ago(e.last_commit, now):>5}  {e.score:>5.2f}"
        )
    if top > 0 and len(entries) > top:
        lines.append(f"... {len(entries) - top} more (raise --top or use --json)")
    lines.append("")
    lines.append("Hotspots are places to read, not verdicts. See the skill body.")
    return "\n".join(lines)


def to_dict(entry: FileChurn) -> dict:
    return {
        "path": entry.path,
        "commits": entry.commits,
        "authors": len(entry.authors),
        "author_names": sorted(entry.authors),
        "lines": entry.lines,
        "binary": entry.binary,
        "last_commit": entry.last_commit.isoformat() if entry.last_commit else None,
        "score": round(entry.score, 4),
    }


def emit(payload: str, dest: str | None) -> int:
    """Print payload, or write it to dest; returns the process exit code."""
    if dest is None:
        print(payload)
        return 0
    try:
        Path(dest).write_text(payload + "\n", encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"error: cannot write {dest}: {exc}\n")
        return 1
    sys.stderr.write(f"wrote {dest}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rank files by git churn x size; orders evidence, judges nothing.",
        epilog="examples:\n"
        "  churn.py --since '6 months ago' --top 10\n"
        "  churn.py --json --output hotspots.json .\n"
        "exit codes: 0 ok, 1 git or path error, 2 bad usage.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path", nargs="?", default=".", type=Path, help="repo or subdir to rank (default: .)"
    )
    parser.add_argument(
        "--since",
        default="12 months ago",
        help="ISO date or '<N> <unit> ago' (default: '12 months ago')",
    )
    parser.add_argument("--top", type=int, default=20, help="rows shown, 0 = all (default: 20)")
    parser.add_argument(
        "--min-commits",
        type=int,
        default=2,
        metavar="N",
        help="hide files below N commits (default: 2)",
    )
    parser.add_argument(
        "--include", action="append", default=[], metavar="GLOB", help="keep only matching paths"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="also skip matching paths",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument(
        "--output", default=None, metavar="FILE", help="write to FILE instead of stdout"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.top < 0 or args.min_commits < 0:
        sys.stderr.write("error: --top and --min-commits must be 0 or greater\n")
        return 2
    if not valid_since(args.since):
        sys.stderr.write(
            f"error: --since '{args.since}' is not a supported date "
            "(use ISO 'YYYY-MM-DD' or '<N> <unit> ago')\n"
        )
        return 2

    try:
        target = args.path.resolve()
        root = repo_root(target)
        if not has_commits(root):
            print(f"{root} has no commits yet. Nothing to rank.")
            return 0
        pathspec = None
        if target != root:
            pathspec = target.relative_to(root).as_posix()
        files, commit_count = collect(root, args.since, pathspec)
    except GitError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    except ValueError:
        sys.stderr.write(f"error: {args.path} is not inside its git work tree\n")
        return 1

    shallow = is_shallow(root)
    if shallow:
        sys.stderr.write(
            "warning: shallow clone -- history is truncated at the clone depth, "
            "so the window may be incomplete\n"
        )

    if not files:
        print(f"No file changes in the window (--since '{args.since}'). Nothing to rank.")
        return 0

    excludes = args.exclude if args.include else [*DEFAULT_EXCLUDES, *args.exclude]
    kept = [e for e in files.values() if keep(e.path, args.include, excludes)]

    for entry in kept:
        measure(root, entry)

    alive = [e for e in kept if e.exists]
    dropped_missing = len(kept) - len(alive)
    ranked_input = [e for e in alive if e.commits >= args.min_commits]
    dropped_min = len(alive) - len(ranked_input)
    entries = rank(ranked_input)

    if args.json:
        page = entries if args.top <= 0 else entries[: args.top]
        return emit(
            json.dumps(
                {
                    "root": str(root),
                    "since": args.since,
                    "shallow": shallow,
                    "commits_scanned": commit_count,
                    "files_seen": len(files),
                    "files_ranked": len(entries),
                    "dropped_missing": dropped_missing,
                    "dropped_below_min_commits": dropped_min,
                    "files": [to_dict(e) for e in page],
                },
                indent=2,
            ),
            args.output,
        )

    if not entries:
        print(
            f"No files survived filtering (seen {len(files)}, "
            f"{dropped_missing} gone from the tree, {dropped_min} below --min-commits)."
        )
        return 0

    return emit(
        render(
            entries,
            since=args.since,
            top=args.top,
            dropped_missing=dropped_missing,
            dropped_min=dropped_min,
            now=datetime.now(timezone.utc),
        ),
        args.output,
    )


if __name__ == "__main__":
    sys.exit(main())
