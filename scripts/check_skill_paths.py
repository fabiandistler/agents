#!/usr/bin/env python3
"""Flag relative paths in skill texts that point at nothing.

Run from repo root:
    python3 scripts/check_skill_paths.py    # exit 1 when a dead path remains

A skill sends the agent to its bundled files by path. When a file is renamed
or deleted and the text is not, the agent opens a path that does not exist
and improvises (skill-audit checklist item R1). This gate checks every
skills/**/SKILL.md and skills/**/references/*.md, router `members/` copies
included (symlinked copies resolve to one file and are checked once):

- skill paths: `references/…`, `scripts/…`, `assets/…`, `evals/…` and
  `members/…` mentioned anywhere — prose, code spans, fenced commands — must
  exist relative to the skill directory. Skill texts write these paths from
  the skill root even inside references/, so that is the base for both.
- Markdown links: a relative link target (a sibling `[x](metrics.md)`, a
  `../other/SKILL.md`) must exist relative to the linking file, as a Markdown
  renderer resolves it. The `#anchor` part is not checked.

Code is checked, unlike in check_dated_claims.py: a path in a code span or a
fenced command is the invocation the agent runs, so it is the place a dead
path hurts most. URLs are removed first; their path segments are not files.
A path with a glob (`scripts/test_*.py`) passes when it matches a file; one
with a placeholder (`members/<name>/SKILL.md`) is not a path and is skipped.

A skill path missing from the skill also passes when it exists in another
skill whose name the same paragraph gives in backticks ("`coupling-cohesion`'s
`scripts/lcom.py`"), or at the repo root (the router notes naming
`scripts/build_routers.py`, a maintainer pointer). That root fallback means
this gate cannot catch a skill that runs a repo-root script; quick_validate.py
covers the `skills/<name>/scripts/` spelling of that mistake.
Stdlib-only, matching the other scripts/check_*.py gates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from catalogue import unique_real_files

REPO_ROOT = Path(__file__).resolve().parent.parent

USAGE = """usage: check_skill_paths.py [--root DIR] [--help]

Flag references/, scripts/, assets/, evals/ and members/ paths and relative
Markdown links in skills/**/SKILL.md and skills/**/references/*.md that do not
exist. Skill paths resolve from the skill directory, links from the file.

  --root DIR  repository root to scan (default: this script's repo)
  --help      show this message

examples:
  python3 scripts/check_skill_paths.py
  python3 scripts/check_skill_paths.py --root /path/to/checkout

exit: 0 every path exists | 1 dead paths found | 2 usage error
"""

DIRECTION = "point the path at the file's current location, or drop the mention if the file is gone"

URL = re.compile(r"[a-z][a-z0-9+.-]*://[^\s)>`]+", re.IGNORECASE)
# Not preceded by a path or word character, so `skills/x/scripts/y.py` and
# `foo/references/` are not read as skill-relative paths.
SKILL_PATH = re.compile(
    r"(?<![\w/.~-])(?:references|scripts|assets|evals|members)/[\w.*<>{}/-]*[\w*>}]"
)
MARKDOWN_LINK = re.compile(r"\]\((?P<target><[^>]*>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINK_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
BACKTICKED_NAME = re.compile(r"`([a-z0-9][a-z0-9-]*)`")
GLOB = re.compile(r"[*?\[]")


def skill_texts(root: Path) -> list[Path]:
    skills_dir = root / "skills"
    return unique_real_files(
        sorted([*skills_dir.rglob("SKILL.md"), *skills_dir.rglob("references/*.md")])
    )


def skill_dir_of(path: Path, skills_dir: Path) -> Path:
    """The top-level skill directory that owns a (resolved) skill text."""
    return skills_dir / path.relative_to(skills_dir).parts[0]


def dead_paths(path: Path, root: Path) -> list[tuple[int, str]]:
    """(line number, path) for each relative path in `path` that does not exist."""
    skills_dir = (root / "skills").resolve()
    skill_dir = skill_dir_of(path, skills_dir)
    dead: list[tuple[int, str]] = []
    for paragraph in paragraphs(path.read_text(encoding="utf-8")):
        named = [
            skills_dir / name
            for _, line in paragraph
            for name in BACKTICKED_NAME.findall(line)
            if (skills_dir / name / "SKILL.md").is_file()
        ]
        skill_bases = [skill_dir, *named, root]
        for number, line in paragraph:
            for match in MARKDOWN_LINK.finditer(line):
                target = match.group("target").strip("<>").split("#", 1)[0]
                if not target or LINK_SCHEME.match(target) or target.startswith("/"):
                    continue
                if not exists(path.parent, target):
                    dead.append((number, target))
            # Link targets were resolved above, from the file; the rest is prose.
            prose = URL.sub("", MARKDOWN_LINK.sub("]()", line))
            for match in SKILL_PATH.finditer(prose):
                mention = match.group(0).rstrip(".")
                if not any(exists(base, mention) for base in skill_bases):
                    dead.append((number, mention))
    return list(dict.fromkeys(dead))


def paragraphs(text: str) -> list[list[tuple[int, str]]]:
    """Numbered lines grouped into blank-line-separated paragraphs."""
    groups: list[list[tuple[int, str]]] = [[]]
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            groups[-1].append((number, line))
        elif groups[-1]:
            groups.append([])
    return [group for group in groups if group]


def exists(base: Path, mention: str) -> bool:
    if "<" in mention or "{" in mention:
        return True  # a placeholder such as members/<name>/SKILL.md, not a path
    if GLOB.search(mention):
        return any(base.glob(mention))
    return (base / mention).exists()


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
        f"{path.relative_to(root)}:{number}: {mention}"
        for path in files
        for number, mention in dead_paths(path, root)
    ]
    if violations:
        sys.stderr.write(f"dead skill paths: {len(violations)} in {len(files)} skill texts\n")
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        sys.stderr.write(f"\nFix: {DIRECTION}.\n")
        return 1
    print(f"skill paths ok ({len(files)} skill texts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
