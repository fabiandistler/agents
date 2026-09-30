#!/usr/bin/env python3
"""Vendor Matt Pocock's skills (github.com/mattpocock/skills) into `.claude/skills/`.

Run from repo root:
    python3 scripts/vendor_mattpocock_skills.py              # update to upstream main
    python3 scripts/vendor_mattpocock_skills.py --ref <sha>  # pin a commit
    python3 scripts/vendor_mattpocock_skills.py --dry-run    # print the plan only

Cloud sessions do not install plugins, so the `mattpocock-skills` plugin is
copied in as plain project skills. The skill list is upstream's own
`.claude-plugin/plugin.json` (its released set; `in-progress/` and `misc/` are
not part of it). The pinned commit, the vendored names and upstream's MIT
license live in `.claude/vendor/mattpocock-skills/`. A re-run replaces exactly
the previously vendored directories, so a skill upstream dropped disappears.

Exit codes: 0 ok, 1 git clone/checkout failed, 2 a name collides with a
directory this script does not own. Needs git; stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
VENDOR_DIR = REPO_ROOT / ".claude" / "vendor" / "mattpocock-skills"
LOCK_PATH = VENDOR_DIR / "lock.json"
UPSTREAM = "https://github.com/mattpocock/skills.git"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--ref", default="main", help="upstream branch, tag or commit (default main)"
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args()

    previous = (
        json.loads(LOCK_PATH.read_text(encoding="utf-8"))["skills"] if LOCK_PATH.is_file() else []
    )

    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "skills"
        try:
            git("clone", "--quiet", "--filter=blob:none", UPSTREAM, str(clone), cwd=Path(tmp))
            git("checkout", "--quiet", args.ref, cwd=clone)
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"git failed: {exc.stderr}")
            return 1
        commit = git("rev-parse", "HEAD", cwd=clone)
        plugin = json.loads((clone / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        sources = {Path(p).name: clone / p for p in plugin["skills"]}

        collisions = [
            name
            for name in sources
            if name not in previous
            and ((SKILLS_DIR / name).exists() or (SKILLS_DIR / name).is_symlink())
        ]
        if collisions:
            sys.stderr.write(
                f"not vendored, names already taken in .claude/skills: {', '.join(sorted(collisions))}\n"
            )
            return 2

        print(
            f"mattpocock/skills {commit[:12]} ({plugin.get('version', '?')}): {len(sources)} skills"
        )
        for name in sorted(set(previous) - set(sources)):
            print(f"  remove {name}")
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
        f"vendored into {SKILLS_DIR.relative_to(REPO_ROOT)}; lock at {LOCK_PATH.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
