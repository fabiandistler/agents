#!/usr/bin/env python3
"""maintenance-instruction-unicode - fail when an instruction file carries an invisible character.

Coding agents load instruction files (AGENTS.md, SKILL.md, .claude/ ...) as trusted guidance.
Zero-width, bidirectional and tag characters can hide text in them that a reviewer does not see
in a diff; GitHub's hidden-Unicode warning exists only in its web UI. This check reads every
tracked instruction file and reports each invisible character in it.

Instruction files, as `git ls-files` lists them from the repo root (untracked files are not
checked, and no base branch is compared - every run checks every file). A tracked symlink is
read through, so its target's content is checked under the link's path:
- AGENTS.md, CLAUDE.md and SKILL.md at any depth
- .mcp.json and .github/copilot-instructions.md
- under .claude/, instructions/ and .cursor/rules/: files ending in .md, .mdc, .txt, .json,
  .yaml or .yml (a logo or a script there is not read)
- each FILE given with --include, a path from the repo root as `git ls-files` prints it: a
  repo's own instruction file outside these paths, such as a routine prompt. A FILE that is
  not tracked is a finding, `path: not a tracked file`, so a moved file does not drop out
  of the check unnoticed. Without --include only the paths above are read.

Always blocked: U+00AD, U+115F, U+1160, U+180E, U+3164, U+200B, U+200C, U+200E, U+200F,
U+202A..U+202E, U+2060..U+2064, U+2066..U+2069, U+FE00..U+FE0D, U+E0100..U+E01EF, the tag
characters U+E0000..U+E007F (so also the flags of England, Scotland and Wales), and U+FEFF
anywhere but as the file's first code point.

Allowed only as part of an emoji:
- U+FE0E and U+FE0F directly after an emoji
- U+200D between two emojis; the left one may end in U+FE0F or a skin-tone modifier
"Emoji" means the Unicode property Emoji=Yes (EMOJI below). An emoji missing from that table
is reported like any other finding: extend the table, do not allow the character.

Output: one line per finding on stderr, `path:line:col: U+200B ZERO WIDTH SPACE`. Line and
column are 1-based, the column counts code points, and only a line feed ends a line. A file
that is not valid UTF-8 is a finding too, `path:line: not valid UTF-8 (byte 0xF6)`, and so is
one that cannot be read, `path: not readable (No such file or directory)` - a dangling
symlink, or a file deleted from the work tree.

Not checked: readable but malicious text. That still needs review.

Exit codes:
  0  no finding
  1  at least one finding
  2  bad arguments
  3  environment: the working directory is not in a Git work tree
  6  git is not on PATH
Plugin-wide exit code table: "## Exit codes" in plugins/repo-maintenance/README.md
(repo fabiandistler/repo-maintenance).

Source: issue fabiandistler/repo-maintenance#127, after the CSA research note on
instruction-file poisoning (2026-10-27); --include: #138.
Part of: plugin `repo-maintenance`; run by the `instruction-unicode` job of maintenance-gate.

Usage:   scripts/maintenance-instruction-unicode.py [--include FILE]...
         (anywhere in the work tree)
"""

from __future__ import annotations

import argparse
import bisect
import os
import subprocess  # nosec B404
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path

# Instruction files: by file name at any depth, or by path from the repo root.
INSTRUCTION_NAMES = {"AGENTS.md", "CLAUDE.md", "SKILL.md"}
INSTRUCTION_PATHS = {".mcp.json", ".github/copilot-instructions.md"}
# Under these directories only text formats count.
INSTRUCTION_DIRS = (".claude/", "instructions/", ".cursor/rules/")
INSTRUCTION_DIR_SUFFIXES = {".md", ".mdc", ".txt", ".json", ".yaml", ".yml"}

ZWJ = 0x200D
VARIATION_SELECTORS = (0xFE0E, 0xFE0F)  # text style, emoji style
BOM = 0xFEFF

Spans = tuple[tuple[int, int], ...]


def parse_spans(table: str) -> Spans:
    """Code points in the emoji-data.txt notation (`200B`, `2066..2069`), sorted."""
    spans = []
    for token in table.split():
        lo, _, hi = token.partition("..")
        spans.append((int(lo, 16), int(hi or lo, 16)))
    return tuple(sorted(spans))


BLOCKED = parse_spans(
    "00AD 115F..1160 180E 200B..200C 200E..200F 202A..202E 2060..2064 2066..2069 3164 "
    "FE00..FE0D E0000..E007F E0100..E01EF"
)

