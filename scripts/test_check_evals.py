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
