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


COMMAND_FRONTMATTER = "name: demo-command\ndescription: Does a thing.\nactivation: command"
OPENCODE_METADATA = 'metadata:\n  opencode/slash: "true"\n  opencode/autoinvoke: "false"'
NO_IMPLICIT = "policy:\n  allow_implicit_invocation: false\n"


def write_sidecar(skill_dir: Path, text: str) -> None:
    (skill_dir / "agents").mkdir()
    (skill_dir / "agents" / "openai.yaml").write_text(text, encoding="utf-8")


def test_command_skill_with_flag_and_sidecar_is_valid(tmp_path):
    skill_dir = write_skill(
        tmp_path,
        "demo-command",
        COMMAND_FRONTMATTER + "\ndisable-model-invocation: true\n" + OPENCODE_METADATA,
    )
    write_sidecar(skill_dir, NO_IMPLICIT)

    valid, message = validate_skill(skill_dir)

    assert valid, message


def test_command_skill_without_disable_model_invocation_is_invalid(tmp_path):
    skill_dir = write_skill(
        tmp_path, "demo-command", COMMAND_FRONTMATTER + "\n" + OPENCODE_METADATA
    )
    write_sidecar(skill_dir, NO_IMPLICIT)

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert "disable-model-invocation" in message


def test_command_skill_without_sidecar_is_invalid(tmp_path):
    skill_dir = write_skill(
        tmp_path,
        "demo-command",
        COMMAND_FRONTMATTER + "\ndisable-model-invocation: true\n" + OPENCODE_METADATA,
    )

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert "agents/openai.yaml" in message


def test_command_skill_sidecar_allowing_implicit_invocation_is_invalid(tmp_path):
    skill_dir = write_skill(
        tmp_path,
        "demo-command",
        COMMAND_FRONTMATTER + "\ndisable-model-invocation: true\n" + OPENCODE_METADATA,
    )
    write_sidecar(skill_dir, "policy:\n  allow_implicit_invocation: true\n")

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert "allow_implicit_invocation" in message


def test_command_skill_requires_opencode_metadata(tmp_path):
    skill_dir = write_skill(
        tmp_path, "demo-command", COMMAND_FRONTMATTER + "\ndisable-model-invocation: true"
    )
    write_sidecar(skill_dir, NO_IMPLICIT)

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert "opencode/slash" in message


def test_command_skill_requires_string_metadata_values(tmp_path):
    skill_dir = write_skill(
        tmp_path,
        "demo-command",
        COMMAND_FRONTMATTER
        + "\ndisable-model-invocation: true\nmetadata:\n"
        + '  opencode/slash: "true"\n  opencode/autoinvoke: false',
    )
    write_sidecar(skill_dir, NO_IMPLICIT)

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert "opencode/autoinvoke" in message


def test_auto_skill_needs_no_sidecar(tmp_path):
    skill_dir = write_skill(
        tmp_path, "demo-skill", "name: demo-skill\ndescription: Does a thing.\nactivation: auto"
    )

    valid, message = validate_skill(skill_dir)

    assert valid, message


VALID_FRONTMATTER = "name: demo-skill\ndescription: Does a thing."
REPO_ROOT_PATH_MESSAGE = (
    "Repo-root skill script path (SKILL.md:7: skills/foo/scripts/): reference bundled "
    "scripts relative to the skill directory (scripts/...) and pass the target repo as "
    "an argument"
)


def fail_reading(monkeypatch, unreadable_name: str) -> None:
    original = Path.read_text

    def read_text(self, *args, **kwargs):
        if self.name == unreadable_name:
            raise PermissionError(13, "Permission denied", str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)


def test_unreadable_skill_md_fails_without_path_wording(tmp_path, monkeypatch):
    skill_dir = write_skill(tmp_path, "demo-skill", VALID_FRONTMATTER)
    fail_reading(monkeypatch, "SKILL.md")

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert "SKILL.md: unreadable:" in message
    assert "Repo-root skill script path" not in message


def test_unreadable_reference_fails_with_its_label(tmp_path, monkeypatch):
    skill_dir = write_skill(tmp_path, "demo-skill", VALID_FRONTMATTER)
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    fail_reading(monkeypatch, "guide.md")

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert "references/guide.md: unreadable:" in message
    assert "Repo-root skill script path" not in message


def test_readable_repo_root_script_path_message_is_unchanged(tmp_path):
    skill_dir = write_skill(tmp_path, "demo-skill", VALID_FRONTMATTER)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8") + "Run skills/foo/scripts/x.py.\n",
        encoding="utf-8",
    )

    valid, message = validate_skill(skill_dir)

    assert not valid
    assert message == REPO_ROOT_PATH_MESSAGE
