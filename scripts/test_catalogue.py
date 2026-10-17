"""Tests for the shared catalogue helpers the check scripts read skills through."""

from pathlib import Path

import catalogue


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
