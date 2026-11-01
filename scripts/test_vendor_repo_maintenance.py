"""Vendoring rules of scripts/vendor_repo_maintenance.py, against a local fake upstream.

The three files land in `scripts/` byte-identical to upstream, the scanner keeps
its executable bit, a re-run at the same ref changes nothing, and `--check`
reports a one-byte edit, a flipped executable bit, a deleted file and a lock
whose file list differs from the vendored one, by file name and without touching
the network. A malformed lock exits 4 with the broken field, not a traceback.
"""

import hashlib
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import vendor_repo_maintenance as vendor

# Keyed by destination in the target repo; the fake upstream holds each at
# its vendor.VENDORED upstream path.
ASSETS = {
    "scripts/maintenance-scan.sh": b"#!/usr/bin/env bash\necho scan\n",
    "scripts/maintenance-r-advisories.py": b"#!/usr/bin/env python3\nprint('advisories')\n",
    "scripts/maintenance-new-deps.py": b"#!/usr/bin/env python3\nprint('new deps')\n",
}
# Upstream ships all three executable; this fake one is not, so the lock's
# "100644" mode is exercised as well as "100755".
NOT_EXECUTABLE = "scripts/maintenance-new-deps.py"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 -- test creates a local fixture repository with argv.
        ["git", "-c", "user.email=t@e", "-c", "user.name=t", *args],  # noqa: S607 -- Git from PATH.
        cwd=cwd,
        check=True,
    )


def _fake_upstream(tmp_path: Path, *, skip: str | None = None) -> Path:
    """A local upstream repo; `skip` names an asset or "LICENSE" to leave out."""
    upstream = tmp_path / "upstream"
    for destination, content in ASSETS.items():
        if destination != skip:
            source = upstream / vendor.VENDORED[destination]
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(content)
            source.chmod(0o644 if destination == NOT_EXECUTABLE else 0o755)
    upstream.mkdir(exist_ok=True)
    if skip != "LICENSE":
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
    monkeypatch.setattr(vendor, "VENDOR_DIR", vendor_dir)
    monkeypatch.setattr(vendor, "LOCK_PATH", vendor_dir / "lock.json")
    return root


def _main(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["vendor_repo_maintenance.py", *args])
    return vendor.main()


def _vendor(tmp_path, monkeypatch, *args: str, skip: str | None = None) -> int:
    monkeypatch.setattr(vendor, "UPSTREAM", str(_fake_upstream(tmp_path, skip=skip)))
    return _main(monkeypatch, *args)


def _lock_path(repo: Path) -> Path:
    return repo / "vendor" / "repo-maintenance" / "lock.json"


def _edit_lock(repo: Path, edit) -> None:
    lock = json.loads(_lock_path(repo).read_text("utf-8"))
    edit(lock)
    _lock_path(repo).write_text(json.dumps(lock), encoding="utf-8")


def test_files_are_byte_identical_and_scanner_stays_executable(repo, tmp_path, monkeypatch):
    assert _vendor(tmp_path, monkeypatch) == 0
    for destination, content in ASSETS.items():
        assert (repo / destination).read_bytes() == content
    assert (repo / "scripts" / "maintenance-scan.sh").stat().st_mode & stat.S_IXUSR
    assert (repo / "vendor" / "repo-maintenance" / "LICENSE").read_text(encoding="utf-8") == "MIT\n"


def test_lock_pins_commit_hashes_and_modes(repo, tmp_path, monkeypatch):
    assert _vendor(tmp_path, monkeypatch) == 0
    lock = json.loads(_lock_path(repo).read_text("utf-8"))
    assert lock["upstream"] == vendor.UPSTREAM
    assert len(lock["commit"]) == 40
    assert lock["files"] == {
        destination: {
            "sha256": hashlib.sha256(content).hexdigest(),
            "mode": "100644" if destination == NOT_EXECUTABLE else "100755",
        }
        for destination, content in ASSETS.items()
    }


def test_rerun_at_same_ref_changes_nothing(repo, tmp_path, monkeypatch):
    assert _vendor(tmp_path, monkeypatch) == 0
    lock_path = _lock_path(repo)
    paths = [lock_path, *(repo / destination for destination in ASSETS)]
    first = {p: (p.read_bytes(), p.stat().st_mode) for p in paths}
    commit = json.loads(lock_path.read_text("utf-8"))["commit"]
    assert _main(monkeypatch, "--ref", commit) == 0
    assert {p: (p.read_bytes(), p.stat().st_mode) for p in paths} == first


def test_dry_run_writes_nothing(repo, tmp_path, monkeypatch):
    assert _vendor(tmp_path, monkeypatch, "--dry-run") == 0
    assert list((repo / "scripts").iterdir()) == []
    assert not (repo / "vendor").exists()


@pytest.mark.parametrize(
    ("skip", "upstream_path"),
    [
        ("scripts/maintenance-new-deps.py", f"{vendor.UPSTREAM_ASSETS}/maintenance-new-deps.py"),
        ("LICENSE", "LICENSE"),
    ],
)
def test_file_missing_upstream_fails_without_writing(
    repo, tmp_path, monkeypatch, capsys, skip, upstream_path
):
    assert _vendor(tmp_path, monkeypatch, skip=skip) == 3
    assert upstream_path in capsys.readouterr().err
    assert list((repo / "scripts").iterdir()) == []
    assert not (repo / "vendor").exists()


