from pathlib import Path

from quick_validate import validate_skill


def write_skill(parent: Path, dir_name: str, frontmatter: str) -> Path:
    skill_dir = parent / dir_name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\nBody.\n", encoding="utf-8")
    return skill_dir


def test_name_matching_directory_is_valid(tmp_path):
    skill_dir = write_skill(tmp_path, "demo-skill", "name: demo-skill\ndescription: Does a thing.")

    valid, message = validate_skill(skill_dir)

    assert valid, message


def test_name_differing_from_directory_is_invalid(tmp_path):
    skill_dir = write_skill(tmp_path, "demo-skill", "name: other-skill\ndescription: Does a thing.")

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert "demo-skill" in message
    assert "other-skill" in message


def test_description_budget_is_left_to_check_descriptions(tmp_path, capsys):
    # A router's 450-char budget and the allowlist live in check_descriptions.py;
    # restating a single 250-char budget here warned on every router skill.
    description = "Routes work. " + "x" * 340
    skill_dir = write_skill(
        tmp_path,
        "demo-router",
        f"name: demo-router\ndescription: {description}\nactivation: router",
    )

    valid, message = validate_skill(skill_dir)

    assert valid, message
    assert "WARNING" not in capsys.readouterr().out
