"""Tests for the model-free pull request risk policy (scripts/pr_risk.py).

The public seam is ``classify_pull_request(context)`` plus the CLI. Fixtures
are plain context dictionaries in the shape produced by ``pr_github.py``; no
test performs a network call.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pr_risk
import pytest

SCRIPT = Path(__file__).resolve().parent / "pr_risk.py"


def file_entry(
    path: str,
    *,
    status: str = "modified",
    additions: int = 1,
    deletions: int = 0,
    binary: bool = False,
    renamed_from: str | None = None,
) -> dict:
    return {
        "path": path,
        "status": status,
        "additions": additions,
        "deletions": deletions,
        "binary": binary,
        "renamed_from": renamed_from,
    }


def make_context(files: list[dict] | None = None, **overrides: object) -> dict:
    context = {
        "schema_version": 1,
        "repo": "fabiandistler/agents",
        "number": 42,
        "title": "A change",
        "body": "",
        "author": "fabiandistler",
        "head_sha": "abc123",
        "head_ref": "fix/x",
        "base_ref": "main",
        "default_branch": "main",
        "draft": False,
        "fork": False,
        "mergeable": True,
        "labels": [],
        "files": [file_entry("docs/guide.md")] if files is None else files,
        "diff": "",
        "base_files": {},
        "comments": [],
        "checks": {},
        "reviews": {"changes_requested": False},
    }
    context.update(overrides)
    return context


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("additions", -5),
        ("additions", "3"),
        ("additions", None),
        ("additions", True),
        ("deletions", -1),
        ("deletions", 2.5),
        ("status", None),
        ("status", "moved"),
        ("binary", None),
        ("binary", "false"),
        ("renamed_from", 7),
    ],
)
def test_malformed_entry_field_is_high_and_names_the_field(field, value):
    entry = file_entry("docs/guide.md")
    entry[field] = value

    decision = pr_risk.classify_pull_request(make_context([entry]))

    assert decision["risk"] == "high"
    assert decision["auto_merge_eligible"] is False
    assert (
        f"unreadable-file-list: entry at index 0 has a malformed {field}" in (decision["reasons"])
    )
    assert "docs: docs/guide.md" in decision["reasons"]


@pytest.mark.parametrize("field", ["additions", "deletions", "status", "binary"])
def test_missing_entry_field_is_high(field):
    entry = file_entry("docs/guide.md")
    del entry[field]

    decision = pr_risk.classify_pull_request(make_context([entry]))

    assert decision["risk"] == "high"
    assert (
        f"unreadable-file-list: entry at index 0 has a malformed {field}" in (decision["reasons"])
    )


@pytest.mark.parametrize("status", ["copied", "changed", "unchanged"])
def test_other_github_statuses_are_readable(status):
    decision = pr_risk.classify_pull_request(
        make_context([file_entry("docs/guide.md", status=status)])
    )

    assert decision["risk"] == "low"


@pytest.mark.parametrize(
    ("field", "value"),
    [("fork", None), ("fork", "false"), ("draft", None), ("draft", 0)],
)
def test_malformed_fork_or_draft_flag_is_high(field, value):
    context = make_context([file_entry("docs/guide.md")])
    context[field] = value

    decision = pr_risk.classify_pull_request(context)

    assert decision["risk"] == "high"
    assert decision["auto_merge_eligible"] is False
    assert f"unreadable-metadata: {field} is not a boolean" in decision["reasons"]


def test_missing_fork_flag_is_high():
    context = make_context([file_entry("docs/guide.md")])
    del context["fork"]

    decision = pr_risk.classify_pull_request(context)

    assert decision["risk"] == "high"
    assert "unreadable-metadata: fork is not a boolean" in decision["reasons"]


def test_decision_echoes_identity_and_counts():
    decision = pr_risk.classify_pull_request(
        make_context(
            [
                file_entry("GLOSSARY.md", additions=3, deletions=1),
                file_entry("docs/guide.md", additions=5, deletions=2),
            ]
        )
    )

    assert decision["schema_version"] == 1
    assert decision["number"] == 42
    assert decision["head_sha"] == "abc123"
    assert decision["counts"] == {
        "files": 2,
        "additions": 8,
        "deletions": 3,
        "changed_lines": 11,
    }
    assert decision["reasons"] == ["docs: GLOSSARY.md", "docs: docs/guide.md"]


def docs_files(count: int, additions: int = 1) -> list[dict]:
    return [file_entry(f"docs/page-{index}.md", additions=additions) for index in range(count)]


@pytest.mark.parametrize(
    ("changed_lines", "risk", "threshold"),
    [
        (300, "low", None),
        (301, "medium", 300),
        (1000, "medium", 300),
        (1001, "high", 1000),
    ],
)
def test_changed_line_escalation_boundaries(changed_lines, risk, threshold):
    decision = pr_risk.classify_pull_request(
        make_context([file_entry("docs/long.md", additions=changed_lines)])
    )

    assert decision["risk"] == risk
    size_reasons = [reason for reason in decision["reasons"] if reason.startswith("size:")]
    if threshold is None:
        assert size_reasons == []
    else:
        assert size_reasons == [f"size: {changed_lines} changed lines > {threshold}"]


@pytest.mark.parametrize(
    ("file_count", "risk", "threshold"),
    [
        (20, "low", None),
        (21, "medium", 20),
        (50, "medium", 20),
        (51, "high", 50),
    ],
)
def test_file_count_escalation_boundaries(file_count, risk, threshold):
    decision = pr_risk.classify_pull_request(make_context(docs_files(file_count)))

    assert decision["risk"] == risk
    count_reasons = [reason for reason in decision["reasons"] if reason.startswith("count:")]
    if threshold is None:
        assert count_reasons == []
    else:
        assert count_reasons == [f"count: {file_count} files > {threshold}"]


def test_exactly_300_lines_across_exactly_20_files_stays_low():
    decision = pr_risk.classify_pull_request(make_context(docs_files(20, additions=15)))

    assert decision["counts"]["changed_lines"] == 300
    assert decision["counts"]["files"] == 20
    assert decision["risk"] == "low"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("docs/old.md", "deletion: docs/old.md"),
        ("skills/foo/SKILL.md", "critical-deletion: skills/foo/SKILL.md"),
        ("install.sh", "critical-deletion: install.sh"),
        (".github/workflows/ci.yml", "critical-deletion: .github/workflows/ci.yml"),
        ("scripts/pr_merge_guard.py", "critical-deletion: scripts/pr_merge_guard.py"),
        ("scripts/secret_read_guard.py", "critical-deletion: scripts/secret_read_guard.py"),
        (
            "plugins/merge-guard/hooks/hooks.json",
            "critical-deletion: plugins/merge-guard/hooks/hooks.json",
        ),
    ],
)
def test_deletions_raise_the_risk_and_name_the_path(path, expected):
    decision = pr_risk.classify_pull_request(
        make_context([file_entry(path, status="removed", deletions=4)])
    )

    assert expected in decision["reasons"]
    if expected.startswith("critical-deletion:"):
        assert decision["risk"] == "high"
    else:
        assert decision["risk"] == "medium"


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "docs/old.md",
        "scripts/test_catalogue.py",
    ],
)
def test_deleting_a_non_critical_file_is_at_least_medium(path):
    decision = pr_risk.classify_pull_request(
        make_context([file_entry(path, status="removed", deletions=1)])
    )

    assert decision["risk"] == "medium"
    assert decision["auto_merge_eligible"] is False
    assert f"deletion: {path}" in decision["reasons"]


def test_rename_is_at_least_medium_and_names_both_paths():
    decision = pr_risk.classify_pull_request(
        make_context(
            [
                file_entry(
                    "docs/new.md",
                    status="renamed",
                    renamed_from="docs/old.md",
                    additions=0,
                    deletions=0,
                )
            ]
        )
    )

    assert decision["risk"] == "medium"
    assert decision["auto_merge_eligible"] is False
    assert "rename: docs/old.md -> docs/new.md" in decision["reasons"]


def test_rename_without_previous_path_still_escalates():
    decision = pr_risk.classify_pull_request(
        make_context([file_entry("docs/new.md", status="renamed", additions=0, deletions=0)])
    )

    assert decision["risk"] == "medium"
    assert "rename: docs/new.md" in decision["reasons"]


def test_rename_of_a_high_risk_path_stays_high():
    decision = pr_risk.classify_pull_request(
        make_context(
            [
                file_entry(
                    "scripts/pr_risk.py",
                    status="renamed",
                    renamed_from="scripts/policy.py",
                    additions=0,
                    deletions=0,
                )
            ]
        )
    )

    assert decision["risk"] == "high"
    assert "rename: scripts/policy.py -> scripts/pr_risk.py" in decision["reasons"]


def test_binary_file_is_high_even_on_a_low_risk_path():
    decision = pr_risk.classify_pull_request(
        make_context([file_entry("docs/diagram.png", binary=True, additions=0, deletions=0)])
    )

    assert decision["risk"] == "high"
    assert decision["auto_merge_eligible"] is False
    assert "binary: docs/diagram.png" in decision["reasons"]


@pytest.mark.parametrize(
    "files",
    [
        [],
        None,
        "not-a-list",
        {"path": "docs/guide.md"},
        [{"status": "modified"}],
        [{"path": "", "status": "modified"}],
        [{"path": 7, "status": "modified"}],
        ["docs/guide.md"],
    ],
)
def test_empty_or_unreadable_file_list_is_high(files):
    context = make_context([])
    context["files"] = files

    decision = pr_risk.classify_pull_request(context)

    assert decision["risk"] == "high"
    assert decision["auto_merge_eligible"] is False
    assert decision["counts"]["files"] == 0


def test_missing_file_key_is_high_not_an_error():
    context = make_context([])
    del context["files"]

    decision = pr_risk.classify_pull_request(context)

    assert decision["risk"] == "high"
    assert any(reason.startswith("unreadable-file-list:") for reason in decision["reasons"])


def test_one_unreadable_entry_does_not_discard_readable_ones():
    context = make_context([])
    context["files"] = [file_entry("docs/guide.md"), {"status": "modified"}]

    decision = pr_risk.classify_pull_request(context)

    assert decision["risk"] == "high"
    assert "docs: docs/guide.md" in decision["reasons"]
    assert decision["counts"]["files"] == 1


def test_fork_is_high_and_never_auto_merge_eligible():
    decision = pr_risk.classify_pull_request(make_context([file_entry("docs/guide.md")], fork=True))

    assert decision["risk"] == "high"
    assert decision["auto_merge_eligible"] is False
    assert "fork: head repository differs from base" in decision["reasons"]


def test_draft_keeps_its_risk_but_is_not_auto_merge_eligible():
    decision = pr_risk.classify_pull_request(
        make_context([file_entry("docs/guide.md")], draft=True)
    )

    assert decision["risk"] == "low"
    assert decision["auto_merge_eligible"] is False
    assert "draft: auto-merge disabled" in decision["reasons"]


def test_low_risk_non_fork_non_draft_is_auto_merge_eligible():
    decision = pr_risk.classify_pull_request(make_context([file_entry("docs/guide.md")]))

    assert decision["auto_merge_eligible"] is True


@pytest.mark.parametrize(
    "path",
    [
        "scripts/pr_risk.py",
        "scripts/pr_github.py",
        "scripts/pr_review.py",
        "scripts/pr_review_prompt.md",
        "scripts/pr_publish.py",
        "scripts/pr_apply.py",
        "scripts/test_pr_risk.py",
        "scripts/test_pr_github.py",
        "scripts/test_pr_review.py",
        "scripts/test_pr_publish.py",
        "scripts/test_pr_apply.py",
        "scripts/test_pr_workflow.py",
        ".github/workflows/pr-review.yml",
    ],
)
def test_any_change_to_the_triage_automation_is_high_even_when_small(path):
    decision = pr_risk.classify_pull_request(
        make_context([file_entry(path, additions=1, deletions=0)])
    )

    assert decision["risk"] == "high"
    assert decision["auto_merge_eligible"] is False


def write_context(tmp_path: Path, context: dict) -> Path:
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context), encoding="utf-8")
    return path


def test_cli_context_prints_the_decision_json(tmp_path, capsys):
    path = write_context(tmp_path, make_context([file_entry("docs/guide.md")]))

    code = pr_risk.main(["--context", str(path)])

    assert code == 0
    decision = json.loads(capsys.readouterr().out)
    assert decision["risk"] == "low"
    assert decision["auto_merge_eligible"] is True


def test_cli_output_file_receives_the_decision(tmp_path, capsys):
    path = write_context(tmp_path, make_context([file_entry("GLOSSARY.md")]))
    output = tmp_path / "decision.json"

    code = pr_risk.main(["--context", str(path), "--output", str(output)])

    assert code == 0
    assert capsys.readouterr().out == ""
    assert json.loads(output.read_text(encoding="utf-8"))["risk"] == "low"


def test_cli_empty_file_list_is_high_and_exits_zero(tmp_path, capsys):
    path = write_context(tmp_path, make_context([]))

    code = pr_risk.main(["--context", str(path)])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["risk"] == "high"


def test_cli_unreadable_context_exits_three(tmp_path):
    assert pr_risk.main(["--context", str(tmp_path / "missing.json")]) == 3


@pytest.mark.parametrize("contents", ["{not json", "[]", '"text"', "null"])
def test_cli_malformed_context_exits_three(tmp_path, contents):
    path = tmp_path / "context.json"
    path.write_text(contents, encoding="utf-8")

    assert pr_risk.main(["--context", str(path)]) == 3


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--context"],
        ["--unknown"],
        ["--context", "x.json", "--live"],
        ["--live", "--pr", "42"],
        ["--live", "--repo", "o/r"],
        ["--live", "--pr", "zero", "--repo", "o/r"],
        ["--live", "--pr", "0", "--repo", "o/r"],
        ["--live", "--pr", "42", "--repo", "no-slash"],
        ["--context", "x.json", "--repo", "o/r"],
    ],
)
def test_cli_usage_errors_exit_two(argv):
    assert pr_risk.main(argv) == 2


def test_cli_live_fetches_the_context_and_passes_the_token(monkeypatch, capsys):
    captured = {}

    def fake_fetch(repo, number, token=None):
        captured.update(repo=repo, number=number, token=token)
        return make_context([file_entry("docs/guide.md")])

    monkeypatch.setattr(pr_risk.pr_github, "fetch_context", fake_fetch)
    monkeypatch.setenv("GITHUB_TOKEN", "not-a-real-token")

    code = pr_risk.main(["--live", "--pr", "42", "--repo", "fabiandistler/agents"])

    assert code == 0
    assert captured == {
        "repo": "fabiandistler/agents",
        "number": 42,
        "token": "not-a-real-token",
    }
    assert json.loads(capsys.readouterr().out)["risk"] == "low"


def test_cli_live_without_a_token_exits_five(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    code = pr_risk.main(["--live", "--pr", "42", "--repo", "fabiandistler/agents"])

    assert code == 5


def test_cli_live_fetch_failure_exits_four(monkeypatch):
    def fail(repo, number, token=None):
        raise pr_risk.pr_github.FetchError("boom")

    monkeypatch.setattr(pr_risk.pr_github, "fetch_context", fail)

    assert pr_risk.main(["--live", "--pr", "42", "--repo", "fabiandistler/agents"]) == 4


def test_cli_output_write_failure_exits_three(tmp_path):
    path = write_context(tmp_path, make_context([]))

    assert pr_risk.main(["--context", str(path), "--output", str(tmp_path)]) == 3


def test_cli_help_is_short_and_documents_exit_codes():
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and script path, no shell
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert len(result.stdout.splitlines()) < 25
    assert "usage:" in result.stdout
    assert "exit:" in result.stdout
    assert result.stderr == ""
