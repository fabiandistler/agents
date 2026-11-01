#!/usr/bin/env python3
"""Vendor the repo-maintenance scanner, its two helpers and a prek hook into `scripts/`.

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
`check-file-tokens` prek hook comes from the same commit, from the prek-hooks
skill's references, into `scripts/hooks/`. The pinned commit, a sha256 and git
file mode per file, and upstream's license live in `vendor/repo-maintenance/`. A
re-run at the same ref changes nothing.

`--check` hashes the vendored files, reads their mode, and compares both with the
lock, without network access; `scripts/check_all.sh` runs it as the `vendor-lock`
check. Fixes go upstream, then a re-vendor brings them here: a local edit, a
flipped executable bit or a hand-edited lock fails the check.

Exit codes are in EPILOG below. Needs git (except --check); stdlib-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from vendoring import clone_at

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "repo-maintenance"
LOCK_PATH = VENDOR_DIR / "lock.json"
UPSTREAM = "https://github.com/fabiandistler/repo-maintenance"
UPSTREAM_ASSETS = "plugins/repo-maintenance/assets"
UPSTREAM_PREK_HOOKS = "plugins/repo-maintenance/skills/prek-hooks/references"
# Destination in this repo -> path in the upstream repo. The scanner runs the
# two helpers from its own directory (SCRIPT_DIR), and
# maintenance-r-advisories.py imports maintenance-new-deps.py the same way.
VENDORED = {
    "scripts/maintenance-scan.sh": f"{UPSTREAM_ASSETS}/maintenance-scan.sh",
    "scripts/maintenance-r-advisories.py": f"{UPSTREAM_ASSETS}/maintenance-r-advisories.py",
    "scripts/maintenance-new-deps.py": f"{UPSTREAM_ASSETS}/maintenance-new-deps.py",
    # The check-file-tokens hook in .pre-commit-config.yaml runs this copy.
    "scripts/hooks/check-file-tokens.sh": f"{UPSTREAM_PREK_HOOKS}/check-file-tokens.sh",
}
REVENDOR = "python3 scripts/vendor_repo_maintenance.py --ref"

DESCRIPTION = """\
Copy maintenance-scan.sh and its two helpers from fabiandistler/repo-maintenance
(plugins/repo-maintenance/assets/) into scripts/, and the check-file-tokens.sh
prek hook (plugins/repo-maintenance/skills/prek-hooks/references/) into
scripts/hooks/; pin the commit and each file's sha256 and git mode in
vendor/repo-maintenance/lock.json."""
EPILOG = """\
examples:
  python3 scripts/vendor_repo_maintenance.py --ref <commit>
  python3 scripts/vendor_repo_maintenance.py --check

exit: 0 ok | 1 git clone/checkout failed | 2 usage error
      3 a vendored file or LICENSE is missing upstream at REF (nothing written)
      4 --check: the lock is missing or malformed or lists other files than the
        four, or a vendored file is missing or differs in content or mode"""


class LockError(Exception):
    """lock.json is not JSON, or a field --check reads is missing or of the wrong type."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_mode(path: Path) -> str:
    """The mode git records for a regular file: only the owner's execute bit counts,
    so a checkout under another umask (0664 instead of 0644) still matches."""
    return "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def read_lock() -> dict:
    """Parse the lock and check the type of every field --check reads."""
    where = rel(LOCK_PATH)
    try:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LockError(f"{where}: not valid JSON (line {exc.lineno}, column {exc.colno})") from exc
    if not isinstance(lock, dict):
        raise LockError(f"{where}: must be a JSON object")
    if not isinstance(lock.get("commit"), str):
        raise LockError(f'{where}: field "commit" is missing or not a string')
    if not isinstance(lock.get("files"), dict):
        raise LockError(f'{where}: field "files" is missing or not an object')
    for path, entry in lock["files"].items():
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("sha256"), str)
            and isinstance(entry.get("mode"), str)
        ):
            raise LockError(
                f'{where}: field files["{path}"] must be an object with string fields'
                ' "sha256" and "mode"'
            )
    return lock


def check() -> int:
    if not LOCK_PATH.is_file():
        sys.stderr.write(f"no lock at {rel(LOCK_PATH)}; vendor first: {REVENDOR} <commit>\n")
        return 4
    try:
        lock = read_lock()
    except LockError as exc:
        sys.stderr.write(
            f"{exc}\nFix: re-vendor instead of editing the lock: {REVENDOR} <commit>\n"
        )
        return 4
    commit = lock["commit"]
    locked_files = lock["files"]
    drifted = [
        f"{path}: in {rel(LOCK_PATH)} but not vendored"
        for path in sorted(locked_files.keys() - VENDORED.keys())
    ]
    for destination in VENDORED:
        target = REPO_ROOT / destination
        locked = locked_files.get(destination)
        if locked is None:
            drifted.append(f"{rel(target)}: not in {rel(LOCK_PATH)}")
            continue
        if not target.is_file():
            drifted.append(f"{rel(target)}: missing")
            continue
        if sha256(target) != locked["sha256"]:
            drifted.append(f"{rel(target)}: differs from repo-maintenance {commit[:12]}")
        if git_mode(target) != locked["mode"]:
            drifted.append(f"{rel(target)}: mode {git_mode(target)}, lock has {locked['mode']}")
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
        sources = {
            destination: clone / upstream_path for destination, upstream_path in VENDORED.items()
        }
        license_source = clone / "LICENSE"
        missing = [
            source.relative_to(clone).as_posix()
            for source in [*sources.values(), license_source]
            if not source.is_file()
        ]
        if missing:
            sys.stderr.write(f"missing upstream at {commit[:12]}: {', '.join(missing)}\n")
            return 3

        print(f"repo-maintenance {commit[:12]}: {len(sources)} files")
        for destination in VENDORED:
            print(f"  {destination}")
        if dry_run:
            return 0

        for destination, source in sources.items():
            target = REPO_ROOT / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            # shutil.copy keeps upstream's mode, so the scanner stays executable.
            shutil.copy(source, target)
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(license_source, VENDOR_DIR / "LICENSE")
        lock = {
            "upstream": UPSTREAM,
            "commit": commit,
            "files": {
                destination: {
                    "sha256": sha256(REPO_ROOT / destination),
                    "mode": git_mode(REPO_ROOT / destination),
                }
                for destination in VENDORED
            },
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
