#!/usr/bin/env python3
"""Generate skills.json from the skill catalogue.

Run from repo root:
    python3 scripts/build_manifest.py            # write skills.json
    python3 scripts/build_manifest.py --check    # exit 1 if drift

Source parsing and entry validation live in `catalogue.py`; this script owns
only the generated manifest file. Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys

from catalogue import MANIFEST_PATH, REPO_ROOT, entry_from_skill_file, find_skill_files

MANIFEST_VERSION = "1"


def build_manifest() -> dict[str, object]:
    entries = [entry_from_skill_file(path) for path in find_skill_files()]
    return {"version": MANIFEST_VERSION, "skills": [entry.to_manifest() for entry in entries]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if skills.json is out of date")
    args = parser.parse_args()

    manifest = build_manifest()
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        existing = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.exists() else ""
        if existing != rendered:
            sys.stderr.write("skills.json is out of date. Run: python3 scripts/build_manifest.py\n")
            return 1
        return 0

    MANIFEST_PATH.write_text(rendered, encoding="utf-8")
    skills = manifest["skills"]
    if not isinstance(skills, list):
        raise TypeError("built manifest skills must be a list")
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} ({len(skills)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
