#!/usr/bin/env python3
"""Flag time-sensitive claims in skill texts.

Run from repo root:
    python3 scripts/check_dated_claims.py    # exit 1 when a dated claim remains

A skill outlives the day it was written, so a dated statement ("as of 2026",
"verified 2026-09-07", "ts-arch's last release was 2024-12") silently turns
false (Anthropic's skill-authoring best practice "avoid time-sensitive
information"; skill-audit checklist item C2). This gate flags ISO dates
(20YY-MM, 20YY-MM-DD) and the phrases "as of <year>", "checked <year>",
"verified <year>" and "last updated <year>" in every skills/**/SKILL.md and
skills/**/references/*.md.

Escape hatch: each file may carry one as-of note, a paragraph whose first
line starts with `As of 20YY-MM` (day optional). Dated provenance — when a
version was verified, a source revision, a re-check deadline — goes there and
nowhere else, so a reader finds every expiring fact in one place. Dates inside
fenced code blocks, inline code spans and URLs are example data or citations
and are ignored. Symlinked member copies resolve to the same file and are
reported once. Stdlib-only, matching the other scripts/check_*.py gates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from catalogue import unique_real_files

REPO_ROOT = Path(__file__).resolve().parent.parent

USAGE = """usage: check_dated_claims.py [--root DIR] [--help]

Flag ISO dates and "as of / checked / verified / last updated <year>" in
skills/**/SKILL.md and skills/**/references/*.md outside the file's one
paragraph starting `As of 20YY-MM[-DD]`. Code and URLs are ignored.

  --root DIR  repository root to scan (default: this script's repo)
  --help      show this message

examples:
  python3 scripts/check_dated_claims.py
  python3 scripts/check_dated_claims.py --root /path/to/checkout

exit: 0 no dated claims | 1 dated claims found | 2 usage error
"""

DIRECTION = "drop the date, or move it into the file's one paragraph starting `As of 20YY-MM[-DD]`"

MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
ISO_DATE = re.compile(r"\b20\d{2}-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?\b")
DATED_PHRASE = re.compile(
    rf"\b(?:as of|checked|verified|last updated)(?:\s+(?:on|in))?\s+(?:{MONTH}\s+)?20\d{{2}}\b",
    re.IGNORECASE,
)
AS_OF_NOTE = re.compile(r"^As of 20\d{2}-(?:0[1-9]|1[0-2])\b")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(`+).+?\1")
URL = re.compile(r"https?://[^\s)>]+")


def skill_texts(root: Path) -> list[Path]:
    skills_dir = root / "skills"
    return unique_real_files(
        sorted([*skills_dir.rglob("SKILL.md"), *skills_dir.rglob("references/*.md")])
    )


def dated_claims(text: str) -> list[tuple[int, str]]:
    """(line number, matched text) for each line with a dated claim.

    A second as-of note is itself reported, so a file keeps its dates in one place.
    """
    claims: list[tuple[int, str]] = []
    fence: str | None = None
    in_note = False
    notes = 0
    previous_blank = True
    for number, line in enumerate(text.splitlines(), start=1):
        opener = FENCE.match(line)
        if fence is not None:
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            continue
        blank = not line.strip()
        if blank:
            in_note = False
        elif previous_blank and AS_OF_NOTE.match(line):
            notes += 1
            if notes == 1:
                in_note = True
            else:
                claims.append((number, "second as-of note"))
                previous_blank = blank
                continue
        previous_blank = blank
        if in_note:
            continue
        prose = URL.sub("", CODE_SPAN.sub("", line))
        # The full ISO date names the claim better than the phrase around it.
        match = ISO_DATE.search(prose) or DATED_PHRASE.search(prose)
        if match:
            claims.append((number, match.group(0)))
    return claims


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
        f"{path.relative_to(root)}:{number}: {claim}"
        for path in files
        for number, claim in dated_claims(path.read_text(encoding="utf-8"))
    ]
    if violations:
        sys.stderr.write(f"dated claims: {len(violations)} in {len(files)} skill texts\n")
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        sys.stderr.write(f"\nFix: {DIRECTION}.\n")
        return 1
    print(f"dated claims ok ({len(files)} skill texts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
