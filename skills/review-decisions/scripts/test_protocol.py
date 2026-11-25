"""Tests for protocol.py through its command line.

Run from the repo root with: uv run --with pytest pytest skills/review-decisions/scripts/
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("protocol.py")


def run(*args, env=None):
    return subprocess.run(  # noqa: S603 -- test invokes protocol.py with argv, no shell.
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False
    )


def git(*args) -> str:
    proc = subprocess.run(  # noqa: S603 -- fixture Git commands use argv; no shell.
        ["git", *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def git_repo(path: Path) -> Path:
    path.mkdir()
    git("init", "-q", "-b", "feature/x", str(path))
    return path


def state_env(tmp_path: Path) -> dict:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
    }


def test_path_lies_outside_the_repo_and_leaves_the_working_tree_clean(tmp_path):
    repo = git_repo(tmp_path / "demo")

    proc = run("path", "--repo", str(repo), env=state_env(tmp_path))

    assert proc.returncode == 0, proc.stderr
    printed = Path(proc.stdout.strip())
    assert printed.is_absolute()
    assert printed.parent == tmp_path / "state" / "review-decisions" / "demo"
    assert printed.name.startswith("feature-x-") and printed.suffix == ".md"
    assert printed.parent.is_dir()
    assert git("-C", str(repo), "status", "--porcelain", "--ignored") == ""


def test_path_refuses_a_state_directory_inside_the_repo(tmp_path):
    repo = git_repo(tmp_path / "demo")
    env = state_env(tmp_path)
    env["XDG_STATE_HOME"] = str(repo / ".state")

    proc = run("path", "--repo", str(repo), env=env)

    assert proc.returncode == 4
    assert not (repo / ".state").exists()


def test_path_rejects_a_directory_that_is_not_a_repo(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()

    proc = run("path", "--repo", str(plain), env=state_env(tmp_path))

    assert proc.returncode == 2


CARD = """\
## Card {n} of 3

- Location: `src/app.py:{n}`
- Criterion: public surface
{answer}
"""


def protocol(tmp_path: Path, answers: list[str], closing: bool = False) -> Path:
    cards = "\n".join(CARD.format(n=i + 1, answer=a) for i, a in enumerate(answers))
    text = "# Review decisions protocol\n\n" + cards
    if closing:
        text += "\nReview decisions settled, no defect review.\n"
    path = tmp_path / "p.md"
    path.write_text(text)
    return path


def test_resume_starts_at_the_first_card_without_an_answer(tmp_path):
    path = protocol(tmp_path, ["- Answer: ok", "- Answer: later", "- Answer:"])

    proc = run("resume", str(path))

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"cards": 3, "next": 3, "later": [2], "closed": False}


def test_resume_counts_a_card_with_only_an_open_question_as_undecided(tmp_path):
    path = protocol(tmp_path, ["- Answer: change", "- Question: why not a flag?", "- Answer: ok"])

    proc = run("resume", str(path))

    assert json.loads(proc.stdout)["next"] == 2


def test_resume_reports_a_closed_protocol(tmp_path):
    path = protocol(tmp_path, ["- Answer: ok", "- Answer: change", "- Answer: ok"], closing=True)

    proc = run("resume", str(path))

    assert json.loads(proc.stdout) == {"cards": 3, "next": None, "later": [], "closed": True}


def test_resume_rejects_an_unknown_answer(tmp_path):
    path = protocol(tmp_path, ["- Answer: ok", "- Answer: maybe", "- Answer:"])

    proc = run("resume", str(path))

    assert proc.returncode == 3
    assert "card 2" in proc.stderr


def test_resume_rejects_a_missing_protocol(tmp_path):
    proc = run("resume", str(tmp_path / "missing.md"))

    assert proc.returncode == 2


ANSWERED = """\
# Review decisions protocol

A defect review was not run.

## Card 1 of 3

- Location: `src/config.py:12`
- Answer: change
- Draft comment: `src/config.py:12`: keep `timeout` in seconds; the new
  `timeout_ms` key breaks existing config files.

## Card 2 of 3

- Location: `src/app.py:40`
- Answer: ok

## Card 3 of 3

- Location: `tests/test_app.py:8`
- Question: why was this test removed?
- Reply: the diff does not say.
- Answer: change
- Draft comment: `tests/test_app.py:8`: restore the deleted retry test.

Review decisions settled, no defect review.
"""


def test_comment_combines_the_change_drafts_in_card_order(tmp_path):
    path = tmp_path / "p.md"
    path.write_text(ANSWERED)

    proc = run("comment", str(path))

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == (
        "1. `src/config.py:12`: keep `timeout` in seconds; the new\n"
        "   `timeout_ms` key breaks existing config files.\n"
        "2. `tests/test_app.py:8`: restore the deleted retry test.\n"
        "\n"
        "This comment covers review decisions only; no defect review was done.\n"
    )


def test_comment_rejects_a_change_without_a_draft(tmp_path):
    path = protocol(tmp_path, ["- Answer: ok", "- Answer: change", "- Answer: ok"])

    proc = run("comment", str(path))

    assert proc.returncode == 3
    assert "card 2" in proc.stderr
    assert proc.stdout == ""


def test_comment_reports_when_no_card_asks_for_a_change(tmp_path):
    path = protocol(tmp_path, ["- Answer: ok", "- Answer: later", "- Answer: ok"])

    proc = run("comment", str(path))

    assert proc.returncode == 5
    assert proc.stdout == ""


def test_comment_leaves_out_a_draft_whose_answer_changed_to_ok(tmp_path):
    path = protocol(
        tmp_path,
        [
            "- Answer: change\n- Draft comment: `a.py:1`: rename the flag.",
            "- Draft comment: `src/app.py:2`: drop the new key.\n- Answer: ok",
            "- Answer: ok",
        ],
    )

    proc = run("comment", str(path))

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines()[0] == "1. `a.py:1`: rename the flag."
    assert "drop the new key" not in proc.stdout
