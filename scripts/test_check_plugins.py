"""Tests for the read-only pin in the plugin check.

The review-decisions classifier reads untrusted text (a diff, an issue), so
its tool list is pinned to read-only tools. Each test copies the real agent
file into a fixture plugins tree, changes its tool list the way a later edit
might, and runs the pin check against that tree.
"""

import shutil
from pathlib import Path

import check_plugins

REPO_ROOT = Path(__file__).resolve().parent.parent
CLASSIFIER = REPO_ROOT / "plugins" / "workflow" / "agents" / "review-decisions-classifier.md"


def fixture_plugins(tmp_path: Path, old: str | None = None, new: str = "") -> Path:
    """Copy the classifier into tmp_path/plugins, optionally replacing `old` by `new`."""
    target = tmp_path / "plugins" / "workflow" / "agents" / CLASSIFIER.name
    target.parent.mkdir(parents=True)
    shutil.copy(CLASSIFIER, target)
    if old is not None:
        text = target.read_text(encoding="utf-8")
        assert old in text, f"fixture expects {old!r} in the classifier"
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return tmp_path / "plugins"


def pin_errors(plugins_dir: Path) -> list[str]:
    errors: list[str] = []
    check_plugins.check_read_only_agents(plugins_dir, errors)
    return errors


def test_shipped_classifier_passes_the_pin(tmp_path):
    assert pin_errors(fixture_plugins(tmp_path)) == []


def test_repo_plugin_check_passes():
    assert check_plugins.main() == 0


def test_adding_a_write_tool_fails(tmp_path):
    plugins = fixture_plugins(tmp_path, "tools: Read,", "tools: Write, Read,")

    errors = pin_errors(plugins)

    assert len(errors) == 1
    assert "review-decisions-classifier.md" in errors[0]
    assert "Write" in errors[0]


def test_adding_an_edit_tool_fails(tmp_path):
    plugins = fixture_plugins(tmp_path, "tools: Read,", "tools: Edit, NotebookEdit, Read,")

    errors = pin_errors(plugins)

    assert len(errors) == 1
    assert "Edit" in errors[0] and "NotebookEdit" in errors[0]


def test_adding_a_forge_tool_fails(tmp_path):
    plugins = fixture_plugins(tmp_path, "tools: Read,", "tools: mcp__github__issue_read, Read,")

    errors = pin_errors(plugins)

    assert len(errors) == 1
    assert "mcp__github__issue_read" in errors[0]


def test_dropping_the_tool_list_fails_because_the_agent_would_inherit_every_tool(tmp_path):
    text = CLASSIFIER.read_text(encoding="utf-8")
    tools_line = next(line for line in text.splitlines() if line.startswith("tools:"))
    plugins = fixture_plugins(tmp_path, tools_line + "\n", "")

    errors = pin_errors(plugins)

    assert len(errors) == 1
    assert "no 'tools'" in errors[0]


def test_a_pinned_agent_that_is_missing_fails(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()

    errors = pin_errors(plugins)

    assert len(errors) == 1
    assert "review-decisions-classifier.md" in errors[0]
    assert "missing" in errors[0]
