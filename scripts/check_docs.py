#!/usr/bin/env python3
"""Verify the hand-maintained skill catalogue tables stay in sync.

Run from repo root:
    python3 scripts/check_docs.py    # exit 1 on any drift

The "when to use" catalogue is duplicated by hand in two places:
  - README.md   (`## Contents`)      rows like `| `skills/<name>/` | … |`
  - AGENTS.md   (`## Skill catalogue`) rows like `| [<name>](…) | … |`

They are intentionally phrased differently from the auto-generated
`skills.json` summaries, so this guard does not touch the prose. It only
checks that both tables cover exactly the current skill set and that the
two tables agree with each other — catching the common mistake of adding,
renaming, or removing a skill and forgetting one of the tables.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
README = REPO_ROOT / "README.md"
AGENTS = REPO_ROOT / "AGENTS.md"

README_ROW = re.compile(r"^\| `skills/([a-z0-9-]+)/` \| (.*) \|$")
AGENTS_ROW = re.compile(r"^\| \[([a-z0-9-]+)\]\(skills/\1/SKILL\.md\) \| (.*) \|$")


def skill_names() -> set[str]:
    return {
        child.name
        for child in SKILLS_DIR.iterdir()
        if child.is_dir()
        and not child.name.startswith(".")
        and (child / "SKILL.md").is_file()
    }


def parse_table(path: Path, pattern: re.Pattern[str]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            rows[m.group(1)] = m.group(2).strip()
    return rows


def report(label: str, skills: set[str], rows: dict[str, str]) -> list[str]:
    errors = []
    listed = set(rows)
    missing = skills - listed
    unknown = listed - skills
    if missing:
        errors.append(f"{label}: missing rows for: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"{label}: rows for unknown skills: {', '.join(sorted(unknown))}")
    return errors


def main() -> int:
    skills = skill_names()
    readme = parse_table(README, README_ROW)
    agents = parse_table(AGENTS, AGENTS_ROW)

    errors: list[str] = []
    errors += report("README.md", skills, readme)
    errors += report("AGENTS.md", skills, agents)

    for name in sorted(set(readme) & set(agents)):
        if readme[name] != agents[name]:
            errors.append(
                f"{name}: README and AGENTS descriptions disagree\n"
                f"    README: {readme[name]}\n"
                f"    AGENTS: {agents[name]}"
            )

    if errors:
        sys.stderr.write("catalogue drift detected:\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        sys.stderr.write(
            "\nUpdate the tables in README.md (## Contents) and "
            "AGENTS.md (## Skill catalogue) so both list every skill "
            "with matching text.\n"
        )
        return 1

    print(f"catalogue in sync ({len(skills)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
