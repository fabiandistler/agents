"""Fetch an upstream repository at a ref, or check a lock against it, for scripts/vendor_*.py.

Stdlib-only; needs git on PATH.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(  # noqa: S603 -- Git args select an intentional operation; no shell.
        ["git", *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def clone_at(upstream: str, ref: str, dest: Path) -> str:
    """Clone `upstream` into `dest`, check out `ref`, and return the full commit SHA.

    `dest` must not exist yet; its parent must. Raises subprocess.CalledProcessError
    when git fails (unreachable upstream, unknown ref).
    """
    git("clone", "--quiet", "--filter=blob:none", upstream, str(dest), cwd=dest.parent)
    git("checkout", "--quiet", ref, cwd=dest)
    return git("rev-parse", "HEAD", cwd=dest)


# Exit codes of check_upstream(), shared by every vendor_*.py --check-upstream.
UPSTREAM_CURRENT = 0
UPSTREAM_NOT_CHECKED = 1
UPSTREAM_BEHIND = 5
RELEASE_TAG = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


class UpstreamError(Exception):
    """The upstream could not be read, or it has no such ref or no release tag."""


def _ls_remote(upstream: str, pattern: str) -> dict[str, str]:
    """Map each remote ref name to the commit it points at; annotated tags are peeled."""
    try:
        listing = git("ls-remote", upstream, pattern, cwd=Path.cwd())
    except subprocess.CalledProcessError as exc:
        raise UpstreamError(f"git ls-remote failed: {exc.stderr.strip()}") from exc
    refs: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in listing.splitlines():
        commit, name = line.split("\t", 1)
        if name.endswith("^{}"):
            peeled[name.removesuffix("^{}")] = commit
        else:
            refs[name] = commit
    return refs | peeled


def upstream_target(upstream: str, branch: str | None) -> tuple[str, str]:
    """Return (target name, commit) a vendored copy should be at.

    `branch` names the upstream branch to track; None tracks the newest release
    tag (vMAJOR.MINOR.PATCH, pre-releases ignored). Raises UpstreamError.
    """
    if branch is not None:
        ref = f"refs/heads/{branch}"
        commit = _ls_remote(upstream, ref).get(ref)
        if commit is None:
            raise UpstreamError(f"upstream has no branch {branch!r}")
        return branch, commit
    releases = {
        tuple(int(part) for part in match.groups()): (name.removeprefix("refs/tags/"), commit)
        for name, commit in _ls_remote(upstream, "refs/tags/*").items()
        if (match := RELEASE_TAG.fullmatch(name.removeprefix("refs/tags/")))
    }
    if not releases:
        raise UpstreamError("upstream has no release tag (vMAJOR.MINOR.PATCH)")
    return releases[max(releases)]


def check_upstream(upstream: str, locked_commit: str, branch: str | None) -> int:
    """Compare a lock's commit with the upstream target; print the result, return an exit code.

    Read-only and networked. `branch` as in upstream_target(). Prints one line to
    stdout (`current` or `behind`); an unreachable upstream or unknown ref prints
    "not checked" and git's error to stderr and never reads as current.
    """
    try:
        target, target_commit = upstream_target(upstream, branch)
    except UpstreamError as exc:
        sys.stderr.write(f"{upstream}: not checked: {exc}\n")
        return UPSTREAM_NOT_CHECKED
    status = "current" if target_commit == locked_commit else "behind"
    print(f"{upstream} ({target}): locked {locked_commit}, upstream {target_commit}: {status}")
    return UPSTREAM_CURRENT if status == "current" else UPSTREAM_BEHIND
