"""Regression tests for description budgets and style."""

from pathlib import Path

import check_descriptions


def write_skill(
    root: Path,
    description: str,
    *,
    activation: str = "auto",
    when_to_use: str | None = None,
) -> Path:
    skill_md = root / "skills" / "demo" / "SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = f"---\nname: demo\nactivation: {activation}\ndescription: {description}\n"
    if when_to_use is not None:
        frontmatter += f"when_to_use: {when_to_use}\n"
    skill_md.write_text(f"{frontmatter}---\n\n# Demo\n", encoding="utf-8")
    return skill_md


def run_checker(skill_md: Path, monkeypatch, capsys):
    monkeypatch.setattr(check_descriptions, "find_skill_files", lambda: [skill_md])
    code = check_descriptions.main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_accepts_third_person_auto_description_with_use_when(tmp_path, monkeypatch, capsys):
    skill_md = write_skill(
        tmp_path,
        "Guides architecture decisions. Use when choosing a system structure.",
    )

    code, out, err = run_checker(skill_md, monkeypatch, capsys)

    assert code == 0, err
    assert "descriptions within budget" in out


def test_accepts_use_for_clause_and_third_person_subject(tmp_path, monkeypatch, capsys):
    skill_md = write_skill(
        tmp_path,
        "The skill guides architecture decisions. Use for design reviews.",
    )

    code, _, err = run_checker(skill_md, monkeypatch, capsys)

    assert code == 0, err


def test_rejects_missing_trigger_and_imperative_opening(tmp_path, monkeypatch, capsys):
    skill_md = write_skill(tmp_path, "Guide architecture decisions.")

    code, _, err = run_checker(skill_md, monkeypatch, capsys)

    assert code == 1
    assert "demo: description" in err
    assert "needs a 'Use when' or 'Use for' trigger clause" in err
    assert "must start in third person" in err


def test_router_uses_when_to_use_as_its_trigger_clause(tmp_path, monkeypatch, capsys):
    skill_md = write_skill(
        tmp_path,
        "Routes architecture work to the right member.",
        activation="router",
        when_to_use="Use even when the request omits architecture jargon.",
    )

    code, _, err = run_checker(skill_md, monkeypatch, capsys)

    assert code == 0, err


def test_router_without_when_to_use_needs_a_trigger_in_description(tmp_path, monkeypatch, capsys):
    skill_md = write_skill(
        tmp_path,
        "Routes architecture work to the right member.",
        activation="router",
    )

    code, _, err = run_checker(skill_md, monkeypatch, capsys)

    assert code == 1
    assert "needs a 'Use when' or 'Use for' trigger clause" in err


def test_router_uses_description_trigger_when_when_to_use_is_absent(tmp_path, monkeypatch, capsys):
    skill_md = write_skill(
        tmp_path,
        "Routes architecture work to the right member. Use when choosing a system design.",
        activation="router",
    )

    code, _, err = run_checker(skill_md, monkeypatch, capsys)

    assert code == 0, err


def test_command_description_is_exempt_from_both_style_rules(tmp_path, monkeypatch, capsys):
    skill_md = write_skill(
        tmp_path,
        "Curate shell-command snippets for reuse.",
        activation="command",
    )

    code, _, err = run_checker(skill_md, monkeypatch, capsys)

    assert code == 0, err
