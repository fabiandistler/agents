"""Read a repository's git history into per-file churn records for churn.py.

`collect` makes one `git log -M --name-status` pass over the window and folds
rename chains onto the current path; the other helpers locate the work tree,
detect unborn or shallow history, and accept only the --since forms churn.py
documents. Every git failure surfaces as `GitError`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

COMMIT_SEP = "\x01"
FIELD_SEP = "\x1f"


class GitError(RuntimeError):
    """git was missing, or refused to answer."""


@dataclass
class FileChurn:
    path: str
    commits: int = 0
    authors: set[str] = field(default_factory=set)
    last_commit: datetime | None = None
    lines: int = 0
    exists: bool = False
    unreadable: bool = False
    binary: bool = False
    score: float = 0.0

    def record(self, author: str, when: datetime | None) -> None:
        self.commits += 1
        self.authors.add(author)
        if when is not None and (self.last_commit is None or when > self.last_commit):
            self.last_commit = when


def run_git(root: Path, args: list[str]) -> str:
    """Run a git command under `root` and return stdout, or raise GitError."""
    try:
        proc = subprocess.run(  # noqa: S603 -- validated Git argv; no shell.
            ["git", "-C", str(root), *args],  # noqa: S607 -- Git intentionally resolves from PATH.
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on PATH") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(detail or f"git {' '.join(args)} failed")
    return proc.stdout.decode("utf-8", errors="replace")


def repo_root(target: Path) -> Path:
    """Resolve the git work tree containing `target`."""
    if not target.exists():
        raise GitError(f"no such path: {target}")
    anchor = target if target.is_dir() else target.parent
    try:
        out = run_git(anchor, ["rev-parse", "--show-toplevel"]).strip()
    except GitError as exc:
        raise GitError(f"not inside a git work tree: {target} ({exc})") from exc
    if not out:
        raise GitError(f"not inside a git work tree: {target}")
    return Path(out)


def has_commits(root: Path) -> bool:
    """False on a freshly-initialized repo, where HEAD points at an unborn branch."""
    try:
        run_git(root, ["rev-parse", "--verify", "--quiet", "HEAD"])
    except GitError:
        return False
    return True


def is_shallow(root: Path) -> bool:
    """True when git reports a truncated history; also true inside worktrees."""
    try:
        return run_git(root, ["rev-parse", "--is-shallow-repository"]).strip() == "true"
    except GitError:
        return False


def parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def valid_since(value: str) -> bool:
    """True for the --since forms this script documents, so git never silently guesses."""
    text = value.strip().lower()
    if text in ("now", "today", "yesterday", "last week", "last month", "last year"):
        return True
    stamp = value.strip()
    if stamp[-1:].lower() == "z":
        stamp = f"{stamp[:-1]}+00:00"
    try:
        datetime.fromisoformat(stamp)
        return True
    except ValueError:
        pass
    words = text.replace(".", " ").split()
    units = (
        "second",
        "seconds",
        "minute",
        "minutes",
        "hour",
        "hours",
        "day",
        "days",
        "week",
        "weeks",
        "month",
        "months",
        "year",
        "years",
    )
    return len(words) == 3 and words[0].isdigit() and words[1] in units and words[2] == "ago"


def collect(root: Path, since: str, pathspec: str | None) -> tuple[dict[str, FileChurn], int]:
    """One `git log` pass over the window. Returns (churn by path, commit count)."""
    args = [
        "log",
        f"--since={since}",
        "--no-merges",
        "-M",
        "-z",
        "--name-status",
        f"--pretty=format:{COMMIT_SEP}%H{FIELD_SEP}%an{FIELD_SEP}%aI",
    ]
    if pathspec:
        args += ["--", pathspec]

    out = run_git(root, args)
    files: dict[str, FileChurn] = {}
    renames: dict[str, str] = {}
    commits = 0

    for chunk in out.split(COMMIT_SEP):
        if not chunk.strip("\0\n"):
            continue
        header, _, body = chunk.partition("\n")
        parts = header.split(FIELD_SEP)
        if len(parts) < 3:
            continue
        commits += 1
        author, when = parts[1], parse_iso(parts[2])
        tokens = body.replace("\n", "\0").split("\0")
        idx = 0
        while idx < len(tokens):
            status_entry = tokens[idx].strip()
            idx += 1
            if not status_entry:
                continue
            if len(status_entry) > 1 and status_entry[0] == "R" and status_entry[1:].isdigit():
                if idx + 1 < len(tokens):
                    old = tokens[idx].strip()
                    new = tokens[idx + 1].strip()
                    idx += 2
                    if old and new:
                        renames[old] = new
                        files.setdefault(new, FileChurn(new)).record(author, when)
                continue
            if len(status_entry) > 1 and status_entry[0] == "C" and status_entry[1:].isdigit():
                if idx + 1 < len(tokens):
                    new = tokens[idx + 1].strip()
                    idx += 2
                    if new:
                        files.setdefault(new, FileChurn(new)).record(author, when)
                continue
            if len(status_entry) == 1 and status_entry in "ADMRTUXB":
                if idx < len(tokens):
                    name = tokens[idx].strip()
                    idx += 1
                    if name:
                        files.setdefault(name, FileChurn(name)).record(author, when)
                continue
            files.setdefault(status_entry, FileChurn(status_entry)).record(author, when)

    def resolve(path: str) -> str:
        seen: set[str] = set()
        while path in renames and path not in seen:
            seen.add(path)
            path = renames[path]
        return path

    merged: dict[str, FileChurn] = {}
    for path, entry in files.items():
        target = resolve(path)
        dest = merged.setdefault(target, entry if target == path else FileChurn(target))
        if dest is entry:
            continue
        dest.commits += entry.commits
        dest.authors |= entry.authors
        if entry.last_commit is not None and (
            dest.last_commit is None or entry.last_commit > dest.last_commit
        ):
            dest.last_commit = entry.last_commit

    return merged, commits
