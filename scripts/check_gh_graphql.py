#!/usr/bin/env python3
"""Flag GraphQL-backed gh commands that offer no MCP or REST alternative.

Run from repo root:
    python3 scripts/check_gh_graphql.py    # exit 1 when violations remain

A GraphQL-backed gh command is gh porcelain that talks to GitHub's GraphQL
API: `gh issue ...`, `gh pr ...`, `gh repo view`, `gh release list|view`,
`gh search ...`, `gh label ...`. Such a step fails in sessions where GitHub's
GraphQL endpoint is blocked, while working locally. REST-backed
commands (`gh api ...`, `gh run ...`) always pass.

A step an agent executes states the operation and then uses the canonical
sentence from AGENTS.md ("Conventions for skill authors"):

    Use the GitHub MCP tools if the session has them; otherwise `gh` ...

keeping the gh command as the fallback for agents without the GitHub MCP. A
script that runs headlessly cannot call MCP tools, so it uses `gh api` against
the REST endpoint instead. A hit passes when the window of WINDOW lines on
either side mentions the GitHub MCP or `gh api`.

Scope: every skills/*/SKILL.md, skills/*/references/*.md, skill scripts and
assets (skills/*/scripts/*, skills/*/assets/*, test_*.py excluded), and
docs/agents/*.md. Symlinked router-member copies resolve to their real file
and are counted once. Vendored skills under .claude/ are out of scope; report
those upstream. Stdlib-only, matching the other scripts/check_*.py gates.

Exemptions live in ALLOWLIST as (relative path, command) keys with the reason
as the value. The list is currently empty; add to it only for a command that
must stay bare on purpose, with the reason. An entry that no longer matches a
hit is reported as stale, so a fixed file must also leave the allowlist.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from catalogue import unique_real_files

REPO_ROOT = Path(__file__).resolve().parent.parent

USAGE = """usage: check_gh_graphql.py [--root DIR] [--help]

Flag GraphQL-backed gh porcelain (gh issue/pr/search/label, gh repo view,
gh release list|view) in skills and docs/agents unless the GitHub MCP or
`gh api` is named within the surrounding lines.

  --root DIR  repository root to scan (default: this script's repo)
  --help      show this message

examples:
  python3 scripts/check_gh_graphql.py
  python3 scripts/check_gh_graphql.py --root /path/to/checkout

exit: 0 no violations | 1 violations or stale allowlist entries | 2 usage error
"""

CANONICAL = "Use the GitHub MCP tools if the session has them; otherwise `gh` ..."
DIRECTION = (
    f'state the operation, then "{CANONICAL}"; in a headless script use `gh api` (REST) instead'
)

# Lines on either side of a hit that may carry the MCP or REST alternative.
WINDOW = 5

GRAPHQL_COMMAND = re.compile(
    r"\bgh\s+(?:"
    r"(?P<group>issue|pr|search|label)(?:\s+(?P<verb>[a-z][a-z-]*))?"
    r"|repo\s+view"
    r"|release\s+(?:list|view)"
    r")\b"
)
ALTERNATIVE = re.compile(r"github\s+mcp|\bgh\s+api\b", re.IGNORECASE)

SCRIPT_SUFFIXES = {".py", ".sh", ".md"}

ALLOWLIST: dict[tuple[str, str], str] = {}


def scanned_files(root: Path) -> list[Path]:
    """Every in-scope file, resolved to its real path and listed once.

    Router `members/` entries are symlinks to top-level skills, so walking the
    top-level skill directories already covers them.
    """
    candidates: list[Path] = []
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            candidates.append(skill_dir / "SKILL.md")
            candidates.extend(sorted(skill_dir.glob("references/*.md")))
            for sub in ("scripts", "assets"):
                candidates.extend(
                    path
                    for path in sorted(skill_dir.glob(f"{sub}/*"))
                    if path.suffix in SCRIPT_SUFFIXES and not path.name.startswith("test_")
                )
    candidates.extend(sorted(root.glob("docs/agents/*.md")))
    return unique_real_files(candidates)


def command_name(match: re.Match[str]) -> str:
    if match.group("group"):
        verb = match.group("verb")
        return f"gh {match.group('group')} {verb}" if verb else f"gh {match.group('group')}"
    return " ".join(match.group(0).split())


def collect(root: Path) -> tuple[list[str], set[tuple[str, str]], int]:
    violations: list[str] = []
    allowed_hits: set[tuple[str, str]] = set()
    files = scanned_files(root)
    real_root = root.resolve()
    for path in files:
        rel = path.relative_to(real_root).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            for match in GRAPHQL_COMMAND.finditer(line):
                command = command_name(match)
                if (rel, command) in ALLOWLIST:
                    allowed_hits.add((rel, command))
                    continue
                window = "\n".join(lines[max(0, index - WINDOW) : index + WINDOW + 1])
                if ALTERNATIVE.search(window):
                    continue
                violations.append(f"{rel}:{index + 1}: {command}: {DIRECTION}")
    return violations, allowed_hits, len(files)


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
    if not root.is_dir():
        sys.stderr.write(f"--root is not a directory: {root}\n")
        return 2

    violations, allowed_hits, checked = collect(root)
    stale = sorted(set(ALLOWLIST) - allowed_hits)
    for rel, command in stale:
        violations.append(
            f"{rel}: {command}: stale allowlist entry (no hit left); delete it from ALLOWLIST"
        )
    if violations:
        sys.stderr.write(f"gh graphql: {len(violations)} problem(s) in {checked} files\n")
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        sys.stderr.write(
            "\nGraphQL-backed gh porcelain fails in sessions where GitHub's GraphQL"
            ' endpoint is blocked. See AGENTS.md, "Conventions for skill authors".\n'
        )
        return 1
    print(f"gh graphql ok ({checked} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
