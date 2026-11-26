"""Tests for skim_proof.py through its command line.

Run from the repo root with: uv run --with pytest pytest skills/review-decisions/scripts/
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("skim_proof.py")


def run(*args):
    return subprocess.run(  # noqa: S603 -- test invokes skim_proof.py with argv, no shell.
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def git(repo: Path, *args) -> str:
    proc = subprocess.run(  # noqa: S603 -- fixture Git commands use argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    for name, text in files.items():
        (repo / name).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "switch", "-q", "-c", "feature")
    return repo


def commit(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "change")


def classify(repo: Path, *extra: str) -> dict:
    proc = run("--repo", str(repo), "--base", "main", *extra)
    assert proc.returncode == 0, proc.stderr
    return {entry["path"]: entry for entry in json.loads(proc.stdout)["files"]}


BODY = "def total(items):\n    return sum(items)\n"


def test_a_pure_rename_is_skim_with_the_rename_as_proof(tmp_path):
    repo = make_repo(tmp_path, {"old.py": BODY})
    git(repo, "mv", "old.py", "new.py")
    commit(repo)

    entry = classify(repo)["new.py"]

    assert entry["skim"] is True
    assert entry["proof"] == "rename"
    assert entry["old_path"] == "old.py"
    assert entry["reason"]


def test_a_content_change_without_ci_is_for_the_reviewer_to_look_at(tmp_path):
    repo = make_repo(tmp_path, {"calc.py": BODY})
    (repo / "calc.py").write_text(BODY.replace("sum(items)", "sum(items) or 0"))
    commit(repo)

    entry = classify(repo)["calc.py"]

    assert entry["skim"] is False
    assert entry["proof"] is None


def test_trailing_whitespace_and_line_endings_only_are_formatting(tmp_path):
    repo = make_repo(tmp_path, {"calc.py": BODY})
    (repo / "calc.py").write_text("def total(items):   \r\n    return sum(items)\t\n")
    commit(repo)

    entry = classify(repo)["calc.py"]

    assert entry["skim"] is True
    assert entry["proof"] == "formatting"


def test_a_rename_with_only_trailing_whitespace_changed_is_formatting(tmp_path):
    long_body = "".join(f"line {n}\n" for n in range(20))
    repo = make_repo(tmp_path, {"old.txt": long_body})
    git(repo, "mv", "old.txt", "new.txt")
    (repo / "new.txt").write_text(long_body.replace("line 3\n", "line 3  \n"))
    commit(repo)

    entry = classify(repo)["new.txt"]

    assert entry["old_path"] == "old.txt"
    assert entry["proof"] == "formatting"


def test_an_indentation_change_is_not_formal(tmp_path):
    repo = make_repo(tmp_path, {"calc.py": BODY})
    (repo / "calc.py").write_text("def total(items):\nreturn sum(items)\n")
    commit(repo)

    assert classify(repo)["calc.py"]["skim"] is False


def test_spacing_inside_a_line_is_not_formal(tmp_path):
    repo = make_repo(tmp_path, {"msg.py": 'GREETING = "a b"\n'})
    (repo / "msg.py").write_text('GREETING = "a  b"\n')
    commit(repo)

    assert classify(repo)["msg.py"]["skim"] is False


def test_added_deleted_and_mode_changed_files_are_not_formal(tmp_path):
    repo = make_repo(tmp_path, {"gone.py": BODY, "tool.sh": "echo hi\n"})
    git(repo, "rm", "-q", "gone.py")
    (repo / "added.py").write_text("VERSION = 2\n")
    (repo / "tool.sh").chmod(0o755)
    commit(repo)

    files = classify(repo)

    assert {path: entry["skim"] for path, entry in files.items()} == {
        "added.py": False,
        "gone.py": False,
        "tool.sh": False,
    }


def write_inputs(scratch: Path, head_sha: str, ci_state: str | None) -> Path:
    scratch.mkdir(parents=True)
    files = {}
    unchecked = []
    if ci_state is None:
        unchecked.append({"input": "ci", "reason": "gh is not installed"})
    else:
        files["ci"] = "ci.json"
        (scratch / "ci.json").write_text(json.dumps({"state": ci_state, "checks": []}))
    manifest = {
        "forge": "github",
        "pr": {"number": 7, "target_branch": "main", "head_sha": head_sha},
        "issues": [],
        "files": files,
        "unchecked": unchecked,
    }
    (scratch / "inputs.json").write_text(json.dumps(manifest))
    return scratch / "inputs.json"


def changed_calc(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path, {"calc.py": BODY})
    (repo / "calc.py").write_text(BODY.replace("sum(items)", "sum(items) or 0"))
    commit(repo)
    return repo


def run_json(repo: Path, inputs: Path) -> dict:
    proc = run("--repo", str(repo), "--base", "main", "--inputs", str(inputs))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_green_ci_on_the_checked_out_commit_proves_a_content_change(tmp_path):
    repo = changed_calc(tmp_path)
    inputs = write_inputs(tmp_path / "scratch", git(repo, "rev-parse", "HEAD"), "green")

    report = run_json(repo, inputs)

    assert report["ci"]["proof"] is True
    assert report["files"][0]["skim"] is True
    assert report["files"][0]["proof"] == "ci-green"


def test_green_ci_for_another_commit_is_no_proof(tmp_path):
    repo = changed_calc(tmp_path)
    inputs = write_inputs(tmp_path / "scratch", "0" * 40, "green")

    report = run_json(repo, inputs)

    assert report["ci"]["proof"] is False
    assert "commit" in report["ci"]["reason"]
    assert report["files"][0]["skim"] is False


def test_failing_pending_or_empty_ci_is_no_proof(tmp_path):
    repo = changed_calc(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    for state in ("failing", "pending", "none"):
        report = run_json(repo, write_inputs(tmp_path / state, head, state))

        assert report["ci"]["proof"] is False, state
        assert report["files"][0]["skim"] is False, state


def test_without_a_ci_status_only_formal_proofs_apply(tmp_path):
    repo = make_repo(tmp_path, {"old.py": BODY, "calc.py": BODY})
    git(repo, "mv", "old.py", "new.py")
    (repo / "calc.py").write_text("VERSION = 2\n")
    commit(repo)
    inputs = write_inputs(tmp_path / "scratch", git(repo, "rev-parse", "HEAD"), None)

    report = run_json(repo, inputs)
    files = {entry["path"]: entry for entry in report["files"]}

    assert report["ci"]["proof"] is False
    assert report["ci"]["reason"].startswith("no CI status")
    assert files["new.py"]["proof"] == "rename"
    assert files["calc.py"]["skim"] is False


def test_no_inputs_means_no_ci_status(tmp_path):
    repo = changed_calc(tmp_path)

    proc = run("--repo", str(repo), "--base", "main")

    assert json.loads(proc.stdout)["ci"] == {
        "proof": False,
        "reason": "no CI status: only renames and formatting can be skimmed",
    }


def test_a_formal_proof_wins_over_green_ci(tmp_path):
    repo = make_repo(tmp_path, {"old.py": BODY})
    git(repo, "mv", "old.py", "new.py")
    commit(repo)
    inputs = write_inputs(tmp_path / "scratch", git(repo, "rev-parse", "HEAD"), "green")

    assert run_json(repo, inputs)["files"][0]["proof"] == "rename"


def test_a_malformed_ci_file_exits_3(tmp_path):
    repo = changed_calc(tmp_path)
    inputs = write_inputs(tmp_path / "scratch", git(repo, "rev-parse", "HEAD"), "green")
    (inputs.parent / "ci.json").write_text("{not json")

    proc = run("--repo", str(repo), "--base", "main", "--inputs", str(inputs))

    assert proc.returncode == 3
    assert proc.stdout == ""


def test_an_unknown_base_exits_2(tmp_path):
    repo = changed_calc(tmp_path)

    proc = run("--repo", str(repo), "--base", "no-such-ref")

    assert proc.returncode == 2


def test_a_directory_outside_git_exits_2(tmp_path):
    proc = run("--repo", str(tmp_path), "--base", "main")

    assert proc.returncode == 2
