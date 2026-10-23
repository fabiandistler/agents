#!/usr/bin/env python3
"""Flag cross-skill references that name a skill an agent cannot invoke.

Run from repo root:
    python3 scripts/check_skill_refs.py    # exit 1 when violations remain

AGENTS.md ("Conventions for skill authors"): cross-skill references name only
registered, model-invocable skills. A router member is read via its router
file, never invoked by name; a command skill is user-invoked, so the text
suggests the user run it. The skill sets come from skills.json (via
catalogue.py), so the check tracks the manifest:

- member: an auto skill in a category that ships a router. Naming it is fine
  once the file has introduced it in the router form, a paragraph holding both
  `members/<name>/SKILL.md` and the router's name. Later mentions in the same
  file may then use the short name. The router's own SKILL.md and the member's
  own files may name it freely.
- command: an `activation: command` skill, matched only in backticks or bold.
  Fine when its paragraph says "run" or "command" (suggest the user run it).
- unknown: "`x` skill" or "skill `x`" where x is in neither skills.json nor the
  vendored Matt Pocock lock. Fine when the paragraph links a URL or credits an
  author ("Someone's `x` skill"): those are third-party skills.
- path: `members/<x>/SKILL.md` where x is no member, or a sibling link
  `../<x>/` to a member or command skill.

Scope: skills/*/SKILL.md and skills/*/references/**/*.md. In SKILL.md
frontmatter only `description` and `when_to_use` count: they are the
always-loaded trigger text, so a member or command name there has no router
form and is always reported (the router itself may name its members). Symlinked router-member copies count once. Stdlib-only.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from catalogue import load_catalogue, routed_categories, router_members, unique_real_files

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_LOCK = Path(".claude/vendor/mattpocock-skills/lock.json")

USAGE = """usage: check_skill_refs.py [--root DIR] [--help]

