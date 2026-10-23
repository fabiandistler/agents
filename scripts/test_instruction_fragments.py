"""Tests for the shared instruction-fragment parser and renderer."""

import subprocess
import sys
from pathlib import Path

import instruction_fragments as fragments
import pytest


def parse(name: str, frontmatter: str, body: str = "\nRule.\n"):
    return fragments.parse_fragment(f"---\n{frontmatter}---\n{body}", Path(name))


def test_parser_reads_only_frontmatter_and_normalizes_body():
    fragment = parse(
        "10-demo.md",
        "title: Demo\ntargets: codex\n",
        "\n\nFirst line\n\n\npaths: **/*.R\n\nLast line\n\n",
    )

    assert fragment.fields == {"title": "Demo", "targets": "codex"}
    assert fragment.body == "First line\n\n\npaths: **/*.R\n\nLast line"


def test_missing_targets_means_all_but_explicit_empty_is_invalid():
    unrestricted = parse("10-all.md", "title: All\n")
    assert fragments.validate_fragment(unrestricted) == []
    assert all(fragments.fragment_matches_target(unrestricted, t) for t in fragments.TARGETS)

    empty = parse("20-empty.md", "title: Empty\ntargets:   \n")
    assert fragments.validate_fragment(empty) == [
        "'targets' is empty (omit the field to mean every agent)"
    ]
    with pytest.raises(fragments.InstructionFragmentError, match="'targets' is empty"):
        fragments.fragment_matches_target(empty, "claude")


def test_selection_and_both_claude_rule_shapes_share_rendering():
    always = parse("10-always.md", "title: Always\n")
    path_rule = parse("20-r.md", "title: R\npaths: **/*.R, R/*.R\n")
    codex_only = parse("30-codex.md", "title: Codex\ntargets: codex\npaths: **/*.py\n")

    assert fragments.select_fragments([always, path_rule, codex_only], "claude", "block") == [
        always
    ]
    assert fragments.select_fragments(
        [always, path_rule, codex_only], "claude", "claude-rules"
    ) == [path_rule]
    assert fragments.select_fragments([always, path_rule, codex_only], "codex", "block") == [
        always,
        path_rule,
        codex_only,
    ]

    marker = "managed-by: test"
    assert fragments.render_claude_rule(always, marker) == ("---\nmanaged-by: test\n---\n\nRule.\n")
    assert fragments.render_claude_rule(path_rule, marker) == (
        '---\npaths:\n  - "**/*.R"\n  - "R/*.R"\nmanaged-by: test\n---\n\nRule.\n'
    )


def test_block_renderer_uses_the_shared_body_and_python_pointer():
    ordinary = parse("10-demo.md", "title: Demo\n", "\nFirst.\n\n")
    python = parse("30-python.md", "title: Python\n", "\nPython rules.\n\n")

    assert (
        fragments.render_instruction_block(
            [ordinary, python], "codex", python_pointer="~/.agents/instructions/30-python.md"
        )
        == "First.\n\nFor Python work, read `~/.agents/instructions/30-python.md`."
    )
    assert fragments.render_instruction_block([ordinary, python], "claude") == (
        "First.\n\nPython rules."
    )


def test_bad_frontmatter_and_path_values_are_reported():
    with pytest.raises(fragments.InstructionFragmentError, match="frontmatter block"):
        fragments.parse_fragment("---\ntitle: Demo\n", Path("10-demo.md"))

    path_error = parse("20-path.md", 'title: Path\npaths: **/*.R, bad"path\n')
    assert fragments.validate_fragment(path_error) == [
        "'paths' glob(s) bad\"path contain a quote or backslash"
    ]


def test_cli_runs_from_outside_the_repository_and_documents_exit_codes(tmp_path):
    script = Path(fragments.__file__).resolve()
    help_result = subprocess.run(  # noqa: S603 - test-owned argv invokes this repository's CLI
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert len(help_result.stdout.splitlines()) <= 25
    assert (
        "Exit codes: 0 success; 2 usage error; 3 invalid fragment or file error."
        in help_result.stdout
    )
    assert help_result.stdout.count("python3 scripts/instruction_fragments.py") == 2
    for command in ("list", "body", "block", "claude-rule"):
        command_help = subprocess.run(  # noqa: S603 - test-owned argv invokes this repository's CLI
            [sys.executable, str(script), command, "--help"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert command_help.returncode == 0
        assert len(command_help.stdout.splitlines()) <= 25
        assert (
            "Exit codes: 0 success; 2 usage error; 3 invalid fragment or file error."
            in command_help.stdout
        )
        assert command_help.stdout.count("python3 scripts/instruction_fragments.py") == 2

    source = tmp_path / "10-demo.md"
    source.write_text("---\ntitle: Demo\n---\n\nRule.\n\n", encoding="utf-8")
    rendered = subprocess.run(  # noqa: S603 - test-owned argv invokes this repository's CLI
        [
            sys.executable,
            str(script),
            "block",
            "--target",
            "codex",
        ],
        cwd=tmp_path,
        input=f"{source}\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert rendered.stdout == "Rule."

    invalid = tmp_path / "20-invalid.md"
    invalid.write_text("---\ntitle: Invalid\npaths:\n---\n\nRule.\n", encoding="utf-8")
    failed = subprocess.run(  # noqa: S603 - test-owned argv invokes this repository's CLI
        [sys.executable, str(script), "body", "--fragment", str(invalid)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode == 3
    assert "'paths' is empty" in failed.stderr
