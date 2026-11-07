"""Fetch an upstream repository at a ref, for the scripts/vendor_*.py scripts.

Stdlib-only; needs git on PATH.
"""

from __future__ import annotations

import subprocess
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
