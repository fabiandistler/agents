"""gather_inputs.py --from-json: GitHub evidence imported without a remote or forge CLI.

Run from the repo root with: python3 -m pytest skills/review-decisions/scripts/
"""

import json
import subprocess
import sys

import pytest
from gather_inputs_testkit import SCRIPT, Forge, assert_fallback, make_repo, manifest


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


PR_BODY = "Adds the widget.\r\n\r\nCloses #12\n  "
ISSUE_BODY = "Build it exactly.\r\n\r\n* Keep café\n"
ISSUE_COMMENT = "Include the edge case.\r\n\n```\n  sample\n```  "


@pytest.fixture
def forge_json(repo):
    head = subprocess.check_output(  # noqa: S603 -- fixed Git argv, no shell.
        ["git", "-C", str(repo), "rev-parse", "HEAD"],  # noqa: S607
        text=True,
    ).strip()
    return {
        "pr": {
            "number": 7,
            "title": "Add widget",
            "body": PR_BODY,
            "base": {"ref": "main"},
            "head": {"sha": head},
        },
        "issues": [
            {
                "number": 12,
                "title": "Widget",
                "body": ISSUE_BODY,
                "comments": [{"body": ISSUE_COMMENT}],
            }
        ],
        "check_runs": [],
    }


def import_forge(tmp_path, repo, envelope):
    source = tmp_path / "forge.json"
    source.write_text(json.dumps(envelope), encoding="utf-8")
    out = tmp_path / "out"
    return Forge(tmp_path, clis=()).run(repo, out, "--from-json", str(source)), out


@pytest.mark.parametrize(
    ("runs", "state"),
    [
        ([{"name": "lint", "status": "completed", "conclusion": "success"}], "green"),
        (
            [
                {"name": "lint", "status": "completed", "conclusion": "failure"},
                {"name": "tests", "status": "queued", "conclusion": None},
            ],
            "failing",
        ),
        (
            [
                {"name": "lint", "status": "completed", "conclusion": "neutral"},
                {"name": "tests", "status": "in_progress", "conclusion": None},
            ],
            "pending",
        ),
        ([], "none"),
    ],
)
def test_json_import_preserves_evidence_and_supplies_skim_proof(
    tmp_path, repo, forge_json, runs, state
):
    forge_json["check_runs"] = runs
    completed, out = import_forge(tmp_path, repo, forge_json)

    assert completed.returncode == 0, completed.stderr
    found = manifest(out)
    assert json.loads(completed.stdout) == found
    assert found == {
        "forge": "github",
        "pr": {
            "number": 7,
            "target_branch": "main",
            "head_sha": forge_json["pr"]["head"]["sha"],
            "merge_status": "unknown",
        },
        "issues": ["12"],
        "files": {"pr": "pr.md", "issue": "issue.md", "ci": "ci.json"},
        "unchecked": [],
    }
    assert (out / "pr.md").read_bytes() == f"# Add widget\n\n{PR_BODY}\n".encode()
    expected_issue = f"# 12 Widget\n\n{ISSUE_BODY}\n\n## Comment\n\n{ISSUE_COMMENT}\n"
    assert (out / "issue.md").read_bytes() == expected_issue.encode()
    assert json.loads((out / "ci.json").read_bytes())["state"] == state
    assert skim_report(repo, out)["ci"]["proof"] == (state == "green")


def skim_report(repo, out):
    proof = subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [
            sys.executable,
            str(SCRIPT.with_name("skim_proof.py")),
            "--repo",
            str(repo),
            "--base",
            "HEAD",
            "--inputs",
            str(out / "inputs.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proof.stdout)


def test_json_import_keeps_stale_pr_head(tmp_path, repo, forge_json):
    forge_json["pr"]["head"]["sha"] = "deadbeef"
    forge_json["statuses"] = [{"context": "tests", "state": "success"}]
    completed, out = import_forge(tmp_path, repo, forge_json)

    assert completed.returncode == 0, completed.stderr
    assert manifest(out)["pr"]["head_sha"] == "deadbeef"
    assert json.loads((out / "ci.json").read_bytes())["state"] == "green"
    assert not skim_report(repo, out)["ci"]["proof"]


@pytest.mark.parametrize(
    ("section", "replacement", "unchecked"),
    [
        ("pr", {"head": []}, "pr"),
        ("pr", {"number": 7, "title": "Widget", "body": "private\ud800"}, "pr"),
        ("pr", {"merge_status": "dirty"}, "pr"),
        ("pr", {"merge_status": None}, "pr"),
        ("issues", [], "issue"),
        ("issues", [{"number": 12, "title": "Widget", "body": "Build it."}], "issue"),
        ("check_runs", [{"name": "lint", "status": "completed"}], "ci"),
        ("check_runs", None, "ci"),
    ],
)
def test_json_import_marks_only_malformed_or_missing_evidence_unchecked(
    tmp_path, repo, forge_json, section, replacement, unchecked
):
    if replacement is None:
        del forge_json[section]
    elif section == "pr" and "merge_status" in replacement:
        forge_json["pr"].update(replacement)
    else:
        forge_json[section] = replacement
    completed, out = import_forge(tmp_path, repo, forge_json)

    assert completed.returncode == 3, completed.stderr
    found = manifest(out)
    assert [item["input"] for item in found["unchecked"]] == [unchecked]
    assert set(found["files"]) == {"pr", "issue", "ci"} - {unchecked}
    assert "private" not in completed.stdout + completed.stderr


@pytest.mark.parametrize("content", ["{", "[]"])
def test_invalid_json_writes_unchecked_manifest(tmp_path, repo, content):
    source = tmp_path / "forge.json"
    source.write_text(content, encoding="utf-8")
    out = tmp_path / "out"

    completed = Forge(tmp_path, clis=()).run(repo, out, "--from-json", str(source))

    assert_fallback(completed, out, "cannot read --from-json as a JSON object")


@pytest.mark.parametrize("status", ["clean", "conflicts", "unknown"])
def test_json_import_records_a_supplied_merge_status(tmp_path, repo, forge_json, status):
    forge_json["pr"]["merge_status"] = status
    completed, out = import_forge(tmp_path, repo, forge_json)

    assert completed.returncode == 0, completed.stderr
    assert manifest(out)["pr"]["merge_status"] == status