@pytest.mark.parametrize("destination", list(ASSETS))
def test_check_names_a_one_byte_edit(repo, tmp_path, monkeypatch, capsys, destination):
    assert _vendor(tmp_path, monkeypatch) == 0
    # --check never clones: an unreachable upstream must not matter.
    monkeypatch.setattr(vendor, "UPSTREAM", str(tmp_path / "no-such-upstream"))
    assert _main(monkeypatch, "--check") == 0
    capsys.readouterr()

    target = repo / destination
    target.write_bytes(target.read_bytes() + b"\n")
    assert _main(monkeypatch, "--check") == 4
    err = capsys.readouterr().err
    assert destination in err
    assert "vendor_repo_maintenance.py --ref" in err
    others = [other for other in ASSETS if other != destination]
    assert not any(other in err for other in others)


@pytest.mark.parametrize("destination", list(ASSETS))
def test_check_names_a_flipped_executable_bit(repo, tmp_path, monkeypatch, capsys, destination):
    assert _vendor(tmp_path, monkeypatch) == 0
    capsys.readouterr()
    target = repo / destination
    target.chmod(target.stat().st_mode ^ 0o111)
    assert _main(monkeypatch, "--check") == 4
    err = capsys.readouterr().err
    assert f"{destination}: mode" in err
    others = [other for other in ASSETS if other != destination]
    assert not any(other in err for other in others)


def test_check_ignores_permission_bits_git_does_not_track(repo, tmp_path, monkeypatch):
    # Checkouts differ by umask (0644 vs 0664); git records only the owner's x bit.
    assert _vendor(tmp_path, monkeypatch) == 0
    (repo / "scripts" / "maintenance-scan.sh").chmod(0o775)
    (repo / NOT_EXECUTABLE).chmod(0o664)
    assert _main(monkeypatch, "--check") == 0


def test_check_names_a_deleted_file(repo, tmp_path, monkeypatch, capsys):
    assert _vendor(tmp_path, monkeypatch) == 0
    capsys.readouterr()
    (repo / "scripts" / "maintenance-r-advisories.py").unlink()
    assert _main(monkeypatch, "--check") == 4
    assert "scripts/maintenance-r-advisories.py: missing" in capsys.readouterr().err


def test_check_names_a_file_the_lock_lacks(repo, tmp_path, monkeypatch, capsys):
    assert _vendor(tmp_path, monkeypatch) == 0
    capsys.readouterr()
    _edit_lock(repo, lambda lock: lock["files"].pop("scripts/maintenance-r-advisories.py"))
    assert _main(monkeypatch, "--check") == 4
    assert "scripts/maintenance-r-advisories.py: not in" in capsys.readouterr().err


def test_check_names_a_lock_entry_that_is_not_vendored(repo, tmp_path, monkeypatch, capsys):
    assert _vendor(tmp_path, monkeypatch) == 0
    capsys.readouterr()
    # A copy of a well-formed entry, so only the file set is wrong.
    _edit_lock(
        repo,
        lambda lock: lock["files"].update(
            {"scripts/maintenance-extra.sh": lock["files"]["scripts/maintenance-scan.sh"]}
        ),
    )
    assert _main(monkeypatch, "--check") == 4
    err = capsys.readouterr().err
    assert "scripts/maintenance-extra.sh" in err
    assert not any(destination in err for destination in ASSETS)


SHA = "0" * 64
COMMIT = "1" * 40


@pytest.mark.parametrize(
    ("lock_text", "field"),
    [
        ("{}", '"commit"'),
        # A merge conflict committed without resolving it.
        ("<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> main\n", "not valid JSON"),
        ("[]", "JSON object"),
        (json.dumps({"commit": COMMIT, "files": []}), '"files"'),
        # The format before modes were locked: a bare sha256 per file.
        (
            json.dumps({"commit": COMMIT, "files": {"scripts/maintenance-scan.sh": SHA}}),
            'files["scripts/maintenance-scan.sh"]',
        ),
        (
            json.dumps(
                {"commit": COMMIT, "files": {"scripts/maintenance-scan.sh": {"sha256": SHA}}}
            ),
            'files["scripts/maintenance-scan.sh"]',
        ),
    ],
)
def test_check_names_the_broken_lock_field(repo, monkeypatch, capsys, lock_text, field):
    _lock_path(repo).parent.mkdir(parents=True)
    _lock_path(repo).write_text(lock_text, encoding="utf-8")
    assert _main(monkeypatch, "--check") == 4
    err = capsys.readouterr().err
    assert "vendor/repo-maintenance/lock.json" in err
    assert field in err


def test_check_without_lock_fails(repo, monkeypatch, capsys):
    assert _main(monkeypatch, "--check") == 4
    assert "no lock" in capsys.readouterr().err


def test_check_rejects_ref(repo, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _main(monkeypatch, "--check", "--ref", "main")
    assert exc.value.code == 2
