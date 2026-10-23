"""Tests for the project mirror's instruction-rule selection."""

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