Flag SKILL.md and reference text that names a router member, a command skill
or a non-existent skill as if it were an invocable skill. Sets come from
DIR/skills.json.

  --root DIR  repository root to scan (default: this script's repo)
  --help      show this message

examples:
  python3 scripts/check_skill_refs.py
  python3 scripts/check_skill_refs.py --root /path/to/checkout

exit: 0 no violations | 1 violations | 2 usage error or missing skills.json
"""

# A skill name standing alone: not inside a longer hyphenated word or a path.
NAME_EDGE_BEFORE = r"(?<![\w/.-])"
NAME_EDGE_AFTER = r"(?![\w/-])"
UNKNOWN_SKILL = re.compile(
    r"`(?P<a>[a-z][a-z0-9-]*)`\*{0,2}\s+(?:sub-)?skill\b"
    r"|\bskill\s+\*{0,2}`(?P<b>[a-z][a-z0-9-]*)`"
)
MEMBER_PATH = re.compile(r"members/(?P<name>[a-z0-9-]+)/SKILL\.md")
SIBLING_LINK = re.compile(r"\]\(\.\./(?P<name>[a-z0-9-]+)/")
RUN_HINT = re.compile(r"\brun\b|\bcommand\b", re.IGNORECASE)
EXTERNAL_HINT = re.compile(r"https?://|\w's\s+`")
TRIGGER_KEY = re.compile(r"(?:description|when_to_use):")


@dataclass(frozen=True)
class SkillSets:
    member_router: dict[str, str]  # member name -> its router's name
    command: frozenset[str]
    known: frozenset[str]


def load_sets(root: Path) -> SkillSets:
    catalogue = load_catalogue(root / "skills.json")
    routers = {e.category: e.name for e in catalogue if e.is_router}
    member_router = {
        e.name: routers[e.category]
        for category in routed_categories(catalogue)
        for e in router_members(catalogue, category)
    }
    known = {e.name for e in catalogue}
    lock = root / VENDOR_LOCK
    if lock.is_file():
        known |= set(json.loads(lock.read_text(encoding="utf-8"))["skills"])
    return SkillSets(
        member_router=member_router,
        command=frozenset(e.name for e in catalogue if e.is_command),
        known=frozenset(known),
    )


def scanned_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            candidates.append(skill_dir / "SKILL.md")
            candidates.extend(sorted(skill_dir.glob("references/**/*.md")))
    return unique_real_files(candidates)


def body_start(lines: list[str]) -> int:
    """Index of the first line after a leading YAML frontmatter block."""
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return index + 1
    return 0


def trigger_fields(lines: list[str]) -> list[tuple[int, int]]:
    """(first, end) line spans of the frontmatter `description` and `when_to_use`.

    A field runs from its key line through any indented continuation lines.
    """
    spans: list[tuple[int, int]] = []
    end_of_frontmatter = body_start(lines) - 1
    index = 1
    while index < end_of_frontmatter:
        if TRIGGER_KEY.match(lines[index]):
            first = index
            index += 1
            while index < end_of_frontmatter and lines[index][:1] in (" ", "\t"):
                index += 1
            spans.append((first, index))
        else:
            index += 1
    return spans


def paragraphs(lines: list[str], start: int) -> list[tuple[int, int]]:
    """(first, end) line spans of blank-line-delimited blocks from `start`."""
    spans: list[tuple[int, int]] = []
    first = None
    for index in range(start, len(lines)):
        if lines[index].strip():
            if first is None:
                first = index
        elif first is not None:
            spans.append((first, index))
            first = None
    if first is not None:
        spans.append((first, len(lines)))
    return spans


def name_pattern(name: str, *, marked_only: bool) -> re.Pattern[str]:
    if marked_only:
        return re.compile(rf"(?:`{re.escape(name)}`|\*\*{re.escape(name)}\*\*)")
    return re.compile(NAME_EDGE_BEFORE + re.escape(name) + NAME_EDGE_AFTER)


def check_file(path: Path, rel: str, owner: str, sets: SkillSets) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    violations: list[str] = []
    introduced: set[str] = set()
    member_patterns = {name: name_pattern(name, marked_only=False) for name in sets.member_router}
    command_patterns = {name: name_pattern(name, marked_only=True) for name in sets.command}

    for first, end in trigger_fields(lines):
        block = "\n".join(lines[first:end])
        for index in range(first, end):
            where = f"{rel}:{index + 1}"
            for name, router in sets.member_router.items():
                if name != owner and owner != router and member_patterns[name].search(lines[index]):
                    violations.append(
                        f"{where}: {name}: router member named in trigger text; drop it or"
                        f" say what the skill is not for"
                    )
            for name, pattern in command_patterns.items():
                if name != owner and pattern.search(lines[index]) and not RUN_HINT.search(block):
                    violations.append(f"{where}: {name}: command skill named in trigger text")

    for first, end in paragraphs(lines, body_start(lines)):
        block = "\n".join(lines[first:end])
        for match in MEMBER_PATH.finditer(block):
            name = match.group("name")
            router = sets.member_router.get(name)
            if router and re.search(rf"\b{re.escape(router)}\b", block):
                introduced.add(name)
        for index in range(first, end):
            line = lines[index]
            where = f"{rel}:{index + 1}"
            for match in MEMBER_PATH.finditer(line):
                if match.group("name") not in sets.member_router:
                    violations.append(
                        f"{where}: members/{match.group('name')}/SKILL.md: no such router member"
                    )
            for match in SIBLING_LINK.finditer(line):
                name = match.group("name")
                if name in sets.member_router or name in sets.command:
                    violations.append(
                        f"{where}: ../{name}/: link the member via its router or name the"
                        " command for the user to run, not a sibling path"
                    )
            for name, router in sets.member_router.items():
                if name == owner or owner == router or name in introduced:
                    continue
                if member_patterns[name].search(line):
                    violations.append(
                        f"{where}: {name}: router member named as a skill; write"
                        f" `members/{name}/SKILL.md`, read via the `{router}` router"
                    )
            for name, pattern in command_patterns.items():
                if name == owner or not pattern.search(line) or RUN_HINT.search(block):
                    continue
                violations.append(
                    f"{where}: {name}: command skill named as invocable; suggest the user run it"
                )
            for match in UNKNOWN_SKILL.finditer(line):
                name = match.group("a") or match.group("b")
                if name in sets.known or EXTERNAL_HINT.search(block):
                    continue
                violations.append(f"{where}: {name}: no such skill in skills.json")
    return violations


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if "--help" in args or "-h" in args:
        sys.stdout.write(USAGE)
        return 0
    root = REPO_ROOT
    if args[:1] == ["--root"]:
        if len(args) < 2:
            sys.stderr.write(f"--root needs a directory\n{USAGE}")
            return 2
        root = Path(args[1])
        args = args[2:]
    if args:
        sys.stderr.write(f"unknown argument: {' '.join(args)}\n{USAGE}")
        return 2
    if not (root / "skills.json").is_file():
        sys.stderr.write(f"{root}/skills.json not found; run scripts/build_manifest.py\n")
        return 2

    sets = load_sets(root)
    real_root = root.resolve()
    files = scanned_files(root)
    violations: list[str] = []
    for path in files:
        rel = path.relative_to(real_root).as_posix()
        violations.extend(check_file(path, rel, rel.split("/")[1], sets))
    if violations:
        sys.stderr.write(f"skill refs: {len(violations)} problem(s) in {len(files)} files\n")
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        sys.stderr.write(
            '\nSee AGENTS.md, "Conventions for skill authors": cross-skill references name'
            " only registered, model-invocable skills.\n"
        )
        return 1
    print(f"skill refs ok ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
