#!/usr/bin/env python3
"""Mirror this repo's skills, subagents and instructions into `.claude/`.

Run from repo root:
    python3 scripts/build_project_claude.py            # write .claude/ links + rules
    python3 scripts/build_project_claude.py --check    # exit 1 if .claude/ is stale

Cloud sessions (Claude Code on the web) start from a fresh clone. They do not
install the plugins a repository enables in `.claude/settings.json`, and they
never see `~/.claude/`. What they do load is the clone's own `.claude/skills/`,
`.claude/agents/` and `.claude/rules/`. This script keeps those in sync with
the catalogue, so a cloud session in this repo gets the same skills and rules
as a local install:

  1. `.claude/skills/<name>` -> `../../skills/<name>` for every top-level skill
     (routers, unrouted auto skills, command skills) whose `environments`
     include `coding` and whose `targets` include `claude`. Router members stay
     nested under their router, as in the plugins.
  2. `.claude/agents/<name>.md` -> the plugins' subagents.
  3. `.claude/rules/agents-<fragment>.md` rendered from `instructions/`: always
     loaded, or path-scoped when the fragment has `paths:` (same rendering as
     install.sh). A path-scoped fragment is skipped while no tracked file
     matches its globs (the R rules in this Python/Markdown repo).

It owns only symlinks pointing into this repo and rule files carrying the
`managed-by:` marker; anything else in `.claude/` (hand-written subagents, the
vendored third-party skills) is left alone. Reads skills.json, so run
build_manifest.py first. Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "skills.json"
INSTRUCTIONS_DIR = REPO_ROOT / "instructions"
PLUGINS_DIR = REPO_ROOT / "plugins"
CLAUDE_DIR = REPO_ROOT / ".claude"
ENVIRONMENT = "coding"
RULE_MARKER = "managed-by: fabiandistler/agents build_project_claude.py"
FIELD = re.compile(r"^([a-z]+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)


def wanted_skill_links() -> dict[Path, Path]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    skills = manifest["skills"]
    routed = {s["category"] for s in skills if s.get("activation") == "router"}
    links: dict[Path, Path] = {}
    for skill in skills:
        activation = skill.get("activation", "auto")
        if activation == "auto" and skill["category"] in routed:
            continue  # a router member, reached through its router
        if ENVIRONMENT not in skill.get("environments", [ENVIRONMENT]):
            continue
        if "claude" not in skill.get("targets", ["claude"]):
            continue
        source = REPO_ROOT / Path(skill["path"]).parent
        links[CLAUDE_DIR / "skills" / skill["name"]] = source
    return links


def wanted_agent_links() -> dict[Path, Path]:
    return {CLAUDE_DIR / "agents" / md.name: md for md in sorted(PLUGINS_DIR.glob("*/agents/*.md"))}


def split_fragment(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 3)
    fields = dict(FIELD.findall(text[4 : end + 1]))
    return fields, text[end + 5 :]


def tracked_files() -> list[str]:
    return subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()


def matches_any(globs: list[str], files: list[str]) -> bool:
    patterns = globs + [g.removeprefix("**/") for g in globs if g.startswith("**/")]
    return any(fnmatchcase(f, p) for f in files for p in patterns)


def wanted_rules() -> dict[Path, str]:
    rules: dict[Path, str] = {}
    files = tracked_files()
    for fragment in sorted(INSTRUCTIONS_DIR.glob("*.md")):
        fields, body = split_fragment(fragment.read_text(encoding="utf-8"))
        targets = [t.strip() for t in fields.get("targets", "all").split(",")]
        if "all" not in targets and "claude" not in targets:
            continue
        # Quoted YAML list: a bare `**/*.R` parses as a YAML alias, and Claude
        # loads a rule whose frontmatter does not parse unconditionally.
        header = "---\n"
        globs = [g.strip() for g in fields.get("paths", "").split(",") if g.strip()]
        if globs and not matches_any(globs, files):
            continue  # path-scoped to files this repo does not have
        if globs:
            header += "paths:\n" + "".join(f'  - "{g}"\n' for g in globs)
        header += f"{RULE_MARKER}\n---\n\n"
        rules[CLAUDE_DIR / "rules" / f"agents-{fragment.name}"] = header + body.lstrip("\n")
    return rules


def is_ours(link: Path) -> bool:
    if not link.is_symlink():
        return False
    target = (link.parent / os.readlink(link)).resolve()
    return target.is_relative_to(REPO_ROOT) and not target.is_relative_to(CLAUDE_DIR)


def sync(check: bool) -> list[str]:
    drift: list[str] = []

    def act(message: str, apply) -> None:
        drift.append(message)
        if not check:
            apply()

    for kind, wanted in (("skills", wanted_skill_links()), ("agents", wanted_agent_links())):
        directory = CLAUDE_DIR / kind
        for link, source in wanted.items():
            rel = os.path.relpath(source, link.parent)
            if link.is_symlink() and os.readlink(link) == rel:
                continue
            if link.exists() and not link.is_symlink():
                drift.append(
                    f"{link.relative_to(REPO_ROOT)} exists and is not a link; resolve by hand"
                )
                continue

            def relink(link=link, rel=rel) -> None:
                link.parent.mkdir(parents=True, exist_ok=True)
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(rel)

            act(f"link {link.relative_to(REPO_ROOT)} -> {rel}", relink)
        if directory.is_dir():
            for entry in sorted(directory.iterdir()):
                if entry not in wanted and is_ours(entry):
                    act(f"remove {entry.relative_to(REPO_ROOT)}", entry.unlink)

    rules = wanted_rules()
    for path, content in rules.items():
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue

        def write(path=path, content=content) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        act(f"write {path.relative_to(REPO_ROOT)}", write)
    rules_dir = CLAUDE_DIR / "rules"
    if rules_dir.is_dir():
        for path in sorted(rules_dir.glob("agents-*.md")):
            if path not in rules and RULE_MARKER in path.read_text(encoding="utf-8"):
                act(f"remove {path.relative_to(REPO_ROOT)}", path.unlink)
    return drift


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if .claude/ is out of date")
    args = parser.parse_args()
    drift = sync(check=args.check)
    for line in drift:
        (sys.stderr if args.check else sys.stdout).write(f"  {line}\n")
    if args.check and drift:
        sys.stderr.write(".claude/ is stale; run python3 scripts/build_project_claude.py\n")
        return 1
    print(
        f".claude/ in sync ({len(drift)} change(s) applied)"
        if not args.check
        else ".claude/ in sync"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
