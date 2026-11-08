"""Vendoring rules of scripts/vendor_mattpocock_skills.py, against a local fake upstream.

EXCLUDED names are never copied, INCLUDED_IN_PROGRESS skills are copied from
`skills/in-progress/`, and a missing in-progress skill fails with exit 3
instead of vendoring a set without it.
"""

import json
import subprocess
import sys
from pathlib import Path

import vendor_mattpocock_skills as vendor


def _skill(root: Path, rel: str) -> None:
    (root / rel).mkdir(parents=True)
    (root / rel / "SKILL.md").write_text(f"---\nname: {Path(rel).name}\n---\n", encoding="utf-8")


def _fake_upstream(tmp_path: Path, *, with_in_progress: bool) -> Path:
    upstream = tmp_path / "upstream"
    released = ["skills/engineering/tdd", "skills/engineering/pr", "skills/engineering/ask-matt"]
    for rel in released:
        _skill(upstream, rel)
    if with_in_progress:
        _skill(upstream, "skills/in-progress/chief-of-staff")
    (upstream / ".claude-plugin").mkdir()
    (upstream / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": "9.9.9", "skills": [f"./{r}" for r in released]}), encoding="utf-8"
    )
    (upstream / "LICENSE").write_text("MIT\n", encoding="utf-8")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "fake"]):
        subprocess.run(  # noqa: S603 -- test creates a local fixture repository with argv.
            [  # noqa: S607 -- Git intentionally resolves from PATH.
                "git",
                "-c",
                "user.email=t@e",
                "-c",
                "user.name=t",
                *args,
            ],
            cwd=upstream,
            check=True,
        )
    return upstream


def _run(tmp_path: Path, monkeypatch, *, with_in_progress: bool = True) -> int:
    vendor_dir = tmp_path / "vendor"
    (tmp_path / "skills").mkdir()
    monkeypatch.setattr(vendor, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(vendor, "VENDOR_DIR", vendor_dir)
    monkeypatch.setattr(vendor, "LOCK_PATH", vendor_dir / "lock.json")
    monkeypatch.setattr(vendor, "REPO_ROOT", tmp_path)
    upstream = _fake_upstream(tmp_path, with_in_progress=with_in_progress)
    monkeypatch.setattr(vendor, "UPSTREAM", str(upstream))
    monkeypatch.setattr(sys, "argv", ["vendor_mattpocock_skills.py"])
    return vendor.main()


def test_in_progress_skill_is_vendored_and_excluded_are_not(tmp_path, monkeypatch):
    skills_dir, vendor_dir = tmp_path / "skills", tmp_path / "vendor"
    assert _run(tmp_path, monkeypatch) == 0
    assert sorted(p.name for p in skills_dir.iterdir()) == ["chief-of-staff", "pr", "tdd"]
    lock = json.loads((vendor_dir / "lock.json").read_text(encoding="utf-8"))
    assert lock["skills"] == ["chief-of-staff", "pr", "tdd"]


def test_missing_in_progress_skill_fails_without_writing(tmp_path, monkeypatch):
    skills_dir, vendor_dir = tmp_path / "skills", tmp_path / "vendor"
    assert _run(tmp_path, monkeypatch, with_in_progress=False) == 3
    assert list(skills_dir.iterdir()) == []
    assert not (vendor_dir / "lock.json").exists()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 -- test drives a local fixture repository with argv.
        ["git", "-c", "user.email=t@e", "-c", "user.name=t", *args],  # noqa: S607 -- Git from PATH.
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _check_upstream(monkeypatch) -> int:
    monkeypatch.setattr(sys, "argv", ["vendor_mattpocock_skills.py", "--check-upstream"])
    return vendor.main()


def test_check_upstream_targets_the_newest_release_tag(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, monkeypatch) == 0
    upstream = Path(vendor.UPSTREAM)
    locked = _git(upstream, "rev-parse", "HEAD")
    _git(upstream, "tag", "v1.10.0")  # lightweight, at the locked commit
    _git(upstream, "commit", "-q", "--allow-empty", "-m", "unreleased work on main")
    # Each newer commit carries a tag that must not win: a lexically larger
    # version, a pre-release, a non-release name. main itself is not the target.
    _git(upstream, "tag", "-a", "v1.9.0", "-m", "older version, newer commit")
    _git(upstream, "tag", "v2.0.0-rc.1")
    _git(upstream, "tag", "not-a-release")
    capsys.readouterr()
    assert _check_upstream(monkeypatch) == 0
    assert f"(v1.10.0): locked {locked}, upstream {locked}: current" in capsys.readouterr().out


def test_check_upstream_reports_behind_with_both_commits(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, monkeypatch) == 0
    upstream = Path(vendor.UPSTREAM)
    locked = _git(upstream, "rev-parse", "HEAD")
    _git(upstream, "commit", "-q", "--allow-empty", "-m", "release work")
    _git(upstream, "tag", "-a", "v1.4.0", "-m", "new release")
    newer = _git(upstream, "rev-parse", "HEAD")
    capsys.readouterr()
    assert _check_upstream(monkeypatch) == 5
    assert f"(v1.4.0): locked {locked}, upstream {newer}: behind" in capsys.readouterr().out


def test_check_upstream_unreachable_is_not_current(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, monkeypatch) == 0
    monkeypatch.setattr(vendor, "UPSTREAM", str(tmp_path / "gone"))
    capsys.readouterr()
    assert _check_upstream(monkeypatch) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not checked: git ls-remote failed:" in captured.err


def test_check_upstream_without_release_tag_is_not_current(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, monkeypatch) == 0
    capsys.readouterr()
    assert _check_upstream(monkeypatch) == 1
    assert "not checked: upstream has no release tag" in capsys.readouterr().err
