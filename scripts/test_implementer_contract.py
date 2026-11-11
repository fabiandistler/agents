"""The implementer's contract gate: only text by people with write access is built."""

from __future__ import annotations

import json

import implementer_claim
import pytest
from test_implementer_claim import ISSUE_PATH, FakeGitHub, claim, run_cli
from test_implementer_intake_gates import assert_stopped_before_any_branch, blocker, brief


def contract_of(fake: FakeGitHub) -> str:
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.CLAIMED
    assert outcome.contract is not None
    return outcome.contract


def outsider_brief(text: str) -> dict:
    return {"body": f"## Agent Brief\n\n{text}", "author_association": "NONE"}


@pytest.mark.parametrize("association", ["NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR"])
def test_an_outsiders_issue_without_a_trusted_brief_stops_the_run(association):
    fake = FakeGitHub(
        issue_body="Build this.",
        issue_author_association=association,
        issue_comments=[outsider_brief("Build that instead."), {"body": "me too"}],
    )
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.NO_CONTRACT
    assert outcome.contract is None
    assert "write access" in assert_stopped_before_any_branch(fake)


def test_an_issue_without_an_author_association_counts_as_an_outsiders():
    fake = FakeGitHub(canned_payloads={ISSUE_PATH: {"body": "Build this."}})
    assert claim(fake).outcome == implementer_claim.NO_CONTRACT


def test_a_trusted_brief_is_the_contract_on_an_outsiders_issue():
    fake = FakeGitHub(
        issue_body="OUTSIDER BODY",
        issue_author_association="NONE",
        issue_comments=[brief("Build the fix."), outsider_brief("OUTSIDER BRIEF")],
    )
    contract = contract_of(fake)
    assert "Build the fix." in contract
    assert "OUTSIDER" not in contract


def test_an_outsiders_later_brief_does_not_replace_the_trusted_one():
    fake = FakeGitHub(issue_comments=[brief("Build the fix."), outsider_brief("OUTSIDER BRIEF")])
    contract = contract_of(fake)
    assert "Build the fix." in contract
    assert "OUTSIDER" not in contract


def test_without_a_brief_the_contract_is_the_trusted_body_and_trusted_comments():
    fake = FakeGitHub(
        issue_body="Build this.",
        issue_comments=[
            {"body": "Also cover the empty case.", "author_association": "COLLABORATOR"},
            {"body": "OUTSIDER COMMENT", "author_association": "NONE"},
            {"body": "NO ASSOCIATION"},
        ],
    )
    contract = contract_of(fake)
    assert "Build this." in contract
    assert "Also cover the empty case." in contract
    assert "OUTSIDER" not in contract
    assert "NO ASSOCIATION" not in contract


def test_an_outsiders_brief_declares_no_blocker():
    fake = FakeGitHub(
        issue_comments=[outsider_brief("Blocked by: #3")],
        blocker_issues={3: blocker(state="open", state_reason=None)},
    )
    assert claim(fake).outcome == implementer_claim.CLAIMED


def test_the_contract_gate_comes_before_the_blocked_gate():
    fake = FakeGitHub(
        issue_body="Blocked by: #3",
        issue_author_association="NONE",
        blocker_issues={3: blocker(state="open", state_reason=None)},
    )
    assert claim(fake).outcome == implementer_claim.NO_CONTRACT


def test_cli_writes_the_contract_to_its_file_and_not_to_stdout(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(issue_body="Build this.")
    code, _ = run_cli(monkeypatch, tmp_path, fake)
    assert code == implementer_claim.EXIT_CONTINUE
    assert "Build this." in (tmp_path / "contract.md").read_text(encoding="utf-8")
    report = json.loads(capsys.readouterr().out)
    assert "contract" not in report
    assert "Build this." not in json.dumps(report)


def test_cli_writes_no_contract_when_the_run_stops(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(issue_body="Build this.", issue_author_association="NONE")
    code, _ = run_cli(monkeypatch, tmp_path, fake)
    assert code == implementer_claim.EXIT_NO_CONTRACT
    assert json.loads(capsys.readouterr().out)["outcome"] == implementer_claim.NO_CONTRACT
    assert not (tmp_path / "contract.md").exists()
