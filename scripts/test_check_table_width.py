"""End-to-end tests for the table-width gate.

Each test builds a fixture repo tree, runs the gate's entry point against it
with --root, and asserts on the exit code and the reported lines.
"""

from pathlib import Path

import check_table_width


def run_gate(root: Path, capsys):
    code = check_table_width.main(["--root", str(root)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def skill_md(body: str) -> str:
    return f"---\nname: demo\ndescription: Demo.\n---\n\n{body}\n"


def test_four_column_table_fails_with_file_line_and_width(tmp_path, capsys):
    table = "| A | B | C | D |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |"
    write(tmp_path, "skills/demo/SKILL.md", skill_md(f"Intro.\n\n{table}"))

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/demo/SKILL.md:8: 4 columns" in err
    assert "nested list" in err


def test_three_columns_and_delimiter_variants_pass(tmp_path, capsys):
    body = (
        "| A | B | C |\n|:--|:-:|--:|\n| 1 | 2 | 3 |\n\n"
        "A | B\n--- | ---\n1 | 2\n\n"
        "Text above a rule.\n\n---\n\nNot a table."
    )
    write(tmp_path, "skills/demo/SKILL.md", skill_md(body))

    code, out, err = run_gate(tmp_path, capsys)

    assert code == 0, err
    assert "table width ok (1 skill texts)" in out


def test_width_comes_from_the_delimiter_row_not_header_pipes(tmp_path, capsys):
    body = "| Command | Effect |\n|---|---|\n| `a \\| b` | pipes |"
    write(tmp_path, "skills/demo/SKILL.md", skill_md(body))

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 0, err


def test_tables_inside_fences_count_whatever_the_language_tag(tmp_path, capsys):
    template = "| ID | Element | Type | Technology |\n|----|----|----|----|\n| ... |"
    body = f"```\n{template}\n```\n\n~~~markdown\n{template}\n~~~"
    write(tmp_path, "skills/demo/SKILL.md", skill_md(body))

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/demo/SKILL.md:7: 4 columns" in err
    assert "skills/demo/SKILL.md:13: 4 columns" in err


def test_references_and_assets_are_scanned_but_docs_are_not(tmp_path, capsys):
    wide = "| A | B | C | D | E |\n|---|---|---|---|---|\n"
    write(tmp_path, "skills/demo/SKILL.md", skill_md("Narrow."))
    write(tmp_path, "skills/demo/references/ref.md", f"# Ref\n\n{wide}")
    write(tmp_path, "skills/demo/assets/template.md", wide)
    write(tmp_path, "docs/notes.md", wide)
    write(tmp_path, "README.md", wide)

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/demo/references/ref.md:3: 5 columns" in err
    assert "skills/demo/assets/template.md:1: 5 columns" in err
    assert "docs/" not in err
    assert "README.md" not in err


def test_symlinked_member_copy_is_reported_once(tmp_path, capsys):
    wide = "| A | B | C | D |\n|---|---|---|---|\n"
    write(tmp_path, "skills/demo/SKILL.md", skill_md(wide))
    (tmp_path / "skills/router/members").mkdir(parents=True)
    (tmp_path / "skills/router/members/demo").symlink_to("../../demo")

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert err.count("4 columns") == 1
    assert "skills/demo/SKILL.md:6: 4 columns" in err


def test_unknown_argument_is_a_usage_error(capsys):
    assert check_table_width.main(["--bogus"]) == 2
    assert "usage:" in capsys.readouterr().err
