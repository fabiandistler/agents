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
    skill ships in exactly one plugin.
  - Every `plugins/<plugin>/kb/<topic>` is a relative symlink to
    `../../../skills/<skill>/references` whose target contains at least one
    Markdown page.
  - If `plugins/<plugin>/.mcp.json` exists it parses as JSON, and when it
    references `${CLAUDE_PLUGIN_ROOT}/mcp-wiki-server` the plugin has a
    `mcp-wiki-server` symlink to `../../mcp-wiki-server`.
  - Every `plugins/<plugin>/agents/<agent>.md` has YAML frontmatter with
    `name:` (matching the filename stem) and `description:`, and every
    `${CLAUDE_PLUGIN_ROOT}/...` path in its body resolves inside the plugin.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
PLUGINS_DIR = REPO_ROOT / "plugins"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

CATEGORY_FIELD = re.compile(r"^category:\s*(\S+)\s*$", re.M)
ACTIVATION_FIELD = re.compile(r"^activation:\s*(\S+)\s*$", re.M)
PLUGIN_ROOT_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s)]+)")


def skill_categories() -> dict[str, str]:
    categories: dict[str, str] = {}
    for child in sorted(SKILLS_DIR.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and not child.name.startswith(".") and skill_md.is_file():
            m = CATEGORY_FIELD.search(skill_md.read_text(encoding="utf-8"))
            categories[child.name] = m.group(1) if m else ""
    return categories


def skill_activations() -> dict[str, str]:
    activations: dict[str, str] = {}
    for child in sorted(SKILLS_DIR.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and not child.name.startswith(".") and skill_md.is_file():
            m = ACTIVATION_FIELD.search(skill_md.read_text(encoding="utf-8"))
            activations[child.name] = m.group(1) if m else "auto"
    return activations


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


def check_kb(plugin: str, errors: list[str]) -> None:
    """Validate the plugin's kb/ topic symlinks, if any."""
    kb_dir = PLUGINS_DIR / plugin / "kb"
    if not kb_dir.is_dir():
        return
    target_re = re.compile(r"^\.\./\.\./\.\./skills/[^/]+/references$")
    for link in sorted(kb_dir.iterdir()):
        rel = link.relative_to(REPO_ROOT)
        if not link.is_symlink():
            errors.append(f"{rel}: expected a symlink into skills/<skill>/references")
            continue
        if not target_re.match(str(link.readlink())):
            errors.append(f"{rel}: points to {link.readlink()}, expected ../../../skills/<skill>/references")
            continue
        if not link.is_dir():
            errors.append(f"{rel}: target does not exist")
            continue
        if not any(link.glob("*.md")):
            errors.append(f"{rel}: target has no Markdown pages")


def check_mcp(plugin: str, errors: list[str]) -> None:
    """Validate the plugin's .mcp.json and its mcp-wiki-server symlink, if any."""
    mcp_json = PLUGINS_DIR / plugin / ".mcp.json"
    if not mcp_json.is_file():
        return
    rel = mcp_json.relative_to(REPO_ROOT)
    try:
        text = mcp_json.read_text(encoding="utf-8")
        json.loads(text)
    except json.JSONDecodeError as e:
        errors.append(f"{rel}: invalid JSON: {e}")
        return
    if "${CLAUDE_PLUGIN_ROOT}/mcp-wiki-server" in text:
        link = PLUGINS_DIR / plugin / "mcp-wiki-server"
        if not link.is_symlink() or str(link.readlink()) != "../../mcp-wiki-server":
            errors.append(
                f"{rel}: references ${{CLAUDE_PLUGIN_ROOT}}/mcp-wiki-server but "
                f"plugins/{plugin}/mcp-wiki-server is not a symlink to ../../mcp-wiki-server"
            )


def check_agent_paths(md: Path, plugin_dir: Path, rel: Path, text: str, errors: list[str]) -> None:
    """Every ${CLAUDE_PLUGIN_ROOT}/... path an agent names must exist.

    install.sh --target=codex resolves these against the plugin directory, and
    Claude Code resolves them the same way at runtime, so a path that does not
    exist is an instruction the subagent cannot follow. Routed categories nest
    their skills under `skills/<router>/members/`, which is the usual way these
    go stale.
    """
    for m in PLUGIN_ROOT_PATH.finditer(text):
        ref = m.group(1).rstrip(".,;:")
        if not (plugin_dir / ref).exists():
            errors.append(f"{rel}: ${{CLAUDE_PLUGIN_ROOT}}/{ref} does not exist")


def check_agents(plugin: str, errors: list[str]) -> None:
    """Validate frontmatter and plugin-root paths of the plugin's agents/*.md."""
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
        check_agent_paths(md, PLUGINS_DIR / plugin, rel, text, errors)


def main() -> int:
    errors: list[str] = []
    categories = skill_categories()
    activations = skill_activations()
    # A category is routed when it ships a skill with activation: router (named
    # after the category). Its auto skills are nested under the router's
    # members/ dir rather than symlinked flat into the plugin, so only the
    # router itself (plus any user-invoked command skills) registers at top
    # level. build_routers.py --check validates the nested members/ symlinks.
    routed = {
        cat for name, cat in categories.items() if activations.get(name) == "router"
    }
    plugins = check_marketplace(errors)

    if PLUGINS_DIR.is_dir():
        for child in sorted(PLUGINS_DIR.iterdir()):
            if child.is_dir() and child.name not in plugins:
                errors.append(f"plugins/{child.name}/ exists but is not in marketplace.json")

    for name, category in sorted(categories.items()):
        if not category:
            errors.append(f"skills/{name}: SKILL.md has no 'category' frontmatter")

    for plugin in plugins:
        check_kb(plugin, errors)
        check_mcp(plugin, errors)
        check_agents(plugin, errors)
        bundled = plugin_skills(plugin, errors)
        if plugin in routed:
            # Only the router and any command skills register at top level;
            # auto members ride nested under the router.
            expected = {
                s
                for s, c in categories.items()
                if c == plugin and activations.get(s) in ("router", "command")
            }
        else:
            expected = {s for s, c in categories.items() if c == plugin}
        for s in sorted(expected - bundled):
            errors.append(f"{plugin}: skills/{s} has category: {plugin} but no symlink in plugins/{plugin}/skills/")
        for s in sorted(bundled - expected):
            errors.append(f"{plugin}: bundles {s}, but its SKILL.md says category: {categories.get(s, '?')}")

    uncovered = {c for c in categories.values() if c} - set(plugins)
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

    print(f"plugin marketplace in sync ({len(plugins)} plugins, {len(categories)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
