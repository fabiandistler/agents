#!/usr/bin/env python3
"""Require a table of contents on long reference files.

Run from repo root:
    python3 scripts/check_reference_tocs.py    # exit 1 when a long reference lacks a TOC

A reference file over 100 lines must contain a `## Contents` heading within
its first 20 lines, so a partial read still shows the file's scope (per
Anthropic's skill-authoring best practices). Only files directly inside a
`references/` directory are checked, not nested subdirectories. Symlinked
member copies resolve to the same file and are reported once. Stdlib-only,
matching the other scripts/check_*.py gates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MAX_LINES = 100
HEAD_LINES = 20
TOC = re.compile(r"^##\s+Contents\b")

USAGE = """usage: check_reference_tocs.py [--help]

Check every skills/*/references/*.md over 100 lines has a `## Contents`
heading in its first 20 lines.

  --help     show this message

examples:
  python3 scripts/check_reference_tocs.py

exit: 0 all long references have a TOC | 1 violations found | 2 usage error
"""


def reference_files() -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for path in sorted(SKILLS_DIR.rglob("references/*.md")):
        if not path.is_file():
            continue
        real = path.resolve()
        if real in seen:
            continue
        seen.add(real)
        files.append(real)
    return files


def has_toc(lines: list[str]) -> bool:
    return any(TOC.match(line) for line in lines[:HEAD_LINES])


def collect_violations() -> tuple[list[str], int]:
    violations: list[str] = []
    checked = 0
    for path in reference_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            violations.append(f"{path.relative_to(REPO_ROOT)}: unreadable: {exc}")
            continue
        count = len(lines)
        if count <= MAX_LINES:
            continue
        checked += 1
        if not has_toc(lines):
            violations.append(
                f"{path.relative_to(REPO_ROOT)}: {count} lines, no `## Contents` in first {HEAD_LINES} lines"
            )
    return violations, checked


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--help" in args or "-h" in args:
        sys.stdout.write(USAGE)
        return 0
    if args:
        sys.stderr.write(f"unknown argument: {' '.join(args)}\n{USAGE}")
        return 2
    violations, checked = collect_violations()
    if violations:
        sys.stderr.write(
            f"reference TOCs: {checked - len(violations)}/{checked} long references have a TOC\n"
        )
        for v in violations:
            sys.stderr.write(f"  - {v}\n")
        sys.stderr.write(
            "\nAdd a `## Contents` heading with section links in the first 20 lines.\n"
        )
        return 1
    print(f"reference TOCs ok ({checked} long references)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
