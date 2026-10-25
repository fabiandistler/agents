#!/usr/bin/env python3
"""Reject Markdown tables wider than three columns in skill content.

Run from repo root:
    python3 scripts/check_table_width.py    # exit 1 when a wide table remains

The repo owner reads skills, and the answers they shape, on a phone, where a
table of four or more columns scrolls sideways or wraps into an unreadable
grid. This gate scans every skills/**/*.md (SKILL.md, references/, assets/)
and flags each pipe table with more than three columns; the fix is a nested
list or a table of at most three columns.

Tables inside fenced code blocks count too, whatever the fence's language
tag: an output template in a fence is what the agent's answer copies. A table
is a line containing `|` followed by a GFM delimiter row (`|---|:--:|`); the
delimiter row's cell count is the table's width, so pipes inside code spans
in the header cannot inflate it. Symlinked member copies resolve to the same
file and are reported once. Stdlib-only, matching the other scripts/check_*.py
gates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from catalogue import unique_real_files

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_COLUMNS = 3

USAGE = """usage: check_table_width.py [--root DIR] [--help]

Flag Markdown tables wider than 3 columns in skills/**/*.md, including
tables inside fenced code blocks (output templates).

  --root DIR  repository root to scan (default: this script's repo)
  --help      show this message

examples:
  python3 scripts/check_table_width.py
  python3 scripts/check_table_width.py --root /path/to/checkout

exit: 0 no wide tables | 1 wide tables found | 2 usage error
"""

DIRECTION = (
    f"turn each table into a nested list (one bullet per row, one sub-bullet per "
    f"column) or a table of at most {MAX_COLUMNS} columns, so it reads on a phone"
)

# A GFM delimiter row: cells of dashes with optional alignment colons,
# separated by pipes. At least one pipe, so a bare `---` rule is not a table.
DELIMITER_CELL = r"\s*:?-+:?\s*"
DELIMITER_ROW = re.compile(
    rf"^\s*(?:\|{DELIMITER_CELL}(?:\|{DELIMITER_CELL})*\|?|{DELIMITER_CELL}(?:\|{DELIMITER_CELL})+\|?)\s*$"
)


def skill_texts(root: Path) -> list[Path]:
    return unique_real_files(sorted((root / "skills").rglob("*.md")))


def column_count(delimiter_row: str) -> int:
    cells = delimiter_row.strip()
    cells = cells.removeprefix("|")
    cells = cells.removesuffix("|")
    return len(cells.split("|"))


def wide_tables(text: str) -> list[tuple[int, int]]:
    """(header line number, column count) for each table over MAX_COLUMNS wide."""
    lines = text.splitlines()
    found: list[tuple[int, int]] = []
    for index in range(1, len(lines)):
        if "|" not in lines[index - 1] or not DELIMITER_ROW.match(lines[index]):
            continue
        columns = column_count(lines[index])
        if columns > MAX_COLUMNS:
            found.append((index, columns))
    return found


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--help" in args or "-h" in args:
        sys.stdout.write(USAGE)
        return 0
    root = REPO_ROOT
    if args[:1] == ["--root"] and len(args) == 2:
        root = Path(args[1]).resolve()
    elif args:
        sys.stderr.write(f"unknown argument: {' '.join(args)}\n{USAGE}")
        return 2
    files = skill_texts(root)
    violations = [
        f"{path.relative_to(root)}:{number}: {columns} columns"
        for path in files
        for number, columns in wide_tables(path.read_text(encoding="utf-8"))
    ]
    if violations:
        sys.stderr.write(
            f"wide tables: {len(violations)} over {MAX_COLUMNS} columns "
            f"in {len(files)} skill texts\n"
        )
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        sys.stderr.write(f"\nFix: {DIRECTION}.\n")
        return 1
    print(f"table width ok ({len(files)} skill texts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
