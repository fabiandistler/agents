#!/usr/bin/env python3
"""Generate the per-category router skills from skills.json.

Run from repo root:
    python3 scripts/build_routers.py            # write router bodies + member symlinks
    python3 scripts/build_routers.py --check    # exit 1 if any router is out of date

A *router* is a skill named after its category whose frontmatter carries
`activation: router`. It is the only member of the category registered at top
level; the category's auto skills are nested under the router's `members/`
subdir (as symlinks) and load lazily when the router routes to them.

This script owns two machine-generated parts of each router, so they can never
drift from the catalogue:
  1. the `members/<name>` symlinks under the router directory, and
  2. the Markdown table between the
     `<!-- BEGIN generated:members -->` / `<!-- END generated:members -->`
     markers in the router's SKILL.md body.
Everything else in the router SKILL.md (frontmatter, prose, routing
instruction) is hand-authored and left untouched.

Member rows are sourced from skills.json, so the router tracks the manifest;
run build_manifest.py first. `activation: command` skills are user-invoked and
bypass routers, so they are excluded from the table. Stdlib-only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from catalogue import REPO_ROOT, SkillEntry, load_catalogue, router_members

BEGIN_MARKER = "<!-- BEGIN generated:members -->"
END_MARKER = "<!-- END generated:members -->"


def router_files(catalogue: list[SkillEntry]) -> dict[str, Path]:
    """Map each routed category to its router's source file."""
    return {entry.category: REPO_ROOT / entry.path for entry in catalogue if entry.is_router}


def render_table(members: list[SkillEntry]) -> str:
    """The generated member table, between (not including) the markers."""
    lines = [
        "| Sub-skill | When to use | Read before acting |",
        "|---|---|---|",
    ]
    for member in members:
        lines.append(f"| {member.name} | {member.summary} | `members/{member.name}/SKILL.md` |")
    return "\n".join(lines)


def splice_region(text: str, table: str, skill_md: Path) -> str:
    """Replace the marked region of a router body with the freshly rendered table."""
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"{skill_md}: missing or malformed generated-members markers"
            f" ({BEGIN_MARKER} … {END_MARKER})"
        )
    head = text[: start + len(BEGIN_MARKER)]
    tail = text[end:]
    return f"{head}\n{table}\n{tail}"


def expected_symlinks(members: list[SkillEntry]) -> dict[str, str]:
    """Map member name -> expected relative symlink target under members/."""
    return {member.name: f"../../{member.name}" for member in members}


def sync_symlinks(members_dir: Path, members: list[SkillEntry], *, check: bool) -> list[str]:
    """Create (or in check mode verify) the members/<name> symlinks. Returns drift."""
    expected = expected_symlinks(members)
    errors: list[str] = []

    existing: dict[str, str] = {}
    if members_dir.is_dir():
        for child in members_dir.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_symlink():
                existing[child.name] = str(child.readlink())
            else:
                existing[child.name] = "<not-a-symlink>"

    if check:
        for name, target in expected.items():
            if existing.get(name) != target:
                errors.append(
                    f"{members_dir.relative_to(REPO_ROOT)}/{name}: expected symlink"
                    f" -> {target}, got {existing.get(name, '<missing>')}"
                )
        for name in existing:
            if name not in expected:
                errors.append(f"{members_dir.relative_to(REPO_ROOT)}/{name}: stale member symlink")
        return errors

    members_dir.mkdir(parents=True, exist_ok=True)
    for name in existing:
        if name not in expected:
            (members_dir / name).unlink()
    for name, target in expected.items():
        link = members_dir / name
        if link.is_symlink() and str(link.readlink()) == target:
            continue
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target)
    return errors


def process(
    category: str,
    skill_md: Path,
    catalogue: list[SkillEntry],
    *,
    check: bool,
) -> list[str]:
    members = router_members(catalogue, category)
    errors = sync_symlinks(skill_md.parent / "members", members, check=check)

    current = skill_md.read_text(encoding="utf-8")
    rendered = splice_region(current, render_table(members), skill_md)

    if check:
        if current != rendered:
            errors.append(
                f"{skill_md.relative_to(REPO_ROOT)}: generated member table is out of date"
            )
    else:
        if current != rendered:
            skill_md.write_text(rendered, encoding="utf-8")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if any router is out of date")
    args = parser.parse_args()

    catalogue = load_catalogue()
    routers = router_files(catalogue)
    errors: list[str] = []
    for category, skill_md in sorted(routers.items()):
        errors.extend(process(category, skill_md, catalogue, check=args.check))

    if args.check:
        if errors:
            sys.stderr.write("router drift detected:\n")
            for e in errors:
                sys.stderr.write(f"  - {e}\n")
            sys.stderr.write("\nRun: python3 scripts/build_routers.py\n")
            return 1
        print(f"routers in sync ({len(routers)} routed categories)")
        return 0

    print(f"wrote {len(routers)} router(s): {', '.join(sorted(routers)) or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
