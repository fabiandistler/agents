"""Tests for check_evals: the success line names the mode it ran in."""

import check_evals


def test_success_line_names_strict_mode(monkeypatch, capsys):
    monkeypatch.setattr(check_evals, "collect_gaps", lambda: ([], 2, 2))
    assert check_evals.main(["--strict"]) == 0
    assert capsys.readouterr().out == "evals coverage: 2/2 auto+router skills (strict)\n"


def test_default_run_reports_gaps_as_warn_only(monkeypatch, capsys):
    monkeypatch.setattr(check_evals, "collect_gaps", lambda: (["x: missing"], 1, 2))
    assert check_evals.main([]) == 0
    captured = capsys.readouterr()
    assert captured.out == "evals coverage: 1/2 auto+router skills (warn-only)\n"
    assert "warn: x: missing" in captured.err


def command_skill_with_evals(monkeypatch, tmp_path, evals_text):
    """Point the check at one command skill whose evals.json holds evals_text."""
    from catalogue import SkillEntry

    path = tmp_path / "evals.json"
    path.write_text(evals_text, encoding="utf-8")
    entry = SkillEntry(
        name="cmd", summary="s", category="workflow", path="skills/cmd", activation="command"
    )
    monkeypatch.setattr(check_evals, "load_catalogue", lambda: [entry])
    monkeypatch.setattr(check_evals, "eval_path", lambda name: path)


def test_command_skill_that_ships_evals_gets_its_shape_checked(monkeypatch, tmp_path):
    command_skill_with_evals(monkeypatch, tmp_path, '{"should_trigger": ["only one"]}')
    gaps, _, _ = check_evals.collect_gaps()
    assert any("should_trigger" in gap for gap in gaps)
    assert any("should_not_trigger" in gap for gap in gaps)


def test_command_skill_without_evals_stays_exempt(monkeypatch, tmp_path):
    command_skill_with_evals(monkeypatch, tmp_path, "{}")
    (tmp_path / "evals.json").unlink()
    assert check_evals.collect_gaps() == ([], 0, 0)
