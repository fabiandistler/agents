"""Tests for the SKILL.md frontmatter parser."""

import pytest
import skill_frontmatter


def test_parse_skill_frontmatter_handles_wrapped_values_and_metadata(tmp_path):
    fields = skill_frontmatter.parse_skill_frontmatter(
        "---\n"
        "name: demo\n"
        'description: "First sentence\n'
        '  continues here."\n'
        "metadata:\n"
        '  version: "1.2.3"\n'
        "---\n\nBody.\n",
        tmp_path / "SKILL.md",
    )

    assert fields == {
        "name": "demo",
        "description": "First sentence continues here.",
        "metadata": {"version": "1.2.3"},
    }


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("name: demo\n---\n", "missing opening"),
        ("---\nname: demo\n", "missing closing"),
        ('---\ndescription: "unfinished\n---\n', "unterminated quoted"),
        ("---\ndescription: Use when: needed\n---\n", "invalid YAML"),
    ],
)
def test_parse_skill_frontmatter_rejects_malformed_input(tmp_path, text, message):
    with pytest.raises(ValueError, match=message):
        skill_frontmatter.parse_skill_frontmatter(text, tmp_path / "SKILL.md")
