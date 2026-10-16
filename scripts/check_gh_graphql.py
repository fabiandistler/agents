#!/usr/bin/env python3
"""Flag GraphQL-backed gh commands that offer no MCP or REST alternative.

Run from repo root:
    python3 scripts/check_gh_graphql.py    # exit 1 when violations remain

A GraphQL-backed gh command is gh porcelain that talks to GitHub's GraphQL
API: `gh issue ...`, `gh pr ...`, `gh repo view`, `gh release list|view`,
`gh search ...`, `gh label ...`. Claude Code cloud sessions block GraphQL, so
such a step fails there with HTTP 403 while working locally. REST-backed
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
as the value, grouped in one block per follow-up ticket so that each ticket
deletes its own block. An entry that no longer matches a hit is reported as
stale, so a fixed file must also leave the allowlist.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

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

# (relative path, command) -> reason. One block per follow-up ticket of #506;
# a ticket that fixes its files deletes its whole block (header comment
# included) but keeps the `# ----` separator lines, so parallel tickets edit
# non-adjacent lines and merge without conflicts.
ALLOWLIST: dict[tuple[str, str], str] = {
    # ----
    # -- #509 poc-spec-loop: loop runner to REST, PR step wording --
    ("skills/poc-spec-loop/SKILL.md", "gh pr create"): "#509 rewords the PR step",
    ("skills/poc-spec-loop/assets/loop.sh", "gh pr create"): "#509 switches to gh api (REST)",
    # ----
    # -- #510 oss-scouting: issue list/view, linked PRs, default branch, code search --
    ("skills/oss-scouting/SKILL.md", "gh issue list"): "#510 adds the MCP sentence",
    ("skills/oss-scouting/SKILL.md", "gh issue view"): "#510 adds the MCP sentence",
    ("skills/oss-scouting/SKILL.md", "gh pr list"): "#510 adds the MCP sentence",
    ("skills/oss-scouting/SKILL.md", "gh repo view"): "#510 adds the MCP sentence",
    ("skills/oss-scouting/SKILL.md", "gh search code"): "#510 adds the MCP sentence",
    # ----
    # -- #511 release-pr: forge reference PR create/edit/view --
    ("skills/release-pr/references/forges.md", "gh pr create"): "#511 adds the MCP sentence",
    ("skills/release-pr/references/forges.md", "gh pr edit"): "#511 adds the MCP sentence",
    ("skills/release-pr/references/forges.md", "gh pr view"): "#511 adds the MCP sentence",
    # ----
    # -- #512 repo-status PR search and docs/agents issue-tracker conventions --
    ("skills/repo-status/SKILL.md", "gh search prs"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh issue close"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh issue comment"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh issue create"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh issue edit"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh issue list"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh issue view"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh pr"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh pr close"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh pr comment"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh pr diff"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh pr edit"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh pr list"): "#512 adds the MCP sentence",
    ("docs/agents/issue-tracker.md", "gh pr view"): "#512 adds the MCP sentence",
    # ----
}


def scanned_files(root: Path) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []

    def add(path: Path) -> None:
        if not path.is_file():
            return
        real = path.resolve()
        if real in seen:
            return
        seen.add(real)
        files.append(path)

    skills_dir = root / "skills"
    skill_dirs: list[Path] = []
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            skill_dirs.append(skill_dir)
            members = skill_dir / "members"
            if members.is_dir():
                skill_dirs.extend(sorted(p for p in members.iterdir() if p.is_dir()))
    for skill_dir in skill_dirs:
        add(skill_dir / "SKILL.md")
        references = skill_dir / "references"
        if references.is_dir():
            for path in sorted(references.glob("*.md")):
                add(path)
        for sub in ("scripts", "assets"):
            folder = skill_dir / sub
            if not folder.is_dir():
                continue
            for path in sorted(folder.iterdir()):
                if path.suffix in SCRIPT_SUFFIXES and not path.name.startswith("test_"):
                    add(path)
    agents_docs = root / "docs" / "agents"
    if agents_docs.is_dir():
        for path in sorted(agents_docs.glob("*.md")):
            add(path)
    return files


def display_path(root: Path, path: Path) -> str:
    """Path relative to root, with a member symlink shown as its real file."""
    real = path.resolve()
    try:
        return real.relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.relative_to(root).as_posix()


def command_name(match: re.Match[str]) -> str:
    if match.group("group"):
        verb = match.group("verb")
        return f"gh {match.group('group')} {verb}" if verb else f"gh {match.group('group')}"
    return " ".join(match.group(0).split())


def collect(root: Path) -> tuple[list[str], set[tuple[str, str]], int]:
    violations: list[str] = []
    allowed_hits: set[tuple[str, str]] = set()
    files = scanned_files(root)
    for path in files:
        rel = display_path(root, path)
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
            "\nGraphQL is blocked in Claude Code cloud sessions. See AGENTS.md,"
            ' "Conventions for skill authors".\n'
        )
        return 1
    print(f"gh graphql ok ({checked} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
