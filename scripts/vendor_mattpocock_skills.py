#!/usr/bin/env python3
"""Vendor Matt Pocock's skills (github.com/mattpocock/skills) into `.claude/skills/`.

Run from repo root:
    python3 scripts/vendor_mattpocock_skills.py              # update to upstream main
    python3 scripts/vendor_mattpocock_skills.py --ref <sha>  # pin a commit
    python3 scripts/vendor_mattpocock_skills.py --dry-run    # print the plan only
    python3 scripts/vendor_mattpocock_skills.py --check-upstream  # behind the newest release?

Cloud sessions do not install plugins, so the `mattpocock-skills` plugin is
copied in as plain project skills. The skill list is upstream's own
`.claude-plugin/plugin.json` (its released set; `in-progress/` and `misc/` are
not part of it), plus the `in-progress/` skills named in INCLUDED_IN_PROGRESS.
The pinned commit, the vendored names and upstream's MIT license live in
`.claude/vendor/mattpocock-skills/`. A re-run replaces exactly the previously
vendored directories, so a skill upstream dropped disappears.
A newly vendored skill also needs a `.claude/skills/<name>/** linguist-vendored`
line in `.gitattributes`; scripts/test_gitattributes.py fails until it has one.

Upstream skills named in the EXCLUDED constant are never vendored; the reason
sits next to the constant. An excluded name is neither copied nor reported as a
collision.

`--check-upstream` compares the lock's commit with upstream's newest release tag
(vMAJOR.MINOR.PATCH; the lock records a release `version`, so `main` is not the
target), read-only over `git ls-remote`, for the `deps-audit` job; it never runs
in CI.

Exit codes: 0 ok (--check-upstream: lock is at the newest release), 1 git
clone/checkout failed (--check-upstream: upstream unreachable or no release tag;
not checked, never current), 2 a name collides with a directory this script does
not own, 3 an INCLUDED_IN_PROGRESS skill is missing upstream at the requested
ref, 4 --check-upstream: no lock, 5 --check-upstream: the lock is behind the
newest release. Needs git; stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from vendoring import check_upstream, clone_at

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_DESCRIPTION = (
    "Vendor Matt Pocock's skills (github.com/mattpocock/skills) into `.claude/skills/`."
)
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
VENDOR_DIR = REPO_ROOT / ".claude" / "vendor" / "mattpocock-skills"
LOCK_PATH = VENDOR_DIR / "lock.json"
UPSTREAM = "https://github.com/mattpocock/skills.git"
# Never vendored: improve-codebase-architecture is forked into this catalogue as
# `improve-codebase` (#492, ADR-0008). ask-matt was deleted by hand on
# 2026-10-13 (5fc4f2f); excluding it keeps a re-run from bringing it back. A
# previously vendored copy is removed on re-run.
EXCLUDED = frozenset({"ask-matt", "improve-codebase-architecture"})
# Unreleased upstream skills vendored anyway: chief-of-staff runs the long-lived
# goal sessions whose record lives in docs/wiki/; software-factory is the
# user-invoked glossary for designing a software factory, vendored on request.
INCLUDED_IN_PROGRESS = ("chief-of-staff", "software-factory")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=CLI_DESCRIPTION,
        epilog=f"Never vendored (EXCLUDED): {', '.join(sorted(EXCLUDED))}.",
    )
    parser.add_argument(
        "--ref", default="main", help="upstream branch, tag or commit (default main)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    mode.add_argument(
        "--check-upstream",
        action="store_true",
        help="compare the lock's commit with the newest release tag (network, read-only)",
    )
    args = parser.parse_args()
    if args.check_upstream:
        if not LOCK_PATH.is_file():
            sys.stderr.write(f"no lock at {LOCK_PATH.relative_to(REPO_ROOT)}; vendor first\n")
            return 4
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        return check_upstream(UPSTREAM, lock["commit"], None)

    previous = (
        json.loads(LOCK_PATH.read_text(encoding="utf-8"))["skills"] if LOCK_PATH.is_file() else []
    )

    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "skills"
        try:
            commit = clone_at(UPSTREAM, args.ref, clone)
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"git failed: {exc.stderr}")
            return 1
        plugin = json.loads((clone / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        sources = {
            Path(p).name: clone / p for p in plugin["skills"] if Path(p).name not in EXCLUDED
        }
        for name in INCLUDED_IN_PROGRESS:
            source = clone / "skills" / "in-progress" / name
            if not (source / "SKILL.md").is_file():
                sys.stderr.write(f"in-progress skill missing upstream at {commit[:12]}: {name}\n")
                return 3
            sources[name] = source

        collisions = [
            name
            for name in sources
            if name not in previous
            and ((SKILLS_DIR / name).exists() or (SKILLS_DIR / name).is_symlink())
        ]
        if collisions:
            sys.stderr.write(
                "not vendored, names already taken in .claude/skills: "
                f"{', '.join(sorted(collisions))}\n"
            )
            return 2

        print(
            f"mattpocock/skills {commit[:12]} ({plugin.get('version', '?')}): {len(sources)} skills"
        )
        for name in sorted(set(previous) - set(sources)):
            print(f"  remove {name}")
        print("  exclude " + ", ".join(sorted(EXCLUDED)))
        if args.dry_run:
            print("  add/refresh " + ", ".join(sorted(sources)))
            return 0

        for name in previous:
            shutil.rmtree(SKILLS_DIR / name, ignore_errors=True)
        for name, source in sources.items():
            shutil.copytree(source, SKILLS_DIR / name, symlinks=True)
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(clone / "LICENSE", VENDOR_DIR / "LICENSE")
        lock = {
            "upstream": UPSTREAM,
            "commit": commit,
            "version": plugin.get("version"),
            "skills": sorted(sources),
        }
        LOCK_PATH.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(
        f"vendored into {SKILLS_DIR.relative_to(REPO_ROOT)}; "
        f"lock at {LOCK_PATH.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
