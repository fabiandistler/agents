"""Tests for the shared instruction-fragment parser and renderer."""

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


def test_target_selection_and_both_claude_rule_shapes_share_rendering():
    always = parse("10-always.md", "title: Always\n")
    path_rule = parse("20-r.md", "title: R\npaths: **/*.R, R/*.R\n")
    codex_only = parse("30-codex.md", "title: Codex\ntargets: codex\npaths: **/*.py\n")

    assert fragments.fragment_matches_target(path_rule, "claude")
    assert not fragments.fragment_matches_target(codex_only, "claude")
    assert fragments.fragment_matches_target(codex_only, "codex")
    with pytest.raises(fragments.InstructionFragmentError, match="invalid target"):
        fragments.fragment_matches_target(always, "all")

    marker = "managed-by: test"
    assert fragments.render_claude_rule(always, marker) == ("---\nmanaged-by: test\n---\n\nRule.\n")
    assert fragments.render_claude_rule(path_rule, marker) == (
        '---\npaths:\n  - "**/*.R"\n  - "R/*.R"\nmanaged-by: test\n---\n\nRule.\n'
    )


def test_bad_frontmatter_and_path_values_are_reported():
    with pytest.raises(fragments.InstructionFragmentError, match="frontmatter block"):
        fragments.parse_fragment("---\ntitle: Demo\n", Path("10-demo.md"))

    path_error = parse("20-path.md", 'title: Path\npaths: **/*.R, bad"path\n')
    assert fragments.validate_fragment(path_error) == [
        "'paths' glob(s) bad\"path contain a quote or backslash"
    ]
