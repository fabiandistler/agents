"""Fixture tests for validate_patch.py.

Run from the repo root with: python3 -m pytest skills/unattended-agent-job/scripts/
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("validate_patch.py")
sys.path.insert(0, str(SCRIPT.parent))

from validate_patch import glob_to_regex


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def make_repo(tmp_path):
    """A committed base checkout with a docs/ tree and a protected workflow."""
    base = tmp_path / "repo"
    (base / "docs").mkdir(parents=True)
    (base / ".github" / "workflows").mkdir(parents=True)
    (base / "docs" / "guide.md").write_text("one\ntwo\n")
    (base / ".github" / "workflows" / "job.yml").write_text("on: push\n")
    (base / "src.py").write_text("x = 1\n")
    git(base, "init", "-q")
    git(base, "config", "user.email", "test@example.com")
    git(base, "config", "user.name", "Test")
    git(base, "add", ".")
    git(base, "commit", "-qm", "base")
    return base


def make_patch(repo, tmp_path, edit):
    """Run `edit(repo)`, capture the staged diff, then reset to the base commit."""
    edit(repo)
    git(repo, "add", "-A")
    diff = git(repo, "diff", "--cached", "-M", "--binary")
    git(repo, "reset", "-q", "--hard")
    git(repo, "clean", "-qfd")
    patch = tmp_path / "patch.diff"
    patch.write_text(diff)
    return patch


def write_allowlist(tmp_path, *patterns):
    path = tmp_path / "allowlist.txt"
    path.write_text("# test allowlist\n" + "\n".join(patterns) + "\n")
    return path


def run(*args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, check=False
    )
    report = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None
    return proc.returncode, report, proc.stderr


def append_line(repo):
    with (repo / "docs" / "guide.md").open("a") as fh:
        fh.write("three\n")


def test_clean_patch_inside_allowlist_passes(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, append_line)
    code, report, _ = run(
        "--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path, "docs/**")
    )
    assert code == 0
    assert report["ok"] is True
    assert report["lines"] == 1
    assert report["violations"] == []


def test_validator_leaves_working_tree_untouched(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, append_line)
    run("--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path, "docs/**"))
    assert git(repo, "status", "--porcelain") == ""


def test_patch_that_does_not_apply_exits_3(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, append_line)
    (repo / "docs" / "guide.md").write_text("changed underneath\n")
    git(repo, "commit", "-qam", "drift")
    code, report, stderr = run(
        "--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path, "docs/**")
    )
    assert code == 3
    assert report["violations"][0]["kind"] == "not_applicable"
    assert stderr


def test_path_outside_allowlist_exits_4(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, lambda r: (r / "src.py").write_text("x = 2\n"))
    code, report, _ = run(
        "--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path, "docs/**")
    )
    assert code == 4
    assert report["violations"] == [
        {"kind": "outside_allowlist", "path": "src.py", "source": "patch"}
    ]


def test_untracked_file_in_checkout_counts_as_changed(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, append_line)
    (repo / "stray.sh").write_text("echo leaked\n")
    code, report, _ = run(
        "--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path, "docs/**")
    )
    assert code == 4
    assert report["untracked_paths"] == 1
    assert {"kind": "outside_allowlist", "path": "stray.sh", "source": "untracked"} in report[
        "violations"
    ]


def test_rename_checks_both_sides(tmp_path):
    repo = make_repo(tmp_path)

    def rename_out(r):
        (r / "docs" / "guide.md").rename(r / "guide.md")

    patch = make_patch(repo, tmp_path, rename_out)
    code, report, _ = run(
        "--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path, "docs/**")
    )
    assert code == 4
    paths = {v["path"] for v in report["violations"]}
    assert paths == {"guide.md"}


def test_over_budget_exits_5(tmp_path):
    repo = make_repo(tmp_path)

    def many_lines(r):
        (r / "docs" / "guide.md").write_text("".join(f"{i}\n" for i in range(50)))

    patch = make_patch(repo, tmp_path, many_lines)
    code, report, _ = run(
        "--repo",
        repo,
        "--patch",
        patch,
        "--allowlist",
        write_allowlist(tmp_path, "docs/**"),
        "--max-lines",
        10,
    )
    assert code == 5
    assert report["lines"] > 10


def test_protected_path_exits_6(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(
        repo,
        tmp_path,
        lambda r: (r / ".github" / "workflows" / "job.yml").write_text("on: schedule\n"),
    )
    code, report, _ = run(
        "--repo",
        repo,
        "--patch",
        patch,
        "--allowlist",
        write_allowlist(tmp_path, "docs/**", ".github/**"),
        "--protected",
        ".github/**",
    )
    assert code == 6
    assert report["violations"][0]["kind"] == "protected"


def test_lowest_failure_code_wins(tmp_path):
    repo = make_repo(tmp_path)

    def both(r):
        (r / "src.py").write_text("x = 2\n")
        (r / ".github" / "workflows" / "job.yml").write_text("on: schedule\n")

    patch = make_patch(repo, tmp_path, both)
    code, report, _ = run(
        "--repo",
        repo,
        "--patch",
        patch,
        "--allowlist",
        write_allowlist(tmp_path, ".github/**"),
        "--protected",
        ".github/**",
    )
    assert code == 4
    assert {v["kind"] for v in report["violations"]} == {"outside_allowlist", "protected"}


USAGE_CASES = [
    ([], "--repo is required"),
    (["--repo", ".", "--patch", "x.diff"], "--allowlist is required"),
    (["--bogus"], "unknown argument"),
]


def test_usage_errors_exit_2():
    for args, message in USAGE_CASES:
        code, report, stderr = run(*args)
        assert code == 2, args
        assert report is None
        assert message in stderr


def test_empty_allowlist_is_a_usage_error(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, append_line)
    code, _, stderr = run(
        "--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path)
    )
    assert code == 2
    assert "no pattern" in stderr


def test_help_is_short_and_lists_exit_codes():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=True
    )
    assert len(proc.stdout.splitlines()) <= 25
    assert "6 touches protected path" in proc.stdout


GLOB_CASES = [
    ("docs/**", "docs/a/b.md", True),
    ("docs/**", "docs", False),
    ("docs/**", "docsx/a.md", False),
    ("docs/*.md", "docs/a.md", True),
    ("docs/*.md", "docs/sub/a.md", False),
    ("**/README.md", "README.md", True),
    ("**/README.md", "a/b/README.md", True),
    ("skills/*/SKILL.md", "skills/x/SKILL.md", True),
    ("src.py", "lib/src.py", False),
    ("src.py", "src.py\n", False),
    ("docs/**", "docs/a.md\n", True),
]


def test_globs_are_anchored():
    for pattern, path, expected in GLOB_CASES:
        assert bool(glob_to_regex(pattern).fullmatch(path)) is expected, (pattern, path)


# Review findings on PR #547: each test below reproduced its defect first.


def test_patch_inside_repo_is_a_usage_error(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, append_line)
    inside = repo / "outputs" / "patch.diff"
    inside.parent.mkdir()
    inside.write_text(patch.read_text())
    code, report, stderr = run(
        "--repo", repo, "--patch", inside, "--allowlist", write_allowlist(tmp_path, "docs/**")
    )
    assert code == 2
    assert report is None
    assert "inside --repo" in stderr


def test_dirty_tracked_file_exits_7(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, append_line)
    (repo / "src.py").write_text("x = 2\n")
    code, report, _ = run(
        "--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path, "docs/**")
    )
    assert code == 7
    assert {"kind": "dirty_tree", "path": "src.py", "source": "worktree"} in report["violations"]


def test_trailing_newline_does_not_satisfy_a_pattern(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, append_line)
    (repo / "src.py\n").write_text("echo leaked\n")
    code, report, _ = run(
        "--repo",
        repo,
        "--patch",
        patch,
        "--allowlist",
        write_allowlist(tmp_path, "docs/**", "src.py"),
    )
    assert code == 4
    assert {"kind": "outside_allowlist", "path": "src.py\n", "source": "untracked"} in report[
        "violations"
    ]


def run_docs_allowlist(tmp_path, repo, patch, allow="docs/**"):
    code, report, _ = run(
        "--repo", repo, "--patch", patch, "--allowlist", write_allowlist(tmp_path, allow)
    )
    return code, {v["kind"] for v in report["violations"]}, report


def test_symlink_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, lambda r: (r / "docs" / "link.md").symlink_to("guide.md"))
    code, kinds, _ = run_docs_allowlist(tmp_path, repo, patch)
    assert code == 8
    assert kinds == {"symlink"}


def test_submodule_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    patch = tmp_path / "patch.diff"
    patch.write_text(
        "diff --git a/docs/sub b/docs/sub\n"
        "new file mode 160000\n"
        "index 0000000..1234567\n"
        "--- /dev/null\n"
        "+++ b/docs/sub\n"
        "@@ -0,0 +1 @@\n"
        "+Subproject commit 1234567890123456789012345678901234567890\n"
    )
    code, kinds, _ = run_docs_allowlist(tmp_path, repo, patch)
    assert code != 0
    assert "submodule" in kinds


def test_binary_patch_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, lambda r: (r / "docs" / "blob.bin").write_bytes(b"\0\1\2"))
    assert "GIT binary patch" in patch.read_text()
    code, kinds, _ = run_docs_allowlist(tmp_path, repo, patch)
    assert code == 8
    assert kinds == {"binary"}


def test_executable_bit_change_is_reported(tmp_path):
    repo = make_repo(tmp_path)
    patch = make_patch(repo, tmp_path, lambda r: (r / "docs" / "guide.md").chmod(0o755))
    code, _, report = run_docs_allowlist(tmp_path, repo, patch)
    assert code == 0
    assert report["mode_changes"] == [
        {"path": "docs/guide.md", "old_mode": "100644", "new_mode": "100755"}
    ]


def test_protected_matches_case_insensitively(tmp_path):
    repo = make_repo(tmp_path)

    def add_workflow(r):
        (r / ".GitHub" / "workflows").mkdir(parents=True)
        (r / ".GitHub" / "workflows" / "new.yml").write_text("on: push\n")

    patch = make_patch(repo, tmp_path, add_workflow)
    code, report, _ = run(
        "--repo",
        repo,
        "--patch",
        patch,
        "--allowlist",
        write_allowlist(tmp_path, ".GitHub/**"),
        "--protected",
        ".github/**",
    )
    assert code == 6
    assert report["violations"][0]["kind"] == "protected"


def new_file_patch(tmp_path, path):
    patch = tmp_path / "patch.diff"
    patch.write_text(
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1 @@\n"
        "+x\n"
    )
    return patch


UNSAFE_PATHS = ["../evil.txt", "docs/../../evil.txt", ".git/hooks/post-commit", "/tmp/evil.txt"]


def test_unsafe_paths_are_rejected(tmp_path):
    repo = make_repo(tmp_path)
    for path in UNSAFE_PATHS:
        patch = new_file_patch(tmp_path, path)
        code, kinds, report = run_docs_allowlist(tmp_path, repo, patch, allow="**")
        assert code != 0, path
        assert "unsafe_path" in kinds, (path, report)
