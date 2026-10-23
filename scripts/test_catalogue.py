"""Tests for the shared catalogue helpers the check scripts read skills through."""

import json
from pathlib import Path

import catalogue
import pytest


def test_unique_real_files_resolves_member_links_keeps_order_and_skips_missing(tmp_path):
    real = tmp_path / "skills" / "member" / "SKILL.md"
    real.parent.mkdir(parents=True)
    real.write_text("member\n", encoding="utf-8")
    other = tmp_path / "skills" / "other" / "SKILL.md"
    other.parent.mkdir(parents=True)
    other.write_text("other\n", encoding="utf-8")
    members = tmp_path / "skills" / "router" / "members"
    members.mkdir(parents=True)
    (members / "member").symlink_to("../../member")

    files = catalogue.unique_real_files(
        [
            members / "member" / "SKILL.md",
            tmp_path / "skills" / "missing" / "SKILL.md",
            other,
            real,
        ]
    )

    assert files == [real.resolve(), other.resolve()]


def test_unique_real_files_skips_directories(tmp_path: Path):
    (tmp_path / "references").mkdir()

    assert catalogue.unique_real_files([tmp_path / "references"]) == []


def test_parse_skill_frontmatter_handles_wrapped_values_and_metadata(tmp_path):
    fields = catalogue.parse_skill_frontmatter(
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
        catalogue.parse_skill_frontmatter(text, tmp_path / "SKILL.md")


def test_entry_from_skill_file_builds_complete_default_entry(tmp_path):
    skill_md = tmp_path / "skills" / "demo" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(
        "---\n"
        "name: demo\n"
        "description: Demo skill. More detail.\n"
        "category: workflow\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )

    entry = catalogue.entry_from_skill_file(skill_md, tmp_path)

    assert entry == catalogue.SkillEntry(
        name="demo",
        summary="Demo skill.",
        category="workflow",
        path="skills/demo/SKILL.md",
    )
    assert entry.to_manifest() == {
        "name": "demo",
        "summary": "Demo skill.",
        "category": "workflow",
        "path": "skills/demo/SKILL.md",
    }


def test_load_catalogue_reads_summary_and_path(tmp_path):
    manifest_path = tmp_path / "skills.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "1",
                "skills": [
                    {
                        "name": "demo",
                        "summary": "Demo summary.",
                        "category": "workflow",
                        "path": "skills/demo/SKILL.md",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    [entry] = catalogue.load_catalogue(manifest_path)

    assert entry.summary == "Demo summary."
    assert entry.path == "skills/demo/SKILL.md"
    assert entry.in_environment("chat")
    assert entry.in_target("opencode")


def test_load_catalogue_fails_loudly_for_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="skill manifest not found"):
        catalogue.load_catalogue(tmp_path / "missing.json")
