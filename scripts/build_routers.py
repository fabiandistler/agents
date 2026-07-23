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
import json
import sys
from pathlib import Path

from build_manifest import (
    extract_frontmatter,
    find_skill_files,
    parse_frontmatter,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_PATH = REPO_ROOT / "skills.json"

BEGIN_MARKER = "<!-- BEGIN generated:members -->"
END_MARKER = "<!-- END generated:members -->"


def routed_categories() -> dict[str, Path]:
    """Map category -> router SKILL.md for every `activation: router` skill.

    The router skill must be named after its category (name == category).
    """
    routers: dict[str, Path] = {}
    for skill_md in find_skill_files():
        fm = parse_frontmatter(extract_frontmatter(skill_md.read_text(encoding="utf-8")))
        if fm.get("activation") != "router":
            continue
        name = fm.get("name")
        category = fm.get("category")
        if name != category:
            raise ValueError(
                f"{skill_md}: a router's name ({name!r}) must equal its category"
                f" ({category!r})"
            )
        routers[str(category)] = skill_md
    return routers


def load_members(category: str) -> list[dict[str, object]]:
    """Auto members of a category from skills.json, in manifest order.

    Excludes the router itself and any `activation: command` skill (those are
    user-invoked and bypass routing).
    """
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    members = []
    for entry in manifest["skills"]:
        if entry.get("category") != category:
            continue
        if entry.get("activation") in ("command", "router"):
            continue
        members.append(entry)
    return members


def render_table(members: list[dict[str, object]]) -> str:
    """The generated member table, between (not including) the markers."""
    lines = [
        "| Sub-skill | When to use | Read before acting |",
        "|---|---|---|",
    ]
    for m in members:
        name = m["name"]
        lines.append(f"| {name} | {m['summary']} | `members/{name}/SKILL.md` |")
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


def expected_symlinks(members: list[dict[str, object]]) -> dict[str, str]:
    """Map member name -> expected relative symlink target under members/."""
    return {str(m["name"]): f"../../{m['name']}" for m in members}


def sync_symlinks(
    members_dir: Path, members: list[dict[str, object]], *, check: bool
) -> list[str]:
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
                errors.append(
                    f"{members_dir.relative_to(REPO_ROOT)}/{name}: stale member symlink"
                )
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


def process(category: str, skill_md: Path, *, check: bool) -> list[str]:
    members = load_members(category)
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
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if any router is out of date"
    )
    args = parser.parse_args()

    routers = routed_categories()
    errors: list[str] = []
    for category, skill_md in sorted(routers.items()):
        errors.extend(process(category, skill_md, check=args.check))

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