# Emoji=Yes from Unicode's emoji-data.txt, Unicode 18.0.0 (Date: 2026-01-30), adjacent
# ranges merged. Regenerate from a newer emoji-data.txt when an emoji is reported.
EMOJI = parse_spans(
    """
0023 002A 0030..0039 00A9 00AE 203C 2049 2122 2139 2194..2199 21A9..21AA
231A..231B 2328 23CF 23E9..23F3 23F8..23FA 24C2 25AA..25AB 25B6 25C0
25FB..25FE 2600..2604 260E 2611 2614..2615 2618 261D 2620 2622..2623 2626
262A 262E..262F 2638..263A 2640 2642 2648..2653 265F..2660 2663 2665..2666
2668 267B 267E..267F 2692..2697 2699 269B..269C 26A0..26A1 26A7 26AA..26AB
26B0..26B1 26BD..26BE 26C4..26C5 26C8 26CE..26CF 26D1 26D3..26D4 26E9..26EA
26F0..26F5 26F7..26FA 26FD 2702 2705 2708..270D 270F 2712 2714 2716 271D
2721 2728 2733..2734 2744 2747 274C 274E 2753..2755 2757 2763..2764
2795..2797 27A1 27B0 27BF 2934..2935 2B05..2B07 2B1B..2B1C 2B50 2B55 3030
303D 3297 3299 1F004 1F0CF 1F170..1F171 1F17E..1F17F 1F18E 1F191..1F19A
1F1E6..1F1FF 1F201..1F202 1F21A 1F22F 1F232..1F23A 1F250..1F251 1F300..1F321
1F324..1F393 1F396..1F397 1F399..1F39B 1F39E..1F3F0 1F3F3..1F3F5
1F3F7..1F4FD 1F4FF..1F53D 1F549..1F54E 1F550..1F567 1F56F..1F570
1F573..1F57A 1F587 1F58A..1F58D 1F590 1F595..1F596 1F5A4..1F5A5 1F5A8
1F5B1..1F5B2 1F5BC 1F5C2..1F5C4 1F5D1..1F5D3 1F5DC..1F5DE 1F5E1 1F5E3 1F5E8
1F5EF 1F5F3 1F5FA..1F64F 1F680..1F6C5 1F6CB..1F6D2 1F6D5..1F6D9 1F6DC..1F6E5
1F6E9 1F6EB..1F6EC 1F6F0 1F6F3..1F6FC 1F7E0..1F7EB 1F7F0 1F90C..1F93A
1F93C..1F945 1F947..1F9FF 1FA70..1FA7C 1FA80..1FAC6 1FAC8 1FACC..1FADD
1FADF..1FAEB 1FAEF..1FAFA
"""
)


def in_spans(cp: int, spans: Spans) -> bool:
    i = bisect.bisect_right(spans, cp, key=lambda span: span[0]) - 1
    return i >= 0 and cp <= spans[i][1]


def is_emoji(text: str, i: int) -> bool:
    return 0 <= i < len(text) and in_spans(ord(text[i]), EMOJI)


def allowed(text: str, i: int) -> bool:
    """Whether the code point at TEXT[I] may stay, given its neighbours."""
    cp = ord(text[i])
    if cp == BOM:
        return i == 0
    if cp in VARIATION_SELECTORS:
        return is_emoji(text, i - 1)
    if cp == ZWJ:
        left = i - 2 if i > 0 and ord(text[i - 1]) == 0xFE0F else i - 1
        return is_emoji(text, left) and is_emoji(text, i + 1)
    return not in_spans(cp, BLOCKED)


def invisible_characters(text: str) -> Iterator[tuple[int, int, str]]:
    """(line, column, character) of each invisible character in TEXT that is not allowed."""
    line, col = 1, 0
    for i, char in enumerate(text):
        if char == "\n":
            line, col = line + 1, 0
            continue
        col += 1
        if not allowed(text, i):
            yield line, col, char


def is_instruction_file(path: str) -> bool:
    """PATH is relative to the repo root, with forward slashes (as git prints it)."""
    if path.rpartition("/")[2] in INSTRUCTION_NAMES or path in INSTRUCTION_PATHS:
        return True
    return (
        path.startswith(INSTRUCTION_DIRS)
        and Path(path).suffix in INSTRUCTION_DIR_SUFFIXES
    )


def file_findings(root: Path, path: str) -> list[str]:
    """Findings in the instruction file at PATH, relative to the repo ROOT."""
    try:
        raw = (root / path).read_bytes()
    except OSError as exc:
        return [f"{path}: not readable ({exc.strerror})"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        line = raw.count(b"\n", 0, exc.start) + 1
        return [f"{path}:{line}: not valid UTF-8 (byte 0x{raw[exc.start]:02X})"]
    return [
        # Unassigned code points (most of the tag block) have no name.
        f"{path}:{line}:{col}: U+{ord(char):04X} {unicodedata.name(char, '')}".rstrip()
        for line, col, char in invisible_characters(text)
    ]


def git(*args: str, cwd: Path | None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=cwd, capture_output=True, check=False
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="FILE",
        help="also check FILE, a path from the repo root; repeatable",
    )
    args = parser.parse_args(argv)
    try:
        toplevel = git("rev-parse", "--show-toplevel", cwd=None)
    except FileNotFoundError:
        print("maintenance-instruction-unicode: git not on PATH.", file=sys.stderr)
        return 6
    if toplevel.returncode != 0:
        sys.stderr.write(toplevel.stderr.decode(errors="replace"))
        return 3
    root = Path(os.fsdecode(toplevel.stdout.rstrip(b"\n")))
    tracked = git("ls-files", "-z", cwd=root)
    if tracked.returncode != 0:
        sys.stderr.write(tracked.stderr.decode(errors="replace"))
        return 3
    paths = [os.fsdecode(p) for p in tracked.stdout.split(b"\0") if p]
    included = dict.fromkeys(args.include)  # ordered, without repeats
    untracked = included.keys() - set(paths)
    findings = [
        f"{path}: not a tracked file" for path in included if path in untracked
    ] + [
        finding
        for path in paths
        if is_instruction_file(path) or path in included
        for finding in file_findings(root, path)
    ]
    for finding in findings:
        print(finding, file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
