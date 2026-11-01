""".gitattributes marks every vendored file, and the check-file-tokens hook honours it.

The vendoring scripts own their file lists (vendor/repo-maintenance/lock.json,
.claude/vendor/mattpocock-skills/lock.json); .gitattributes repeats them so the
check-file-tokens prek hook skips vendored files instead of blocking a re-vendor.
The first test fails when a locked path is not marked linguist-vendored. The
second runs the real hook in a scratch repo with the real .gitattributes: a file
over the limit is skipped at a vendored or generated path and blocked elsewhere.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GITATTRIBUTES = REPO_ROOT / ".gitattributes"
HOOK = "scripts/hooks/check-file-tokens.sh"
REPO_MAINTENANCE_LOCK = REPO_ROOT / "vendor" / "repo-maintenance" / "lock.json"
MATTPOCOCK_LOCK = REPO_ROOT / ".claude" / "vendor" / "mattpocock-skills" / "lock.json"
# Over the hook's 5000-token limit (tokens = bytes / 4); plain filler, so no
# generator banner or lockfile name makes the hook skip it for another reason.
OVERSIZED = "x\n" * 15_000


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 -- fixed git argv, no shell.
        ["git", "-c", "user.email=t@e", "-c", "user.name=t", *args],  # noqa: S607 -- Git from PATH.
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _vendored_paths() -> list[str]:
    """Every tracked file the two vendoring scripts write."""
    locked = list(json.loads(REPO_MAINTENANCE_LOCK.read_text(encoding="utf-8"))["files"])
    skills = json.loads(MATTPOCOCK_LOCK.read_text(encoding="utf-8"))["skills"]
    pathspecs = ["vendor", ".claude/vendor", *(f".claude/skills/{name}" for name in skills)]
    tracked = _git(REPO_ROOT, "ls-files", "--", *pathspecs).splitlines()
    for name in skills:
        assert any(path.startswith(f".claude/skills/{name}/") for path in tracked), (
            f".claude/skills/{name}: in {MATTPOCOCK_LOCK.relative_to(REPO_ROOT)} but no file tracked"
        )
    return locked + tracked


def test_every_vendored_file_is_marked_linguist_vendored():
    paths = _vendored_paths()
    attributes = _git(REPO_ROOT, "check-attr", "-z", "linguist-vendored", "--", *paths)
    # -z output: path NUL attribute NUL value NUL, repeated.
    fields = attributes.split("\0")
    unmarked = [
        path for path, value in zip(fields[0::3], fields[2::3], strict=False) if value != "set"
    ]
    assert not unmarked, (
        "vendored but not marked linguist-vendored in .gitattributes "
        "(add a '<path> linguist-vendored' line, '<dir>/**' for a skill):\n  "
        + "\n  ".join(unmarked)
    )


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A git repo holding the real .gitattributes and the real hook."""
    _git(tmp_path, "init", "-q")
    shutil.copyfile(GITATTRIBUTES, tmp_path / ".gitattributes")
    (tmp_path / HOOK).parent.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / HOOK, tmp_path / HOOK)
    return tmp_path


def _run_hook_on_staged(repo: Path, path: str) -> subprocess.CompletedProcess:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(OVERSIZED, encoding="utf-8")
    _git(repo, "add", "--", path)
    return subprocess.run(  # noqa: S603 -- fixed argv, no shell.
        ["bash", HOOK, path],  # noqa: S607 -- bash from PATH, as prek runs it.
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "path",
    [
        "scripts/maintenance-scan.sh",
        "vendor/repo-maintenance/LICENSE",
        ".claude/skills/tdd/SKILL.md",
        "skills.json",
        ".claude/rules/agents-20-coding-standards.md",
    ],
)
def test_hook_skips_an_oversized_vendored_or_generated_file(scratch_repo, path):
    run = _run_hook_on_staged(scratch_repo, path)
    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize(
    "path",
    [
        "scripts/not-vendored.sh",
        ".claude/skills/hand-written/SKILL.md",
        ".claude/agents/skill-reviewer.md",
        ".claude/settings.json",
    ],
)
def test_hook_blocks_the_same_file_at_a_hand_written_path(scratch_repo, path):
    run = _run_hook_on_staged(scratch_repo, path)
    assert run.returncode == 1
    assert f"{path}: " in run.stderr
