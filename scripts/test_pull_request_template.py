"""The GitHub PR template carries the pr skill's body headings.

.github/pull_request_template.md prefills the *Summary* / *Evidence* /
*Merge Danger* format that the vendored pr skill (.claude/skills/pr/SKILL.md)
defines in its fenced ``markdown`` template block. The first test fails when
the two lists of headings differ; the others show that a renamed heading in
either file is caught, without editing the vendored skill.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PR_SKILL = REPO_ROOT / ".claude" / "skills" / "pr" / "SKILL.md"
PR_TEMPLATE = REPO_ROOT / ".github" / "pull_request_template.md"
CONTRIBUTING = REPO_ROOT / "docs" / "contributing.md"

TEMPLATE_BLOCK = re.compile(r"^```markdown\n(.*?)^```$", re.MULTILINE | re.DOTALL)
HEADING = re.compile(r"^#{1,6} +(.+?) *$", re.MULTILINE)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def skill_template_headings(skill_text: str) -> list[str]:
    """Headings inside the skill's first fenced ``markdown`` block."""
    block = TEMPLATE_BLOCK.search(skill_text)
    if block is None:
        msg = "pr skill has no ```markdown template block"
        raise ValueError(msg)
    return HEADING.findall(block.group(1))


def pr_template_headings(template_text: str) -> list[str]:
    """Headings of the PR template, ignoring its HTML comments."""
    return HEADING.findall(HTML_COMMENT.sub("", template_text))


def test_pr_template_matches_skill_template() -> None:
    skill = skill_template_headings(PR_SKILL.read_text(encoding="utf-8"))
    template = pr_template_headings(PR_TEMPLATE.read_text(encoding="utf-8"))
    assert skill == ["Summary", "Evidence", "Merge Danger"]
    assert template == skill


def test_pr_template_links_skill() -> None:
    assert ".claude/skills/pr/SKILL.md" in PR_TEMPLATE.read_text(encoding="utf-8")


def test_contributing_names_sections_and_links_skill() -> None:
    text = CONTRIBUTING.read_text(encoding="utf-8")
    for section in ("*Summary*", "*Evidence*", "*Merge Danger*"):
        assert section in text
    assert "(../.claude/skills/pr/SKILL.md)" in text


@pytest.mark.parametrize("old", ["Summary", "Evidence", "Merge Danger"])
def test_renamed_heading_in_skill_is_caught(old: str) -> None:
    skill_text = PR_SKILL.read_text(encoding="utf-8").replace(
        f"## {old}\n", f"## {old} renamed\n", 1
    )
    template = pr_template_headings(PR_TEMPLATE.read_text(encoding="utf-8"))
    assert skill_template_headings(skill_text) != template


@pytest.mark.parametrize("old", ["Summary", "Evidence", "Merge Danger"])
def test_renamed_heading_in_pr_template_is_caught(old: str) -> None:
    skill = skill_template_headings(PR_SKILL.read_text(encoding="utf-8"))
    template_text = PR_TEMPLATE.read_text(encoding="utf-8").replace(
        f"## {old}\n", f"## {old} renamed\n", 1
    )
    assert pr_template_headings(template_text) != skill


def test_skill_without_template_block_raises() -> None:
    with pytest.raises(ValueError, match="template block"):
        skill_template_headings("## Summary\n")
