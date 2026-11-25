"""End-to-end tests for the line-citation gate.

Each test builds a fixture git checkout, runs the gate's entry point against it
with --root, and asserts on the exit code and the reported lines.
"""

import subprocess
from pathlib import Path

import check_line_cites
import pytest

CAPACITY_MODULE = '''"""Fixture module."""

MAX_WORKING_RUNS = 1


def is_job(listed_name: object, job: str) -> bool:
    return listed_name == job
'''


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    write(tmp_path, "scripts/agent_run_capacity.py", CAPACITY_MODULE)
    write(tmp_path, "scripts/implementer_claim.py")
    write(tmp_path, "scripts/pr_risk.py")
    write(tmp_path, ".github/workflows/factory-implementer.yml")
    write(tmp_path, "scripts/agent_run_settings.json", "{}\n")
    git(tmp_path, "init", "--quiet")
    return tmp_path


def git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 -- test drives a scratch repo with argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git resolves from PATH.
        check=True,
    )


def write(root: Path, rel: str, text: str = "x = 1\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def doc(root: Path, rel: str, text: str) -> None:
    write(root, rel, text)
    git(root, "add", "--all")


def run_gate(root: Path, capsys):
    code = check_line_cites.main(["--root", str(root)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize(
    "citation",
    ["implementer_claim.py:68", "scripts/pr_risk.py:30-34", "factory-implementer.yml:76-82"],
)
def test_line_citation_fails_and_names_the_line(checkout, capsys, citation):
    doc(checkout, "docs/factory/architecture.md", f"# Factory\n\nSee (`{citation}`).\n")

    code, _, err = run_gate(checkout, capsys)

    assert code == 1
    assert f"docs/factory/architecture.md:3: line citation `{citation}`" in err
    assert "cite the symbol instead" in err


def test_comma_separated_lines_in_docs_agents_fail(checkout, capsys):
    doc(checkout, "docs/agents/runbook.md", "Read `pr_risk.py:30,34` first.\n")

    code, _, err = run_gate(checkout, capsys)

    assert code == 1
    assert "docs/agents/runbook.md:1: line citation `pr_risk.py:30,34`" in err


def test_existing_symbol_passes_and_missing_symbol_fails(checkout, capsys):
    doc(checkout, "docs/factory/a.md", "Matches by `agent_run_capacity.is_job`.\n")

    code, out, err = run_gate(checkout, capsys)
    assert code == 0, err
    assert "line citations ok (1 docs)" in out

    doc(checkout, "docs/factory/a.md", "Matches by `agent_run_capacity.no_such_name`.\n")

    code, _, err = run_gate(checkout, capsys)
    assert code == 1
    assert (
        "docs/factory/a.md:1: `agent_run_capacity.no_such_name` names no def, class or "
        "top-level assignment in scripts/agent_run_capacity.py"
    ) in err


def test_top_level_assignment_counts_as_symbol(checkout, capsys):
    doc(checkout, "docs/factory/a.md", "Cap: `agent_run_capacity.MAX_WORKING_RUNS`.\n")

    code, _, err = run_gate(checkout, capsys)

    assert code == 0, err


def test_non_citations_pass(checkout, capsys):
    text = (
        "Runs at `12:30`, serves `http://localhost:8080/path`, reads "
        "`agent_run_settings.json` and `pr_risk.py`, and names `job.workflow_sha`.\n"
        "A missing file: `gone.py:12`.\n"
    )
    doc(checkout, "docs/factory/a.md", text)

    code, _, err = run_gate(checkout, capsys)

    assert code == 0, err


def test_citation_outside_a_code_span_is_left_alone(checkout, capsys):
    doc(checkout, "docs/factory/a.md", "Prose implementer_claim.py:68 is not a code span.\n")

    code, _, err = run_gate(checkout, capsys)

    assert code == 0, err


@pytest.mark.parametrize("rel", ["docs/adr/0001-x.md", "docs/wiki/page.md", "README.md"])
def test_docs_outside_the_checked_dirs_are_left_alone(checkout, capsys, rel):
    doc(checkout, rel, "See `implementer_claim.py:68`.\n")

    code, out, err = run_gate(checkout, capsys)

    assert code == 0, err
    assert "line citations ok (0 docs)" in out


def test_repository_docs_hold_no_line_citations(capsys):
    code, _, err = run_gate(check_line_cites.REPO_ROOT, capsys)

    assert code == 0, err


def test_unknown_argument_is_a_usage_error(capsys):
    assert check_line_cites.main(["--bogus"]) == 2
    assert "unknown argument" in capsys.readouterr().err
