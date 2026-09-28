#!/usr/bin/env python3
"""Generate the coding-conventions skill body from instructions/.

Run from repo root:
    python3 scripts/build_conventions_skill.py            # rewrite the generated region
    python3 scripts/build_conventions_skill.py --check    # exit 1 if it is out of date

install.sh --instructions composes instructions/*.md into the global
instruction file of Claude Code, Codex CLI and opencode. Chat surfaces —
Claude Desktop, claude.ai, Cowork, Langdock — have no such file, so the same
fragments ship there as the `coding-conventions` skill. This script owns the
region between the `<!-- BEGIN generated:instructions -->` /
`<!-- END generated:instructions -->` markers in its SKILL.md; frontmatter and
the prose around the markers are hand-authored and left untouched.

A fragment is included when its `targets:` field is `all` or names `claude`,
the only target the skill ships to. `paths:` scoping is dropped: a chat has no
files to match, so the R rules are included unconditionally.

exit: 0 ok | 1 drift found with --check | 2 missing or malformed markers
Stdlib-only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS_DIR = REPO_ROOT / "instructions"
SKILL_MD = REPO_ROOT / "skills" / "coding-conventions" / "SKILL.md"

BEGIN_MARKER = "<!-- BEGIN generated:instructions -->"
END_MARKER = "<!-- END generated:instructions -->"
TARGETS = re.compile(r"^targets:[ \t]*(.*?)[ \t]*$", re.MULTILINE)


def split_fragment(text: str) -> tuple[str, str]:
    """Return (frontmatter, body) of a fragment; frontmatter is '' when absent."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 3)
    if end == -1:
        return "", text
    return text[4 : end + 1], text[end + 5 :]


def ships_to_claude(frontmatter: str) -> bool:
    match = TARGETS.search(frontmatter)
    if not match:
        return True
    parts = {p.strip() for p in match.group(1).split(",")}
    return "all" in parts or "claude" in parts


def render() -> str:
    """The composed fragments, in filename order, one blank line between them."""
    bodies = []
    for fragment in sorted(INSTRUCTIONS_DIR.glob("*.md")):
        frontmatter, body = split_fragment(fragment.read_text(encoding="utf-8"))
        if ships_to_claude(frontmatter):
            bodies.append(body.strip("\n"))
    return "\n\n".join(bodies)


def splice(text: str, generated: str) -> str:
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"{SKILL_MD.relative_to(REPO_ROOT)}: missing or malformed markers")
    return f"{text[: start + len(BEGIN_MARKER)]}\n\n{generated}\n\n{text[end:]}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate skills/coding-conventions/SKILL.md from instructions/.",
        epilog="exit: 0 ok | 1 drift found with --check | 2 missing or malformed markers",
    )
    parser.add_argument("--check", action="store_true", help="exit 1 if the skill is out of date")
    args = parser.parse_args()

    current = SKILL_MD.read_text(encoding="utf-8")
    try:
        rendered = splice(current, render())
    except ValueError as e:
        sys.stderr.write(f"{e}\n")
        return 2

    if args.check:
        if current != rendered:
            sys.stderr.write(
                f"{SKILL_MD.relative_to(REPO_ROOT)}: generated instructions are out of date\n"
                "\nRun: python3 scripts/build_conventions_skill.py\n"
            )
            return 1
        print("coding-conventions skill in sync with instructions/")
        return 0

    if current != rendered:
        SKILL_MD.write_text(rendered, encoding="utf-8")
        print(f"wrote {SKILL_MD.relative_to(REPO_ROOT)}")
    else:
        print("coding-conventions skill already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
