#!/usr/bin/env python3
"""Vendor the repo-maintenance scanner and its two Python helpers into `scripts/`.

Run from repo root:
    python3 scripts/vendor_repo_maintenance.py              # update to upstream main
    python3 scripts/vendor_repo_maintenance.py --ref <sha>  # pin a commit
    python3 scripts/vendor_repo_maintenance.py --dry-run    # print the plan only
    python3 scripts/vendor_repo_maintenance.py --check      # offline drift check (CI)

The maintenance runs in this repo call `scripts/maintenance-scan.sh`. A hand-kept
copy of it drifted from upstream, so every scanner fix had to be ported by hand
(#673, #675). This script copies the scanner from upstream
`plugins/repo-maintenance/assets/` together with the two helpers it loads from its
own directory, so the three stay siblings and keep upstream's file mode. The
pinned commit, a sha256 per file and upstream's license live in
`vendor/repo-maintenance/`. A re-run at the same ref changes nothing.

`--check` hashes the vendored files and compares them with the lock, without
network access; `scripts/check_all.sh` runs it as the `vendor-lock` check. Fixes go
upstream, then a re-vendor brings them here: a local edit fails the check.

Exit codes are in EPILOG below. Needs git (except --check); stdlib-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from vendoring import clone_at

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
VENDOR_DIR = REPO_ROOT / "vendor" / "repo-maintenance"
LOCK_PATH = VENDOR_DIR / "lock.json"
UPSTREAM = "https://github.com/fabiandistler/repo-maintenance"
UPSTREAM_ASSETS = "plugins/repo-maintenance/assets"
# The scanner runs the two helpers from its own directory (SCRIPT_DIR), and
# maintenance-r-advisories.py imports maintenance-new-deps.py the same way.
VENDORED = ("maintenance-scan.sh", "maintenance-r-advisories.py", "maintenance-new-deps.py")
REVENDOR = "python3 scripts/vendor_repo_maintenance.py --ref"

DESCRIPTION = """\
Copy maintenance-scan.sh and its two helpers from fabiandistler/repo-maintenance
(plugins/repo-maintenance/assets/) into scripts/; pin the commit and a sha256 per
file in vendor/repo-maintenance/lock.json."""
EPILOG = """\
examples:
  python3 scripts/vendor_repo_maintenance.py --ref <commit>
  python3 scripts/vendor_repo_maintenance.py --check

exit: 0 ok | 1 git clone/checkout failed | 2 usage error
      3 a vendored file is missing upstream at REF (nothing written)
      4 --check: a vendored file differs from the lock or is missing, or there is no lock"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def check() -> int:
    if not LOCK_PATH.is_file():
        sys.stderr.write(f"no lock at {rel(LOCK_PATH)}; vendor first: {REVENDOR} <commit>\n")
        return 4
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    commit = lock["commit"]
    drifted = []
    for name in VENDORED:
        target = SCRIPTS_DIR / name
        locked = lock["files"].get(rel(target))
        if locked is None:
            drifted.append(f"{rel(target)}: not in {rel(LOCK_PATH)}")
        elif not target.is_file():
            drifted.append(f"{rel(target)}: missing")
        elif sha256(target) != locked:
            drifted.append(f"{rel(target)}: differs from repo-maintenance {commit[:12]}")
    if drifted:
        sys.stderr.write(f"vendored repo-maintenance files: {len(drifted)} drifted\n")
        for line in drifted:
            sys.stderr.write(f"  - {line}\n")
        sys.stderr.write(
            f"\nFix: put the change upstream ({UPSTREAM}), then re-vendor;"
            f" to restore the pinned copy: {REVENDOR} {commit}\n"
        )
        return 4
    print(f"vendored repo-maintenance files ok ({len(VENDORED)} at {commit[:12]})")
    return 0


def vendor(ref: str, dry_run: bool) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "repo-maintenance"
        try:
            commit = clone_at(UPSTREAM, ref, clone)
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"git failed: {exc.stderr}")
            return 1
        sources = {name: clone / UPSTREAM_ASSETS / name for name in VENDORED}
        missing = [name for name, source in sources.items() if not source.is_file()]
        if missing:
            sys.stderr.write(
                f"missing upstream in {UPSTREAM_ASSETS}/ at {commit[:12]}: {', '.join(missing)}\n"
            )
            return 3

        print(f"repo-maintenance {commit[:12]}: {len(sources)} files into {rel(SCRIPTS_DIR)}/")
        for name in VENDORED:
            print(f"  {name}")
        if dry_run:
            return 0

        for name, source in sources.items():
            # shutil.copy keeps upstream's mode, so the scanner stays executable.
            shutil.copy(source, SCRIPTS_DIR / name)
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(clone / "LICENSE", VENDOR_DIR / "LICENSE")
        lock = {
            "upstream": UPSTREAM,
            "commit": commit,
            "files": {rel(SCRIPTS_DIR / name): sha256(SCRIPTS_DIR / name) for name in VENDORED},
        }
        LOCK_PATH.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"lock at {rel(LOCK_PATH)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ref", help="upstream branch, tag or commit (default main)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    mode.add_argument(
        "--check",
        action="store_true",
        help="compare the vendored files with the lock, offline; write nothing",
    )
    args = parser.parse_args()
    if args.check:
        if args.ref:
            parser.error("--check reads the commit from the lock; it takes no --ref")
        return check()
    return vendor(args.ref or "main", args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
