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


def test_entry_from_skill_file_rejects_router_name_mismatch(tmp_path):
    skill_md = tmp_path / "skills" / "other" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(
        "---\nname: other\ndescription: Routes skills.\ncategory: workflow\n"
        "activation: router\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="router's name.*equal its category"):
        catalogue.entry_from_skill_file(skill_md, tmp_path)


def test_load_catalogue_preserves_order_defaults_and_named_selections(tmp_path):
    entries = [
        {"name": "architecture", "category": "architecture", "activation": "router"},
        {
            "name": "ddd",
            "category": "architecture",
            "environments": ["coding"],
            "targets": ["codex"],
        },
        {"name": "pypet-snippets", "category": "workflow", "activation": "command"},
        {
            "name": "docs",
            "category": "communication",
            "environments": ["chat"],
            "targets": ["opencode"],
        },
    ]
    manifest_path = tmp_path / "skills.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "1",
                "skills": [
                    {
                        "summary": f"{entry['name']} summary.",
                        "path": f"skills/{entry['name']}/SKILL.md",
                        **entry,
                    }
                    for entry in entries
                ],
            }
        ),
        encoding="utf-8",
    )

    catalogue_entries = catalogue.load_catalogue(manifest_path)

    assert [entry.name for entry in catalogue_entries] == [
        "architecture",
        "ddd",
        "pypet-snippets",
        "docs",
    ]
    assert catalogue_entries[0].summary == "architecture summary."
    assert catalogue_entries[0].path == "skills/architecture/SKILL.md"
    assert catalogue_entries[0].in_environment("chat")
    assert catalogue_entries[0].in_target("opencode")
    assert [entry.name for entry in catalogue.top_level_entries(catalogue_entries)] == [
        "architecture",
        "pypet-snippets",
        "docs",
    ]
    assert [
        entry.name for entry in catalogue.router_members(catalogue_entries, "architecture")
    ] == ["ddd"]
    assert [entry.name for entry in catalogue.entries_for_target(catalogue_entries, "codex")] == [
        "architecture",
        "ddd",
        "pypet-snippets",
    ]
    assert [
        entry.name for entry in catalogue.entries_for_environment(catalogue_entries, "chat")
    ] == ["architecture", "pypet-snippets", "docs"]


def test_load_catalogue_fails_loudly_for_missing_or_malformed_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="skill manifest not found"):
        catalogue.load_catalogue(tmp_path / "missing.json")

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid skills.json"):
        catalogue.load_catalogue(malformed)

    missing_skills = tmp_path / "missing-skills.json"
    missing_skills.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="'skills' array"):
        catalogue.load_catalogue(missing_skills)


def test_load_catalogue_rejects_invalid_paths_and_router_identity(tmp_path):
    manifest = tmp_path / "skills.json"
    manifest.write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "name": "demo",
                        "summary": "Demo.",
                        "category": "workflow",
                        "path": "../outside/SKILL.md",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="relative source path"):
        catalogue.load_catalogue(manifest)

    manifest.write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "name": "demo",
                        "summary": "Demo.",
                        "category": "workflow",
                        "path": "skills/demo/SKILL.md",
                        "activation": "router",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="router's name.*equal its category"):
        catalogue.load_catalogue(manifest)


def test_target_and_environment_queries_reject_unknown_names():
    with pytest.raises(ValueError, match="unknown target"):
        catalogue.entries_for_target([], "unknown")
    with pytest.raises(ValueError, match="unknown environment"):
        catalogue.entries_for_environment([], "unknown")
