"""End-to-end tests for the dated-claims gate (#582).

Each test builds a fixture repo tree, runs the gate's entry point against it
with --root, and asserts on the exit code and the reported lines.
"""

from pathlib import Path

import check_dated_claims


def run_gate(root: Path, capsys):
    code = check_dated_claims.main(["--root", str(root)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def skill_md(body: str) -> str:
    return f"---\nname: demo\ndescription: Demo.\n---\n\n{body}\n"


def test_iso_dates_and_dated_phrases_fail_with_file_and_line(tmp_path, capsys):
    for index, claim in enumerate(
        [
            "Verified 2026-09-07 against uv.",
            "The last release was 2024-12.",
            "These tools are examples as of 2026.",
            "Flags were checked in October 2026.",
            "Last updated 2025 by the maintainers.",
        ]
    ):
        root = tmp_path / str(index)
        write(root, "skills/demo/SKILL.md", skill_md(f"Intro.\n\n{claim}"))

        code, _, err = run_gate(root, capsys)

        assert code == 1, claim
        assert "skills/demo/SKILL.md:8:" in err, claim
        assert "As of 20YY-MM[-DD]" in err


def test_one_as_of_note_per_file_passes_including_continuation_lines(tmp_path, capsys):
    note = "As of 2026-10, NetArchTest's last release was in 2021,\nts-arch's in 2024-12."
    write(tmp_path, "skills/demo/references/tools.md", f"# Tools\n\n{note}\n\nBody.\n")

    code, out, err = run_gate(tmp_path, capsys)

    assert code == 0, err
    assert "dated claims ok (1 skill texts)" in out


def test_note_must_start_a_paragraph_and_stays_unique(tmp_path, capsys):
    write(
        tmp_path,
        "skills/demo/SKILL.md",
        skill_md("Reviewed once.\nAs of 2026-09-01, Part C was reviewed."),
    )
    write(
        tmp_path,
        "skills/demo/references/twice.md",
        "As of 2026-09-01, first.\n\nAs of 2026-10-01, second.\n",
    )

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/demo/SKILL.md:7: 2026-09-01" in err
    assert "skills/demo/references/twice.md:3: second as-of note" in err


def test_dates_after_the_note_paragraph_still_fail(tmp_path, capsys):
    write(
        tmp_path,
        "skills/demo/SKILL.md",
        skill_md("As of 2026-09-01, verified.\n\nSunset on 2027-03-01."),
    )

    code, _, err = run_gate(tmp_path, capsys)

    assert code == 1
    assert "skills/demo/SKILL.md:8: 2027-03-01" in err


def test_code_and_urls_are_ignored(tmp_path, capsys):
    body = (
        "```markdown\n## [1.2.0] - 2026-09-19\n```\n\n"
        "Built from `schema_fixture.json` (rev `2026-10-02`).\n\n"
        "See <https://example.org/blog/2026-01-26-bounty/>.\n\n"
        "Branch: `poc/<YYYY-MM-DD>`, cited from Smith et al. (2025)."
    )
    write(tmp_path, "skills/demo/SKILL.md", skill_md(body))

    code, out, err = run_gate(tmp_path, capsys)

    assert code == 0, err
    assert "dated claims ok" in out


def test_files_outside_skill_texts_are_not_scanned(tmp_path, capsys):
    write(tmp_path, "skills/demo/SKILL.md", skill_md("Undated."))
    write(tmp_path, "skills/demo/assets/template.md", "Written 2026-09-02.\n")
    write(tmp_path, "docs/notes.md", "Verified 2026-09-02.\n")

    code, out, _ = run_gate(tmp_path, capsys)

    assert code == 0
    assert "(1 skill texts)" in out


def test_unknown_argument_is_a_usage_error(capsys):
    assert check_dated_claims.main(["--bogus"]) == 2
    assert "usage:" in capsys.readouterr().err
