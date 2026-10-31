"""Vendoring rules of scripts/vendor_repo_maintenance.py, against a local fake upstream.

The three files land in `scripts/` byte-identical to upstream, the scanner keeps
its executable bit, a re-run at the same ref changes nothing, and `--check`
reports a one-byte edit by file name without touching the network.
"""

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import vendor_repo_maintenance as vendor

ASSETS = {
    "maintenance-scan.sh": b"#!/usr/bin/env bash\necho scan\n",
    "maintenance-r-advisories.py": b"#!/usr/bin/env python3\nprint('advisories')\n",
    "maintenance-new-deps.py": b"#!/usr/bin/env python3\nprint('new deps')\n",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 -- test creates a local fixture repository with argv.
        ["git", "-c", "user.email=t@e", "-c", "user.name=t", *args],  # noqa: S607 -- Git from PATH.
        cwd=cwd,
        check=True,
    )


def _fake_upstream(tmp_path: Path, *, skip: str | None = None) -> Path:
    upstream = tmp_path / "upstream"
    assets = upstream / vendor.UPSTREAM_ASSETS
    assets.mkdir(parents=True)
    for name, content in ASSETS.items():
        if name != skip:
            (assets / name).write_bytes(content)
            (assets / name).chmod(0o755)
    (upstream / "LICENSE").write_text("MIT\n", encoding="utf-8")
    _git(upstream, "init", "-q", "-b", "main")
    _git(upstream, "add", "-A")
    _git(upstream, "commit", "-qm", "fake")
    return upstream


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A fake target repo with the module's paths pointed into it."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    vendor_dir = root / "vendor" / "repo-maintenance"
    monkeypatch.setattr(vendor, "REPO_ROOT", root)
    monkeypatch.setattr(vendor, "SCRIPTS_DIR", root / "scripts")
    monkeypatch.setattr(vendor, "VENDOR_DIR", vendor_dir)
    monkeypatch.setattr(vendor, "LOCK_PATH", vendor_dir / "lock.json")
    return root


def _main(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["vendor_repo_maintenance.py", *args])
    return vendor.main()


def _vendor(tmp_path, monkeypatch, *args: str, skip: str | None = None) -> int:
    monkeypatch.setattr(vendor, "UPSTREAM", str(_fake_upstream(tmp_path, skip=skip)))
    return _main(monkeypatch, *args)


def test_files_are_byte_identical_and_scanner_stays_executable(repo, tmp_path, monkeypatch):
    assert _vendor(tmp_path, monkeypatch) == 0
    for name, content in ASSETS.items():
        assert (repo / "scripts" / name).read_bytes() == content
    assert (repo / "scripts" / "maintenance-scan.sh").stat().st_mode & stat.S_IXUSR
    assert (repo / "vendor" / "repo-maintenance" / "LICENSE").read_text(encoding="utf-8") == "MIT\n"


def test_lock_pins_commit_and_hashes(repo, tmp_path, monkeypatch):
    assert _vendor(tmp_path, monkeypatch) == 0
    lock = json.loads((repo / "vendor" / "repo-maintenance" / "lock.json").read_text("utf-8"))
    assert lock["upstream"] == vendor.UPSTREAM
    assert len(lock["commit"]) == 40
    assert sorted(lock["files"]) == sorted(f"scripts/{name}" for name in ASSETS)


def test_rerun_at_same_ref_changes_nothing(repo, tmp_path, monkeypatch):
    assert _vendor(tmp_path, monkeypatch) == 0
    lock_path = repo / "vendor" / "repo-maintenance" / "lock.json"
    first = {p: p.read_bytes() for p in [lock_path, *(repo / "scripts").iterdir()]}
    commit = json.loads(lock_path.read_text("utf-8"))["commit"]
    assert _main(monkeypatch, "--ref", commit) == 0
    assert {p: p.read_bytes() for p in first} == first


def test_dry_run_writes_nothing(repo, tmp_path, monkeypatch):
    assert _vendor(tmp_path, monkeypatch, "--dry-run") == 0
    assert list((repo / "scripts").iterdir()) == []
    assert not (repo / "vendor").exists()


def test_asset_missing_upstream_fails_without_writing(repo, tmp_path, monkeypatch, capsys):
    assert _vendor(tmp_path, monkeypatch, skip="maintenance-new-deps.py") == 3
    assert "maintenance-new-deps.py" in capsys.readouterr().err
    assert list((repo / "scripts").iterdir()) == []
    assert not (repo / "vendor").exists()


@pytest.mark.parametrize("name", list(ASSETS))
def test_check_names_a_one_byte_edit(repo, tmp_path, monkeypatch, capsys, name):
    assert _vendor(tmp_path, monkeypatch) == 0
    # --check never clones: an unreachable upstream must not matter.
    monkeypatch.setattr(vendor, "UPSTREAM", str(tmp_path / "no-such-upstream"))
    assert _main(monkeypatch, "--check") == 0
    capsys.readouterr()

    target = repo / "scripts" / name
    target.write_bytes(target.read_bytes() + b"\n")
    assert _main(monkeypatch, "--check") == 4
    err = capsys.readouterr().err
    assert f"scripts/{name}" in err
    assert "vendor_repo_maintenance.py --ref" in err
    others = [other for other in ASSETS if other != name]
    assert not any(f"scripts/{other}" in err for other in others)


def test_check_without_lock_fails(repo, monkeypatch, capsys):
    assert _main(monkeypatch, "--check") == 4
    assert "no lock" in capsys.readouterr().err


def test_check_rejects_ref(repo, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _main(monkeypatch, "--check", "--ref", "main")
    assert exc.value.code == 2
