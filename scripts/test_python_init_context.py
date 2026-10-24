"""Tests for the Claude `uv init` context hook and its settings entries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build_project_claude
import python_init_context as hook


def test_context_injects_project_baseline_without_frontmatter_or_check_markers(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "30-python.md"
    baseline.write_text(
        "---\ntitle: Python\npaths: **/*.py\n---\n\n"
        "## Python\n\n<!-- python-project-baseline:start -->\n"
        "Use uv for Python package development.\n"
        "<!-- python-project-baseline:end -->\n",
        encoding="utf-8",
    )

    context = hook.context_for(
        {"tool_name": "Bash", "tool_input": {"command": "uv init --package demo"}},
        baseline,
    )

    assert context == "## Python\n\nUse uv for Python package development."


def test_hook_ignores_non_bash_and_non_init_commands(tmp_path: Path) -> None:
    missing_baseline = tmp_path / "missing.md"

    assert (
        hook.context_for(
            {"tool_name": "Read", "tool_input": {"command": "uv init demo"}},
            missing_baseline,
        )
        is None
    )
    assert (
        hook.context_for(
            {"tool_name": "Bash", "tool_input": {"command": "uv run pytest"}},
            missing_baseline,
        )
        is None
    )


def test_hook_settings_preserve_foreign_handlers_and_are_idempotent() -> None:
    settings: dict[str, object] = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "keep-this-hook"}],
                }
            ]
        }
    }
    command = 'python3 "$CLAUDE_PROJECT_DIR"/scripts/python_init_context.py --baseline project.md'

    installed = hook.with_claude_hook(settings, command)
    repeated: Any = hook.with_claude_hook(installed, command)
    entry = repeated["hooks"]["PreToolUse"][-1]["hooks"][0]

    assert repeated == installed
    assert entry["if"] == "Bash(uv init*)"
    assert entry["command"] == command
    assert hook.without_claude_hook(installed) == settings


def test_project_mirror_contains_uv_init_hook_for_cloud_sessions() -> None:
    generated_settings = json.loads(build_project_claude.wanted_settings())
    committed_settings = json.loads(build_project_claude.SETTINGS_PATH.read_text(encoding="utf-8"))
    handlers = [
        handler for group in generated_settings["hooks"]["PreToolUse"] for handler in group["hooks"]
    ]
    python_hook = next(handler for handler in handlers if handler.get("if") == "Bash(uv init*)")

    assert generated_settings == committed_settings
    assert "scripts/python_init_context.py" in python_hook["command"]
    assert "instructions/30-python.md" in python_hook["command"]
