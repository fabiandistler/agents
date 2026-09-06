#!/usr/bin/env python3
"""Verify the plugin marketplace stays consistent with the skill catalogue.

Run from repo root:
    python3 scripts/check_plugins.py    # exit 1 on any drift

Checked invariants:
  - `.claude-plugin/marketplace.json` parses and has name, owner, plugins.
  - Every marketplace entry points at an existing `plugins/<name>/` with a
    `.claude-plugin/plugin.json` whose name matches the entry.
  - Every directory under `plugins/` is listed in the marketplace.
  - Every `plugins/<plugin>/skills/<skill>` is a relative symlink to
    `../../../skills/<skill>` whose target contains a SKILL.md.
  - Plugin membership mirrors the `category:` frontmatter exactly: plugin
    `<cat>` contains precisely the skills with `category: <cat>`, so each
    skill ships in exactly one plugin. Skills whose `targets:` frontmatter
    excludes `claude` are left out — the plugins are the Claude distribution.
  - Every `plugins/<plugin>/agents/<agent>.md` has YAML frontmatter with
    `name:` (matching the filename stem) and `description:`.

Each skill's category, activation and targets come from `skills.json` via
`catalogue.py`, not from crawling `skills/`, so a stale manifest makes this
check answer from stale metadata. Run `python3 scripts/build_manifest.py`
first; CI gates it with `build_manifest.py --check` before this check runs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from catalogue import load_catalogue, routed_categories

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def check_marketplace(errors: list[str]) -> list[str]:
    """Validate marketplace.json; return the plugin names it declares."""
    if not MARKETPLACE.is_file():
        errors.append(f"missing {MARKETPLACE.relative_to(REPO_ROOT)}")
        return []
    try:
        data = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"marketplace.json: invalid JSON: {e}")
        return []
    for field in ("name", "owner", "plugins"):
        if field not in data:
            errors.append(f"marketplace.json: missing field '{field}'")
    names = []
    for entry in data.get("plugins", []):
        name = entry.get("name")
        source = entry.get("source", "")
        if not name:
            errors.append(f"marketplace.json: plugin entry without name: {entry}")
            continue
        names.append(name)
        if source != f"./plugins/{name}":
            errors.append(f"marketplace.json: {name}: expected source ./plugins/{name}, got {source!r}")
        manifest = REPO_ROOT / "plugins" / name / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            errors.append(f"{name}: missing plugins/{name}/.claude-plugin/plugin.json")
            continue
        try:
            declared = json.loads(manifest.read_text(encoding="utf-8")).get("name")
        except json.JSONDecodeError as e:
            errors.append(f"plugins/{name}/.claude-plugin/plugin.json: invalid JSON: {e}")
            continue
        if declared != name:
            errors.append(f"plugins/{name}: plugin.json name is {declared!r}")
    return names


def plugin_skills(plugin: str, errors: list[str]) -> set[str]:
    """Return skill names bundled by a plugin, validating each symlink."""
    skills_dir = PLUGINS_DIR / plugin / "skills"
    if not skills_dir.is_dir():
        errors.append(f"{plugin}: missing plugins/{plugin}/skills/")
        return set()
    found: set[str] = set()
    for link in sorted(skills_dir.iterdir()):
        rel = link.relative_to(REPO_ROOT)
        if not link.is_symlink():
            errors.append(f"{rel}: expected a symlink into skills/")
            continue
        expected = f"../../../skills/{link.name}"
        if str(link.readlink()) != expected:
            errors.append(f"{rel}: points to {link.readlink()}, expected {expected}")
            continue
        if not (link / "SKILL.md").is_file():
            errors.append(f"{rel}: target has no SKILL.md")
            continue
        found.add(link.name)
    return found


def check_agents(plugin: str, errors: list[str]) -> None:
    """Validate frontmatter of the plugin's agents/*.md, if any."""
    agents_dir = PLUGINS_DIR / plugin / "agents"
    if not agents_dir.is_dir():
        return
    for md in sorted(agents_dir.glob("*.md")):
        rel = md.relative_to(REPO_ROOT)
        text = md.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            errors.append(f"{rel}: missing YAML frontmatter")
            continue
        frontmatter = text[4:].split("\n---", 1)[0]
        m = re.search(r"^name:\s*(\S+)\s*$", frontmatter, re.M)
        if not m:
            errors.append(f"{rel}: frontmatter has no 'name'")
        elif m.group(1) != md.stem:
            errors.append(f"{rel}: frontmatter name {m.group(1)!r} != filename stem {md.stem!r}")
        if not re.search(r"^description:", frontmatter, re.M):
            errors.append(f"{rel}: frontmatter has no 'description'")


def main() -> int:
    errors: list[str] = []
    catalogue = load_catalogue()
    categories = {entry.name: entry.category for entry in catalogue}
    routed = routed_categories(catalogue)
    plugins = check_marketplace(errors)

    if PLUGINS_DIR.is_dir():
        for child in sorted(PLUGINS_DIR.iterdir()):
            if child.is_dir() and child.name not in plugins:
                errors.append(f"plugins/{child.name}/ exists but is not in marketplace.json")

    for plugin in plugins:
        check_agents(plugin, errors)
        bundled = plugin_skills(plugin, errors)
        members = [entry for entry in catalogue if entry.category == plugin]
        if plugin in routed:
            # Only the router and any command skills register at top level;
            # auto members ride nested under the router.
            members = [e for e in members if e.activation in ("router", "command")]
        # Plugins are the Claude distribution, so a skill that opts out of the
        # claude target ships in neither.
        expected = {e.name for e in members if e.in_target("claude")}
        for s in sorted(expected - bundled):
            errors.append(f"{plugin}: skills/{s} has category: {plugin} but no symlink in plugins/{plugin}/skills/")
        for s in sorted(bundled - expected):
            errors.append(f"{plugin}: bundles {s}, but its SKILL.md says category: {categories.get(s, '?')}")

    uncovered = set(categories.values()) - set(plugins)
    for c in sorted(uncovered):
        errors.append(f"category '{c}' has skills but no plugin in marketplace.json")

    if errors:
        sys.stderr.write("plugin marketplace drift detected:\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        sys.stderr.write(
            "\nKeep .claude-plugin/marketplace.json and plugins/<category>/skills/ "
            "symlinks in sync with each skill's 'category' frontmatter.\n"
        )
        return 1

    # `catalogue` covers every skill including routers, so this count is
    # deliberately higher than check_docs.py's, which excludes them.
    print(
        f"plugin marketplace in sync ({len(plugins)} plugins, "
        f"{len(catalogue)} skills incl. routers)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
