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
        subprocess.run(
            ["git", "-c", "user.email=t@e", "-c", "user.name=t", *args], cwd=upstream, check=True
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
