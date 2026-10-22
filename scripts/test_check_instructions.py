"""Tests for the instruction-fragment gate, focused on the `targets:` field (#595).

Each test writes one fragment into a fixture instructions/ directory, points the
gate at it, and asserts on the exit code and the reported error.
"""

import check_instructions


def run_gate(root, monkeypatch, capsys, frontmatter: str):
    instructions = root / "instructions"
    instructions.mkdir(parents=True)
    (instructions / "10-demo.md").write_text(
        f"---\ntitle: Demo\n{frontmatter}---\n\nBody.\n", encoding="utf-8"
    )
    monkeypatch.setattr(check_instructions, "INSTRUCTIONS_DIR", instructions)
    code = check_instructions.main()
    captured = capsys.readouterr()
    return code, captured.err


def test_absent_or_valid_targets_pass(tmp_path, monkeypatch, capsys):
    for label, frontmatter in [
        ("absent", ""),
        ("all", "targets: all\n"),
        ("list", "targets: claude, codex\n"),
    ]:
        code, err = run_gate(tmp_path / label, monkeypatch, capsys, frontmatter)

        assert code == 0, (label, err)


def test_blank_targets_fail(tmp_path, monkeypatch, capsys):
    for label, frontmatter in [
        ("blank", "targets:\n"),
        ("whitespace", "targets:   \n"),
        ("comma", "targets: ,\n"),
    ]:
        code, err = run_gate(tmp_path / label, monkeypatch, capsys, frontmatter)

        assert code == 1, label
        assert "10-demo.md: 'targets' is empty" in err, label


def test_unknown_target_fails(tmp_path, monkeypatch, capsys):
    code, err = run_gate(tmp_path, monkeypatch, capsys, "targets: claude, cursor\n")

    assert code == 1
    assert "unknown value(s) cursor" in err
