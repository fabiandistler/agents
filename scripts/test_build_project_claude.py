"""Tests for the project mirror's instruction-rule selection."""

import json
from pathlib import Path

import build_project_claude as project_claude


def write_fragment(directory: Path, name: str, frontmatter: str, body: str) -> None:
    (directory / name).write_text(
        f"---\ntitle: {name}\n{frontmatter}---\n\n{body}\n",
        encoding="utf-8",
    )


def test_wanted_rules_uses_shared_rendering_and_keeps_repo_filters(tmp_path, monkeypatch):
    instructions = tmp_path / "instructions"
    instructions.mkdir()
    write_fragment(instructions, "10-always.md", "", "Always rule.")
    write_fragment(instructions, "20-r.md", "paths: **/*.R\n", "R rule.")
    write_fragment(instructions, "30-no-match.md", "paths: **/*.sql\n", "SQL rule.")
    write_fragment(instructions, "40-codex.md", "targets: codex\n", "Codex rule.")
    write_fragment(instructions, "60-code-comments.md", "", "Skipped here.")

    monkeypatch.setattr(project_claude, "INSTRUCTIONS_DIR", instructions)
    monkeypatch.setattr(project_claude, "CLAUDE_DIR", tmp_path / ".claude")
    monkeypatch.setattr(project_claude, "tracked_files", lambda: ["README.md", "src/data.R"])

    rules = project_claude.wanted_rules()

    assert set(rules) == {
        tmp_path / ".claude/rules/agents-10-always.md",
        tmp_path / ".claude/rules/agents-20-r.md",
    }
    assert rules[tmp_path / ".claude/rules/agents-10-always.md"] == (
        "---\nmanaged-by: fabiandistler/agents build_project_claude.py\n---\n\nAlways rule.\n"
    )
    assert rules[tmp_path / ".claude/rules/agents-20-r.md"] == (
        '---\npaths:\n  - "**/*.R"\n'
        "managed-by: fabiandistler/agents build_project_claude.py\n"
        "---\n\nR rule.\n"
    )


def test_synced_copy_of_every_marketplace_disabled_plugin_is_disabled():
    settings = {
        "enabledPlugins": {
            "ai-ml@fabiandistler-agents": False,
            "tdd-pack@other": True,
            "mattpocock-skills@mattpocock": False,
            "local@inline": False,
            "folder@skills-dir": False,
            "unrelated@synced": True,
        },
        "hooks": {},
    }

    plugins = project_claude.with_synced_plugins_disabled(settings)["enabledPlugins"]

    assert list(plugins.items()) == [
        ("ai-ml@fabiandistler-agents", False),
        ("ai-ml@synced", False),
        ("tdd-pack@other", True),
        ("mattpocock-skills@mattpocock", False),
        ("mattpocock-skills@synced", False),
        ("local@inline", False),
        ("folder@skills-dir", False),
        ("unrelated@synced", True),
    ]


def test_synced_entries_are_regenerated_in_place_and_idempotent():
    settings = {"enabledPlugins": {"ai-ml@synced": True, "ai-ml@fabiandistler-agents": False}}

    once = project_claude.with_synced_plugins_disabled(settings)
    twice = project_claude.with_synced_plugins_disabled(once)

    assert list(once["enabledPlugins"].items()) == [
        ("ai-ml@fabiandistler-agents", False),
        ("ai-ml@synced", False),
    ]
    assert twice == once


def test_committed_settings_disable_synced_copy_of_each_mirrored_plugin():
    """Every plugin whose skills `.claude/skills` mirrors stays off when synced (#768)."""
    plugins = json.loads(project_claude.SETTINGS_PATH.read_text(encoding="utf-8"))["enabledPlugins"]
    skill_plugins = {path.parent.name for path in project_claude.PLUGINS_DIR.glob("*/skills")}
    mirrored = skill_plugins | {"mattpocock-skills"}

    assert len(skill_plugins) >= 6
    assert {name for name in mirrored if plugins.get(f"{name}@synced") is not False} == set()


LINT_ON_EDIT_ENTRY = {
    "matcher": "Edit|Write|MultiEdit",
    "hooks": [
        {
            "type": "command",
            "command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/lint-on-edit.sh',
            "timeout": 60,
        }
    ],
}


def test_committed_settings_run_lint_on_edit_once_after_file_edits():
    """One hand-written PostToolUse entry runs the ruff hooks after each file edit (#806)."""
    hooks = json.loads(project_claude.SETTINGS_PATH.read_text(encoding="utf-8"))["hooks"]

    (entry,) = hooks["PostToolUse"]
    assert entry["matcher"] == "Edit|Write|MultiEdit"
    (hook,) = entry["hooks"]
    assert hook["command"] == '"$CLAUDE_PROJECT_DIR"/.claude/hooks/lint-on-edit.sh'
    assert 0 < hook["timeout"] < 600


def test_regenerated_settings_keep_the_hand_written_post_tool_use_entry(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"hooks": {"PostToolUse": [LINT_ON_EDIT_ENTRY]}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(project_claude, "SETTINGS_PATH", settings_path)

    once = json.loads(project_claude.wanted_settings())
    settings_path.write_text(json.dumps(once), encoding="utf-8")
    twice = json.loads(project_claude.wanted_settings())

    assert once["hooks"]["PostToolUse"] == [LINT_ON_EDIT_ENTRY]
    assert twice == once
