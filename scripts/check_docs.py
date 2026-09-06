#!/usr/bin/env python3
"""Verify the hand-maintained skill catalogue tables stay in sync.

Run from repo root:
    python3 scripts/check_docs.py    # exit 1 on any drift

The "when to use" catalogue is duplicated by hand in two places:
  - README.md   (`## Skill catalogue`) rows like `| `skills/<name>/` | … |`
  - AGENTS.md   (`## Skill catalogue`) rows like `| [<name>](…) | … |`

They are intentionally phrased differently from the auto-generated
`skills.json` summaries, so this guard does not touch the prose. It only
checks that both tables cover exactly the current skill set and that the
two tables agree with each other — catching the common mistake of adding,
renaming, or removing a skill and forgetting one of the tables.

The current skill set and each skill's category come from `skills.json` via
`catalogue.py`, not from crawling `skills/`, so a stale manifest makes this
check answer from stale metadata. Run `python3 scripts/build_manifest.py`
first; CI gates it with `build_manifest.py --check` before this check runs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from catalogue import load_catalogue

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
AGENTS = REPO_ROOT / "AGENTS.md"

README_ROW = re.compile(r"^\| `skills/([a-z0-9-]+)/` \| (.*) \|$")
AGENTS_ROW = re.compile(r"^\| \[([a-z0-9-]+)\]\(skills/\1/SKILL\.md\) \| (.*) \|$")
# Category sections look like: ### Architecture & design (`architecture`)
SECTION_HEADING = re.compile(r"^### .+ \(`([a-z0-9-]+)`\)$")


def parse_table(
    path: Path, pattern: re.Pattern[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Return (skill -> description, skill -> category of enclosing section)."""
    rows: dict[str, str] = {}
    sections: dict[str, str] = {}
    current = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        h = SECTION_HEADING.match(line)
        if h:
            current = h.group(1)
            continue
        m = pattern.match(line)
        if m:
            rows[m.group(1)] = m.group(2).strip()
            sections[m.group(1)] = current
    return rows, sections


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
    # Router skills (activation: router) are per-category infrastructure, not a
    # distinct capability, so they carry no "when to use" catalogue row; their
    # members are listed individually as usual.
    catalogued = [entry for entry in load_catalogue() if not entry.is_router]
    skills = {entry.name for entry in catalogued}
    categories = {entry.name: entry.category for entry in catalogued}
    readme, readme_sections = parse_table(README, README_ROW)
    agents, agents_sections = parse_table(AGENTS, AGENTS_ROW)

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

    for label, sections in (("README.md", readme_sections), ("AGENTS.md", agents_sections)):
        for name, section in sorted(sections.items()):
            want = categories.get(name)
            if want is not None and section != want:
                errors.append(
                    f"{label}: {name} listed under section `{section or '(none)'}` "
                    f"but its SKILL.md says category: {want}"
                )

    if errors:
        sys.stderr.write("catalogue drift detected:\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        sys.stderr.write(
            "\nUpdate the tables in README.md and AGENTS.md "
            "(## Skill catalogue in both) so they list every skill "
            "with matching text.\n"
        )
        return 1

    print(f"catalogue in sync ({len(skills)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
