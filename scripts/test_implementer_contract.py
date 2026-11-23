"""The implementer's contract gate: only text by people with write access is built."""

from __future__ import annotations

import json

import implementer_claim
import pytest
from test_implementer_briefs import brief
from test_implementer_claim import ISSUE_PATH, REPO, FakeGitHub, claim, http_error, run_cli
from test_implementer_intake_gates import assert_stopped_before_any_branch, blocker

EVENTS_PATH = f"{ISSUE_PATH}/events"


def contract_of(fake: FakeGitHub) -> str:
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.CLAIMED
    assert outcome.contract is not None
    return outcome.contract


def outsider_brief(text: str) -> dict:
    return brief(text, author_association="NONE")


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


def permission_path(login: str) -> str:
    return f"/repos/{REPO}/collaborators/{login}/permission"


def audit_finding(
    events: list[dict],
    *,
    author: dict | None = None,
    permissions: dict[str, str] | None = None,
) -> FakeGitHub:
    """An App-filed audit-finding issue; ``permissions`` maps a label adder to its role."""
    issue = {
        "body": "AUDIT FINDINGS",
        "author_association": "CONTRIBUTOR",
        "user": author or {"login": "claude[bot]", "type": "Bot"},
        "labels": [{"name": "audit-finding"}, {"name": "ready-for-agent"}],
    }
    roles = {"maintainer": "admin", **(permissions or {})}
    payloads = {permission_path(login): {"permission": role} for login, role in roles.items()}
    return FakeGitHub(canned_payloads={ISSUE_PATH: issue, EVENTS_PATH: events, **payloads})


def labeled(name: str, actor_type: str = "User", login: str = "maintainer") -> dict:
    actor = {"type": actor_type, "login": login}
    return {"event": "labeled", "label": {"name": name}, "actor": actor}


@pytest.mark.parametrize("role", ["admin", "write"])
def test_an_audit_finding_a_writer_released_is_the_contract(role):
    fake = audit_finding(
        [labeled("audit-finding", "Bot", "claude[bot]"), labeled("ready-for-agent", login="dev")],
        permissions={"dev": role},
    )
    assert "AUDIT FINDINGS" in contract_of(fake)


@pytest.mark.parametrize(
    "events",
    [
        [labeled("ready-for-agent", "Bot", "claude[bot]")],
        [labeled("ready-for-agent"), labeled("ready-for-agent", "Bot", "claude[bot]")],
        [labeled("audit-finding")],
        [],
    ],
)
def test_an_audit_finding_no_person_released_stops_the_run(events):
    fake = audit_finding(events)
    assert claim(fake).outcome == implementer_claim.NO_CONTRACT
    assert_stopped_before_any_branch(fake)


# Triage and the other read roles can add labels without write access.
@pytest.mark.parametrize("role", ["read", "none"])
def test_an_audit_finding_released_without_write_access_stops_the_run(role):
    fake = audit_finding(
        [labeled("ready-for-agent", login="triager")], permissions={"triager": role}
    )
    assert claim(fake).outcome == implementer_claim.NO_CONTRACT


def test_an_audit_finding_released_by_an_unknown_account_stops_the_run():
    fake = audit_finding([labeled("ready-for-agent", login="gone")])
    fake.errors[("GET", permission_path("gone"))] = http_error(404, permission_path("gone"))
    assert claim(fake).outcome == implementer_claim.NO_CONTRACT


@pytest.mark.parametrize(
    "author",
    [
        {"login": "someone[bot]", "type": "Bot"},
        {"login": "claude[bot]", "type": "User"},
        {"login": "mallory", "type": "User"},
    ],
)
def test_only_the_apps_own_issue_counts_as_an_audit_finding(author):
    fake = audit_finding([labeled("ready-for-agent")], author=author)
    assert claim(fake).outcome == implementer_claim.NO_CONTRACT
