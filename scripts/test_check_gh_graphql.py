"""End-to-end tests for the GraphQL-backed gh gate (#508).

Each test builds a fixture repo tree, runs the gate's entry point against it
with --root, and asserts on the exit code and the reported lines.
"""

from pathlib import Path

import check_gh_graphql


def run_gate(root: Path, monkeypatch, capsys, allowlist: dict | None = None):
    """Run the gate on a fixture root with an empty allowlist unless given one."""
    monkeypatch.setattr(check_gh_graphql, "ALLOWLIST", allowlist or {})
    code = check_gh_graphql.main(["--root", str(root)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def skill_md(body: str) -> str:
    return f"---\nname: demo\ndescription: Demo.\n---\n\n{body}\n"


def test_bare_graphql_command_fails_naming_file_line_command_and_direction(
    tmp_path, monkeypatch, capsys
):
    write(tmp_path, "skills/demo/SKILL.md", skill_md("List them:\n\n`gh issue list --state open`"))

    code, _, err = run_gate(tmp_path, monkeypatch, capsys)

    assert code == 1
    assert "skills/demo/SKILL.md:8: gh issue list:" in err
    assert "GitHub MCP" in err
    assert "gh api" in err


def test_same_line_passes_with_mcp_sentence_or_gh_api_in_window(tmp_path, monkeypatch, capsys):
    for index, nearby in enumerate(
        [
            "Use the GitHub MCP tools if the session has them; otherwise `gh`:",
            "Or call the REST endpoint with `gh api repos/<owner>/<repo>/issues`.",
        ]
    ):
        root = tmp_path / str(index)
        write(root, "skills/demo/SKILL.md", skill_md(f"{nearby}\n\n`gh issue list --state open`"))

        code, out, err = run_gate(root, monkeypatch, capsys)

        assert code == 0, (nearby, err)
        assert "gh graphql ok" in out


def test_alternative_outside_window_does_not_count(tmp_path, monkeypatch, capsys):
    far = "\n".join(["Use the GitHub MCP tools if the session has them."] + ["filler"] * 10)
    write(tmp_path, "skills/demo/SKILL.md", skill_md(f"{far}\n`gh pr create --fill`"))

    code, _, err = run_gate(tmp_path, monkeypatch, capsys)

    assert code == 1
    assert "gh pr create" in err


def test_rest_backed_commands_never_trigger(tmp_path, monkeypatch, capsys):
    for index, command in enumerate(
        [
            "gh api repos/o/r/pulls --method POST -f base=main",
            "gh run list --branch main --limit 1",
            "gh release create v1.0.0 --notes-file NEWS.md",
        ]
    ):
        root = tmp_path / str(index)
        write(root, "skills/demo/SKILL.md", skill_md(f"`{command}`"))

        code, _, err = run_gate(root, monkeypatch, capsys)

        assert code == 0, (command, err)


def test_each_graphql_family_is_flagged(tmp_path, monkeypatch, capsys):
    for index, (command, reported) in enumerate(
        [
            ("gh repo view o/r --json defaultBranchRef", "gh repo view"),
            ("gh release list --limit 5", "gh release list"),
            ("gh search prs --author=@me", "gh search prs"),
            ("gh label create bug", "gh label create"),
        ]
    ):
        root = tmp_path / str(index)
        write(root, "skills/demo/SKILL.md", skill_md(f"`{command}`"))

        code, _, err = run_gate(root, monkeypatch, capsys)

        assert code == 1, command
        assert f": {reported}:" in err


def test_allowlist_entry_suppresses_its_hit(tmp_path, monkeypatch, capsys):
    write(tmp_path, "skills/demo/SKILL.md", skill_md("`gh issue view 1 --comments`"))
    allowlist = {("skills/demo/SKILL.md", "gh issue view"): "#999 rewords this"}

    code, _, err = run_gate(tmp_path, monkeypatch, capsys, allowlist)

    assert code == 0, err


def test_allowlist_entry_without_hit_is_reported_stale(tmp_path, monkeypatch, capsys):
    write(tmp_path, "skills/demo/SKILL.md", skill_md("No GitHub steps here."))
    allowlist = {("skills/demo/SKILL.md", "gh issue view"): "#999 rewords this"}

    code, _, err = run_gate(tmp_path, monkeypatch, capsys, allowlist)

    assert code == 1
    assert "skills/demo/SKILL.md: gh issue view: stale allowlist entry" in err


def test_symlinked_member_copy_is_reported_once_under_its_real_path(tmp_path, monkeypatch, capsys):
    write(tmp_path, "skills/member/SKILL.md", skill_md("`gh pr list`"))
    members = tmp_path / "skills" / "router" / "members"
    members.mkdir(parents=True)
    (members / "member").symlink_to("../../member")
    write(tmp_path, "skills/router/SKILL.md", skill_md("Routes."))

    code, _, err = run_gate(tmp_path, monkeypatch, capsys)

    assert code == 1
    assert err.count("gh pr list") == 1
    assert "skills/member/SKILL.md:6: gh pr list:" in err


def test_scans_references_scripts_and_agents_docs_but_not_tests_or_vendored(
    tmp_path, monkeypatch, capsys
):
    write(tmp_path, "skills/demo/SKILL.md", skill_md("Clean."))
    write(tmp_path, "skills/demo/references/forge.md", "gh pr view --json url\n")
    write(tmp_path, "skills/demo/scripts/open.sh", "gh pr create --fill\n")
    write(tmp_path, "skills/demo/assets/run.sh", "gh issue comment 1 --body x\n")
    write(tmp_path, "skills/demo/scripts/test_open.py", "ARGV = 'gh pr create'\n")
    write(tmp_path, "docs/agents/issue-tracker.md", "Run `gh issue close 1`.\n")
    write(tmp_path, ".claude/skills/vendored/SKILL.md", skill_md("`gh issue list`"))

    code, _, err = run_gate(tmp_path, monkeypatch, capsys)

    assert code == 1
    assert "skills/demo/references/forge.md:1: gh pr view:" in err
    assert "skills/demo/scripts/open.sh:1: gh pr create:" in err
    assert "skills/demo/assets/run.sh:1: gh issue comment:" in err
    assert "docs/agents/issue-tracker.md:1: gh issue close:" in err
    assert "test_open.py" not in err
    assert "vendored" not in err


def test_repo_itself_is_clean():
    assert check_gh_graphql.main([]) == 0


def test_top_level_markdown_is_in_scope(tmp_path, monkeypatch, capsys):
    write(tmp_path, "MAINTENANCE.md", "# Catalog\n\nsee `gh pr list --state open`\n")

    code, _, err = run_gate(tmp_path, monkeypatch, capsys)

    assert code == 1
    assert "MAINTENANCE.md:3: gh pr list:" in err


def test_markdown_below_top_level_outside_skills_and_agent_docs_is_out_of_scope(
    tmp_path, monkeypatch, capsys
):
    write(tmp_path, "docs/wiki/notes.md", "`gh pr list --state open`\n")

    code, out, _ = run_gate(tmp_path, monkeypatch, capsys)

    assert code == 0
    assert "gh graphql ok" in out
