"""AGENTS.md stays under the split target; README.md holds the catalogue (#924)."""

from pathlib import Path

import check_docs

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"
# scripts/hooks/check-file-tokens.sh names 4000 tokens (bytes / 4) as the split target.
SPLIT_TARGET_BYTES = 4000 * 4


def test_agents_md_is_under_the_split_target():
    assert len(AGENTS.read_bytes()) <= SPLIT_TARGET_BYTES


def test_agents_md_keeps_the_sections_checks_cite():
    text = AGENTS.read_text(encoding="utf-8")
    for heading in ("## Conventions for skill authors\n", "## Scripts an agent runs\n"):
        assert heading in text


def test_agents_md_points_to_the_catalogue_instead_of_copying_it():
    text = AGENTS.read_text(encoding="utf-8")
    assert "](skills/" not in text.split("## Skill catalogue", 1)[1].split("\n## ", 1)[0]
    assert "skills.json" in text
    assert "README.md" in text


def test_check_docs_passes_on_the_repository(capsys):
    assert check_docs.main() == 0
    assert "catalogue in sync" in capsys.readouterr().out


def test_check_docs_reports_a_missing_readme_row(tmp_path, monkeypatch, capsys):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    trimmed = "\n".join(
        line for line in readme.splitlines() if not line.startswith("| `skills/tldr/` |")
    )
    assert trimmed != readme
    stale = tmp_path / "README.md"
    stale.write_text(trimmed, encoding="utf-8")
    monkeypatch.setattr(check_docs, "README", stale)

    assert check_docs.main() == 1
    assert "README.md: missing rows for: tldr" in capsys.readouterr().err


def test_check_docs_reports_a_row_under_the_wrong_category(tmp_path, monkeypatch, capsys):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lines = readme.splitlines()
    row = next(line for line in lines if line.startswith("| `skills/tldr/` |"))
    lines.remove(row)
    heading = next(i for i, line in enumerate(lines) if line.endswith("(`personal`)"))
    lines.insert(heading + 1, row)
    moved = tmp_path / "README.md"
    moved.write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.setattr(check_docs, "README", moved)

    assert check_docs.main() == 1
    assert "tldr listed under section `personal`" in capsys.readouterr().err
