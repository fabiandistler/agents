#!/usr/bin/env python3
"""Flag agent-specific vocabulary and bad cross-skill pointers in skill bodies.

Run from repo root:
    python3 scripts/check_skill_vocab.py    # exit 1 when violations remain

Skill bodies are plain Markdown read by any agent (Claude Code, Codex CLI,
opencode, and others), so they avoid agent-specific vocabulary and only name
skills the model can actually invoke. This check scans every
skills/*/SKILL.md body (after frontmatter) and skills/*/references/*.md,
resolving symlinked member copies once. Stdlib-only, matching the other
scripts/check_*.py gates.

Denylist (case-insensitive): /mnt/skills, skill tool, plugin:skill,
slash-command, unknown skill, ~/.claude, ~/.codex, frontend-design. Each hit
names the file, line, and replacement direction. Additions belong here, not in
per-skill wording, so the rule stays in one place.

Cross-skill pointers: a backticked name that matches a skills.json entry with
activation command is user-invoked, never model-invoked. Such a reference
passes only when the surrounding three-line window says suggest the user run
it. Router members are read via their router file, not invoked by a
namespaced name; that rule is documented in AGENTS.md and enforced by wording
review, not by this script, to keep member-to-member pointers inside a router
from failing.

Exemptions live in ALLOWLIST as (relative path, pattern name) pairs with the
reason recorded next to the entry. The list is currently empty; add to it
only for intentional, documented coupling such as a compatibility-declared
CLI dependency.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_PATH = REPO_ROOT / "skills.json"

USAGE = """usage: check_skill_vocab.py [--help]

Check skill bodies for agent-specific vocabulary and for cross-skill
references that name a user-invoked command skill without asking the user
to run it.

  --help     show this message

examples:
  python3 scripts/check_skill_vocab.py

exit: 0 no violations | 1 violations found | 2 usage error
"""

DENYLIST: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "/mnt/skills",
        re.compile(r"/mnt/skills", re.IGNORECASE),
        "hardcoded internal skill path; describe the file to read instead",
    ),
    (
        "skill tool",
        re.compile(r"skill\s+tool", re.IGNORECASE),
        "proprietary tool name; say file-reading tool instead",
    ),
    (
        "plugin:skill",
        re.compile(r"plugin\s*:\s*skill", re.IGNORECASE),
        "namespaced plugin reference; name the skill file to read instead",
    ),
    (
        "slash-command",
        re.compile(r"slash[\s-]*commands?", re.IGNORECASE),
        "agent-specific invocation; describe the workflow instead",
    ),
    (
        "unknown skill",
        re.compile(r"unknown\s+skill", re.IGNORECASE),
        "runtime error text; use neutral routing wording instead",
    ),
    (
        "~/.claude",
        re.compile(r"~/\.claude\b", re.IGNORECASE),
        "agent-specific install path; say your agent skills directory instead",
    ),
    (
        "~/.codex",
        re.compile(r"~/\.codex\b", re.IGNORECASE),
        "agent-specific install path; say your agent skills directory instead",
    ),
    (
        "frontend-design",
        re.compile(r"frontend-design", re.IGNORECASE),
        "external skill name; use generic design-system wording instead",
    ),
)

ALLOWLIST: frozenset[tuple[str, str]] = frozenset()

BACKTICKED = re.compile(r"`([a-z0-9][a-z0-9-]*?)`")
SUGGEST = re.compile(r"suggest", re.IGNORECASE)
USER = re.compile(r"\buser\b", re.IGNORECASE)
RUN = re.compile(r"\brun\b", re.IGNORECASE)


def body_files() -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        candidates = [skill_dir / "SKILL.md"]
        references = skill_dir / "references"
        if references.is_dir():
            candidates.extend(sorted(references.glob("*.md")))
        for path in candidates:
            if not path.is_file():
                continue
            real = path.resolve()
            if real in seen:
                continue
            seen.add(real)
            files.append(real)
    return files


def body_lines(path: Path) -> tuple[list[str], int]:
    text = path.read_text(encoding="utf-8")
    if path.name == "SKILL.md" and text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            offset = text.count("\n", 0, end + 4) + 1
            return text[end + 4 :].splitlines(), offset
    split = text.splitlines()
    return split, 0


def load_command_skills() -> set[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    commands: set[str] = set()
    for entry in manifest.get("skills", []):
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        if entry.get("activation") == "command":
            commands.add(name)
    return commands


def check_denylist(path: Path, rel: str, lines: list[str], offset: int) -> list[str]:
    violations: list[str] = []
    for index, line in enumerate(lines):
        lineno = offset + index + 1
        for pattern_name, pattern, hint in DENYLIST:
            if (rel, pattern_name) in ALLOWLIST:
                continue
            if pattern.search(line):
                violations.append(f"{rel}:{lineno}: {pattern_name}: {hint}")
    return violations


def check_command_refs(
    path: Path, rel: str, lines: list[str], offset: int, commands: set[str]
) -> list[str]:
    violations: list[str] = []
    own_name = path.parent.name if path.name == "SKILL.md" else ""
    for index, line in enumerate(lines):
        lineno = offset + index + 1
        for match in BACKTICKED.finditer(line):
            name = match.group(1)
            if name not in commands or name == own_name:
                continue
            window = "\n".join(lines[max(0, index - 1) : index + 2])
            if SUGGEST.search(window) and USER.search(window) and RUN.search(window):
                continue
            violations.append(
                f"{rel}:{lineno}: `{name}` is a user-invoked command skill;"
                " say suggest the user run it instead of invoking it"
            )
    return violations


def collect_violations() -> tuple[list[str], int]:
    commands = load_command_skills()
    violations: list[str] = []
    checked = 0
    for path in body_files():
        checked += 1
        rel = str(path.relative_to(REPO_ROOT))
        try:
            lines, offset = body_lines(path)
        except OSError as exc:
            violations.append(f"{rel}: unreadable: {exc}")
            continue
        violations.extend(check_denylist(path, rel, lines, offset))
        violations.extend(check_command_refs(path, rel, lines, offset, commands))
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
        sys.stderr.write(f"skill vocab: {checked - len(violations)}/{checked} files clean\n")
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        sys.stderr.write("\nReword to agent-neutral prose per AGENTS.md.\n")
        return 1
    print(f"skill vocab ok ({checked} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
