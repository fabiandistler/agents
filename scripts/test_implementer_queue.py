"""The implementer queue: which waiting issue gets the next dispatch, and when none does."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import cast

import implementer_claim
import implementer_queue
import pr_github_client
import pytest
from implementer_setup import DEFAULT_SETUP
from pr_github_client import GitHubClient
from pr_github_fake import release_pin
from test_implementer_claim import (
    QUEUE_WORKFLOW,
    REPO,
    RUN_ID,
    FakeGitHub,
    http_error,
    json_response,
    pull_request,
    working_job,
)

DISPATCHES = f"/repos/{REPO}/actions/workflows/implementer.yml/dispatches"
RUNS = f"/repos/{REPO}/actions/workflows/implementer.yml/runs"
REPO_URL = f"https://api.github.com/repos/{REPO}"
EARLIER = "2026-11-10T09:55:00Z"
WORKING_RUN = 4999


def ticket(body: str = "", association: str = "OWNER") -> dict:
    return {"body": body, "author_association": association, "state": "open"}


def closed_issue(state_reason: str = "completed") -> dict:
    return {
        "body": "",
        "author_association": "OWNER",
        "state": "closed",
        "state_reason": state_reason,
        "repository_url": REPO_URL,
    }


def run(issue: int, status: str = "completed", conclusion: str | None = "success") -> dict:
    return {
        "display_title": f"implementer: issue #{issue}",
        "status": status,
        "conclusion": conclusion,
    }


@dataclass
class QueueFake:
    """A routed fake for the queue's REST calls, over several issues.

    ``issues`` maps a number to its issue payload; ``labelled`` lists the
    numbers carrying `ready-for-agent` (open or not: the fake filters by state).
    ``working`` maps an in-progress run id to its jobs; ``runs`` is the run
    listing, newest first. ``branches`` names the issues whose branch exists.
    ``listed_total``, when set, is the ``total_count`` the working-run and job listings report.
    ``events`` maps a number to its issue events; ``collaborators`` maps a login
    to the base role the permission endpoint reports.
    """

    issues: dict[int, dict] = field(default_factory=dict)
    labelled: list[int] = field(default_factory=list)
    pull_requests_in_listing: list[int] = field(default_factory=list)
    pulls: list[dict] = field(default_factory=list)
    branches: set[int] = field(default_factory=set)
    runs: list[dict] = field(default_factory=list)
    working: dict[int, list[dict]] = field(default_factory=dict)
    errors: dict[tuple[str, str], Exception] = field(default_factory=dict)
    reads: list[str] = field(default_factory=list)
    writes: list[tuple[str, str, dict]] = field(default_factory=list)
    workflow_file: str = "implementer.yml"
    listed_total: int | None = None
    events: dict[int, list[dict]] = field(default_factory=dict)
    collaborators: dict[str, str] = field(default_factory=dict)
    comments: dict[int, list[dict]] = field(default_factory=dict)

    def get(
        self, path: str, params: dict | None = None, accept: str | None = None
    ) -> pr_github_client.Response:
        if ("GET", path) in self.errors:
            raise self.errors[("GET", path)]
        self.reads.append(path)
        params = params or {}
        later_page = params.get("page", 1) != 1
        if path.startswith(f"/repos/{REPO}/actions/"):
            return self._get_actions(path, params)
        if path == f"/repos/{REPO}/issues":
            return json_response([] if later_page else self._waiting_listing(params))
        if path == f"/repos/{REPO}/pulls":
            return json_response([] if later_page else self.pulls)
        if path == f"/repos/{REPO}":
            return json_response({"default_branch": "trunk"})
        routes = (
            (rf"/repos/{REPO}/git/ref/heads/agent/issue-(\d+)", self._get_branch),
            (rf"/repos/{REPO}/issues/(\d+)(/.*)?", self._get_issue),
            (rf"/repos/{REPO}/collaborators/([^/]+)/permission", self._get_permission),
        )
        for pattern, handler in routes:
            if (found := re.fullmatch(pattern, path)) is not None:
                return handler(found, later_page)
        raise AssertionError(f"unexpected GET {path}")

    def _get_branch(self, found: re.Match, later_page: bool) -> pr_github_client.Response:
        """The agent branch of an issue in ``branches``; 404 for any other."""
        if int(found[1]) not in self.branches:
            raise http_error(404, found[0])
        return json_response({"object": {"sha": "b" * 40}})

    def _get_permission(self, found: re.Match, later_page: bool) -> pr_github_client.Response:
        """A login's repository permission; 404 for a login the fake does not know."""
        if found[1] not in self.collaborators:
            raise http_error(404, found[0])
        return json_response({"permission": self.collaborators[found[1]]})

    def _waiting_listing(self, params: dict) -> list[dict[str, object]]:
        """The open issues labelled `ready-for-agent`, as the issue listing returns them."""
        assert params.get("state") == "open", "only open issues wait"
        assert params.get("labels") == "ready-for-agent"
        listed: list[dict[str, object]] = [
            {"number": number} for number in self.labelled if self.issues[number]["state"] == "open"
        ]
        return listed + [{"number": n, "pull_request": {}} for n in self.pull_requests_in_listing]

    def _get_actions(self, path: str, params: dict) -> pr_github_client.Response:
        """The implementer's run listings and a working run's jobs."""
        if path == f"/repos/{REPO}/actions/workflows/{self.workflow_file}/runs":
            if params.get("status") == "in_progress":
                listed = [{"id": run_id} for run_id in self.working]
                total = len(listed) if self.listed_total is None else self.listed_total
                return json_response({"total_count": total, "workflow_runs": listed})
            return json_response({"total_count": len(self.runs), "workflow_runs": self.runs})
        if (found := re.fullmatch(rf"/repos/{REPO}/actions/runs/(\d+)/jobs", path)) is not None:
            jobs = self.working[int(found[1])]
            total = len(jobs) if self.listed_total is None else self.listed_total
            return json_response({"total_count": total, "jobs": jobs})
        raise AssertionError(f"unexpected GET {path}")

    def _get_issue(self, found: re.Match, later_page: bool) -> pr_github_client.Response:
        """An issue, its comments, blockers or events; 404 for an issue the fake does not hold."""
        number, rest, path = int(found[1]), found[2], found[0]
        if rest == "/comments":
            return json_response([] if later_page else self.comments.get(number, []))
        if rest == "/dependencies/blocked_by":
            return json_response([])
        if rest == "/events":
            return json_response([] if later_page else self.events.get(number, []))
        if rest is None and number in self.issues:
            return json_response(self.issues[number])
        raise http_error(404, path)

    def post(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        self.writes.append(("POST", path, payload or {}))
        return pr_github_client.Response(status=204, body=b"")


def start(fake: QueueFake, dry_run: bool = False) -> implementer_queue.QueueOutcome:
    return implementer_queue.start_next(
        cast(GitHubClient, fake), REPO, DEFAULT_SETUP, dry_run=dry_run
    )


def waiting(*numbers: int) -> QueueFake:
    payloads = {number: ticket() for number in numbers}
    return QueueFake(issues=payloads, labelled=list(numbers))


def dispatched_issue(fake: QueueFake) -> int:
    assert len(fake.writes) == 1, "exactly one dispatch"
    method, path, payload = fake.writes[0]
    assert (method, path) == ("POST", DISPATCHES)
    assert payload["ref"] == "trunk", "the dispatch runs the default branch's workflow"
    assert set(payload) == {"ref", "inputs"}
    assert set(payload["inputs"]) == {"issue"}
    return int(payload["inputs"]["issue"])


# The pick.


def test_several_waiting_issues_dispatch_the_lowest_dispatchable_one_once():
    fake = waiting(30, 21, 25, 22, 40)
    fake.issues[20] = {**closed_issue(), "state": "closed"}
    fake.labelled.append(20)
    fake.pulls = [pull_request(number=7, body="Closes #21")]
    fake.issues[22] = ticket("Blocked by #3")
    fake.issues[3] = {**ticket(), "state": "open", "state_reason": None, "repository_url": REPO_URL}
    outcome = start(fake)
    assert outcome.outcome == implementer_queue.DISPATCHED
    assert outcome.issue == 25
    assert dispatched_issue(fake) == 25
    assert [(skip.issue, skip.reason) for skip in outcome.skipped] == [
        (21, "pull-request"),
        (22, "blocked"),
    ]


def test_the_dispatch_input_is_the_issue_number_as_text():
    fake = waiting(12)
    start(fake)
    assert fake.writes[0][2]["inputs"] == {"issue": "12"}


def test_a_pull_request_in_the_issue_listing_is_not_a_ticket():
    fake = waiting()
    fake.pull_requests_in_listing = [9]
    assert start(fake).outcome == implementer_queue.EMPTY
    assert fake.writes == []


@pytest.mark.parametrize(
    ("latest", "reason"),
    [
        (run(12, status="in_progress", conclusion=None), "run-active"),
        (run(12, status="queued", conclusion=None), "run-active"),
        (run(12, conclusion="failure"), "run-failed"),
        (run(12, conclusion="timed_out"), "run-failed"),
        (run(12, conclusion="cancelled"), "run-failed"),
    ],
    ids=["running", "queued", "failed", "timed-out", "cancelled"],
)
def test_an_issue_whose_latest_run_is_active_or_failed_is_skipped(latest, reason):
    fake = waiting(12, 13)
    fake.runs = [latest, run(12)]
    outcome = start(fake)
    assert dispatched_issue(fake) == 13
    assert [(skip.issue, skip.reason) for skip in outcome.skipped] == [(12, reason)]


@pytest.mark.parametrize("conclusion", ["success", "skipped"])
def test_an_issue_whose_latest_run_ended_normally_is_picked(conclusion):
    fake = waiting(12)
    fake.runs = [run(12, conclusion=conclusion), run(12, conclusion="failure")]
    start(fake)
    assert dispatched_issue(fake) == 12


def test_an_issue_with_a_branch_is_skipped():
    fake = waiting(12, 13)
    fake.branches = {12}
    outcome = start(fake)
    assert dispatched_issue(fake) == 13
    assert outcome.skipped == [implementer_queue.Skip(12, "branch")]


def test_an_issue_without_a_contract_is_skipped():
    fake = waiting(12, 13)
    fake.issues[12] = ticket(association="NONE")
    outcome = start(fake)
    assert dispatched_issue(fake) == 13
    assert outcome.skipped == [implementer_queue.Skip(12, "no-contract")]


def audit_finding() -> dict:
    """An open audit-finding issue the App filed."""
    return {
        **ticket("AUDIT FINDINGS", association="CONTRIBUTOR"),
        "user": {"login": "claude[bot]", "type": "Bot"},
        "labels": [{"name": "audit-finding"}, {"name": "ready-for-agent"}],
    }


@pytest.mark.parametrize(
    ("adder", "pinned_body", "picked"),
    [
        (("User", "maintainer"), "AUDIT FINDINGS", 12),
        (("Bot", "claude[bot]"), "AUDIT FINDINGS", 13),
        (("User", "triager"), "AUDIT FINDINGS", 13),
        (("User", "maintainer"), "THE TEXT THE PERSON RELEASED", 13),
    ],
    ids=["writer-release-picks", "bot-label-skips", "read-role-skips", "edited-after-pin-skips"],
)
def test_an_audit_finding_is_picked_only_once_a_writer_released_its_body(
    adder, pinned_body, picked
):
    fake = waiting(12, 13)
    fake.issues[12] = audit_finding()
    actor_type, login = adder
    release = {"type": actor_type, "login": login}
    fake.events[12] = [
        {
            "event": "labeled",
            "label": {"name": "ready-for-agent"},
            "actor": release,
            "created_at": "2026-11-23T10:00:00Z",
        }
    ]
    fake.comments[12] = [release_pin(pinned_body, at="2026-11-23T10:00:05Z")]
    fake.collaborators = {"maintainer": "write", "triager": "read"}
    outcome = start(fake)
    assert dispatched_issue(fake) == picked
    if picked == 13:
        assert outcome.skipped == [implementer_queue.Skip(12, "no-contract")]


@pytest.mark.parametrize(
    ("state_reason", "picked"),
    [("completed", 12), ("not_planned", None)],
    ids=["completed-picks", "not-planned-skips"],
)
def test_a_closed_blocker_frees_the_issue_only_when_completed(state_reason, picked):
    fake = waiting(12)
    fake.issues[12] = ticket("Blocked by #3")
    fake.issues[3] = closed_issue(state_reason)
    outcome = start(fake)
    assert outcome.issue == picked
    if picked is None:
        assert outcome.outcome == implementer_queue.EMPTY
        assert fake.writes == []
    else:
        assert dispatched_issue(fake) == picked


# When nothing is dispatched.


def test_nothing_is_dispatched_or_read_while_an_implementer_run_works():
    fake = waiting(12)
    fake.working = {WORKING_RUN: [working_job(EARLIER)]}
    outcome = start(fake)
    assert outcome.outcome == implementer_queue.BUSY
    assert fake.writes == []
    assert f"/repos/{REPO}/issues" not in fake.reads


def test_a_run_whose_job_was_skipped_or_has_ended_does_not_make_the_queue_busy():
    fake = waiting(12)
    fake.working = {
        WORKING_RUN: [
            {"name": "implement / implement", "status": "completed", "started_at": EARLIER}
        ]
    }
    start(fake)
    assert dispatched_issue(fake) == 12


@pytest.mark.parametrize(
    "working", [{}, {WORKING_RUN: [working_job(EARLIER)]}], ids=["idle", "busy"]
)
def test_a_working_run_listing_whose_total_count_exceeds_its_items_does_not_fail(working):
    # Issue #905: four queue runs failed on such a listing and dispatched nothing.
    fake = waiting(12)
    fake.working = working
    fake.listed_total = 200
    outcome = start(fake)
    if working:
        assert outcome.outcome == implementer_queue.BUSY
        assert fake.writes == []
    else:
        assert dispatched_issue(fake) == 12


def test_a_called_job_name_counts_as_working():
    fake = waiting(12)
    fake.working = {WORKING_RUN: [{**working_job(EARLIER), "name": "implement / implement"}]}
    assert start(fake).outcome == implementer_queue.BUSY


def test_nothing_is_dispatched_when_no_issue_waits():
    fake = waiting()
    outcome = start(fake)
    assert outcome == implementer_queue.QueueOutcome(implementer_queue.EMPTY)
    assert fake.writes == []


def test_dry_run_reports_the_pick_without_writing():
    fake = waiting(14, 12)
    outcome = start(fake, dry_run=True)
    assert (outcome.outcome, outcome.issue, outcome.dry_run) == ("dispatched", 12, True)
    assert fake.writes == []


# The loop the queue must not start.


def test_a_dispatched_run_that_stops_at_capacity_keeps_waiting_without_a_loop():
    # A run for issue 12 starts while run 4999 works: the claim stops it and
    # keeps the label, so the issue still waits.
    claim_fake = FakeGitHub(jobs={RUN_ID: [working_job()], WORKING_RUN: [working_job(EARLIER)]})
    client = cast(GitHubClient, claim_fake)
    stopped = implementer_claim.claim_branch(
        client, client, REPO, 12, RUN_ID, queue_workflow=QUEUE_WORKFLOW
    )
    assert stopped.outcome == implementer_claim.AT_CAPACITY
    assert [write[:2] for write in claim_fake.writes] == [
        ("POST", f"/repos/{REPO}/issues/12/comments")
    ], "the label stays: no DELETE"

    # Its end triggers the queue, but run 4999 still works: no dispatch.
    queue = waiting(12)
    queue.runs = [run(12)]
    queue.working = {WORKING_RUN: [working_job(EARLIER)]}
    assert start(queue).outcome == implementer_queue.BUSY
    assert queue.writes == []

    # Run 4999 ends: the queue dispatches issue 12, once.
    queue.working = {}
    start(queue)
    assert dispatched_issue(queue) == 12


# The command line.


def run_cli(monkeypatch, fake: QueueFake, *argv: str) -> int:
    monkeypatch.setenv("GH_TOKEN", "job-token")
    monkeypatch.setattr(implementer_queue, "GitHubClient", lambda token: fake)
    return implementer_queue.main(["--repo", REPO, *argv])


def test_cli_dry_run_prints_the_pick_and_writes_nothing(monkeypatch, capsys):
    fake = waiting(12, 13)
    fake.branches = {12}
    code = run_cli(monkeypatch, fake, "--dry-run")
    assert code == implementer_queue.EXIT_OK
    assert json.loads(capsys.readouterr().out) == {
        "outcome": "dispatched",
        "issue": 13,
        "dry_run": True,
        "skipped": [{"issue": 12, "reason": "branch"}],
    }
    assert fake.writes == []


def test_cli_dispatches_the_named_workflow_file(monkeypatch, capsys):
    fake = waiting(12)
    fake.workflow_file = "agent.yml"
    code = run_cli(monkeypatch, fake, "--workflow-file", "agent.yml")
    assert code == implementer_queue.EXIT_OK
    assert fake.writes[0][1] == f"/repos/{REPO}/actions/workflows/agent.yml/dispatches"
    assert json.loads(capsys.readouterr().out)["outcome"] == "dispatched"


def test_cli_ignores_the_workflow_ref_of_its_own_workflow(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", f"{REPO}/.github/workflows/implementer-queue.yml@x")
    fake = waiting(12)
    run_cli(monkeypatch, fake)
    assert fake.writes[0][1] == DISPATCHES


def test_cli_reports_an_api_error_as_failed(monkeypatch, capsys):
    fake = waiting(12)
    fake.errors[("GET", RUNS)] = http_error(403, RUNS)
    code = run_cli(monkeypatch, fake)
    printed = json.loads(capsys.readouterr().out)
    assert code == implementer_queue.EXIT_FAILED
    assert printed["outcome"] == "failed"
    assert printed["reason"].startswith("GitHub API returned 403")
    assert fake.writes == []


def test_cli_without_a_token_fails(monkeypatch, capsys):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    code = implementer_queue.main(["--repo", REPO])
    assert code == implementer_queue.EXIT_FAILED
    assert json.loads(capsys.readouterr().out)["reason"] == "GH_TOKEN is not set"


def test_cli_rejects_a_bad_branch_prefix_before_any_call(monkeypatch, capsys):
    fake = waiting(12)
    code = run_cli(monkeypatch, fake, "--branch-prefix", "agent/issue")
    assert code == implementer_queue.EXIT_FAILED
    assert fake.reads == []


def test_cli_keeps_issue_text_out_of_its_output(monkeypatch, capsys):
    private_text = "Salary of Jane Doe"
    fake = waiting(12)
    fake.issues[12] = ticket(f"## Blocked by\n\n{private_text}\n")
    run_cli(monkeypatch, fake)
    out = capsys.readouterr()
    assert private_text not in out.out + out.err
