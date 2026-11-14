"""Every outcome of the implementer's branch claim, against a routed fake API."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import agent_run_report
import implementer_claim
import pr_github_client
import pytest
from pr_github_client import GitHubClient

REPO = "fabiandistler/agents"
ISSUE = 12
BRANCH = "agent/issue-12"
MAIN_SHA = "a" * 40
OLD_SHA = "b" * 40
AHEAD_SHA = "c" * 40

PULLS = f"/repos/{REPO}/pulls"
MAIN_REF = f"/repos/{REPO}/git/ref/heads/main"
BRANCH_REF = f"/repos/{REPO}/git/ref/heads/{BRANCH}"
CREATE_REF = f"/repos/{REPO}/git/refs"
UPDATE_REF = f"/repos/{REPO}/git/refs/heads/{BRANCH}"
COMMENTS = f"/repos/{REPO}/issues/{ISSUE}/comments"
LABELS = f"/repos/{REPO}/issues/{ISSUE}/labels"
REMOVE_LABEL = f"{LABELS}/ready-for-agent"
ISSUE_PATH = f"/repos/{REPO}/issues/{ISSUE}"
DEPENDENCIES = f"{ISSUE_PATH}/dependencies/blocked_by"
RUNS = f"/repos/{REPO}/actions/workflows/implementer.yml/runs"
RUN_ID = 5000
MAIN = "refs/heads/main"
JOB_START = "2026-11-10T10:00:00Z"


def working_job(started_at: str = JOB_START, status: str = "in_progress") -> dict:
    return {"name": "implement", "status": status, "started_at": started_at}


def http_error(status: int, path: str) -> pr_github_client.FetchError:
    return pr_github_client.FetchError(f"GitHub API returned {status} for {path}", status=status)


def json_response(payload: object) -> pr_github_client.Response:
    return pr_github_client.Response(status=200, body=json.dumps(payload).encode("utf-8"))


def pull_request(
    number: int = 7,
    state: str = "open",
    merged_at: str | None = None,
    body: str | None = "Unrelated work",
    head_label: str = "fabiandistler:fix/other",
) -> dict:
    return {
        "number": number,
        "state": state,
        "merged_at": merged_at,
        "body": body,
        "head": {"label": head_label},
    }


@dataclass
class FakeGitHub:
    """A routed fake for the claim's REST calls.

    ``errors`` maps (method, path) to an error, ``canned_payloads`` a GET path to its answer.
    ``jobs`` maps a run id to its jobs; by default only this run works.
    ``branch`` and ``workflow_file`` are the names the routes expect.
    """

    pulls: list[dict] = field(default_factory=list)
    branch_sha: str | None = None
    ahead_by: int = 0
    issue_body: str | None = ""
    issue_author_association: str = "OWNER"
    issue_comments: list[dict] = field(default_factory=list)
    native_blockers: list[dict] = field(default_factory=list)
    blocker_issues: dict[int, dict] = field(default_factory=dict)
    jobs: dict[int, list[dict]] = field(default_factory=lambda: {RUN_ID: [working_job()]})
    errors: dict[tuple[str, str], Exception] = field(default_factory=dict)
    canned_payloads: dict[str, object] = field(default_factory=dict)
    writes: list[tuple[str, str, dict]] = field(default_factory=list)
    compared: list[str] = field(default_factory=list)
    branch: str = BRANCH
    workflow_file: str = "implementer.yml"

    def _fail_if_routed(self, method: str, path: str) -> None:
        if (method, path) in self.errors:
            raise self.errors[(method, path)]

    def get(
        self, path: str, params: dict | None = None, accept: str | None = None
    ) -> pr_github_client.Response:
        self._fail_if_routed("GET", path)
        if path in self.canned_payloads:
            first_page = (params or {}).get("page", 1) == 1
            return json_response(self.canned_payloads[path] if first_page else [])
        if path == PULLS:
            assert (params or {}).get("state") == "all", "merged pull requests must be listed"
            return json_response(self.pulls if (params or {}).get("page") == 1 else [])
        if path == MAIN_REF:
            return json_response({"object": {"sha": MAIN_SHA}})
        if path == f"/repos/{REPO}/git/ref/heads/{self.branch}":
            if self.branch_sha is None:
                raise http_error(404, path)
            return json_response({"object": {"sha": self.branch_sha}})
        if path.startswith(f"/repos/{REPO}/compare/"):
            self.compared.append(path)
            return json_response({"ahead_by": self.ahead_by})
        return self._get_intake(path, params or {})

    def _get_intake(self, path: str, params: dict) -> pr_github_client.Response:
        """The routes the intake gates read."""
        first_page = params.get("page", 1) == 1
        if path == ISSUE_PATH:
            return json_response(
                {"body": self.issue_body, "author_association": self.issue_author_association}
            )
        if path == COMMENTS:
            return json_response(self.issue_comments if first_page else [])
        if path == DEPENDENCIES:
            return json_response(self.native_blockers if first_page else [])
        if path == f"/repos/{REPO}/actions/workflows/{self.workflow_file}/runs":
            assert params.get("status") == "in_progress", "only working runs may be counted"
            runs = [{"id": run_id} for run_id in self.jobs]
            return json_response({"total_count": len(runs), "workflow_runs": runs})
        if (match := re.fullmatch(rf"/repos/{REPO}/actions/runs/(\d+)/jobs", path)) is not None:
            jobs = self.jobs[int(match[1])]
            return json_response({"total_count": len(jobs), "jobs": jobs})
        if (match := re.fullmatch(rf"/repos/{REPO}/issues/(\d+)", path)) is not None:
            number = int(match[1])
            if number not in self.blocker_issues:
                raise http_error(404, path)
            return json_response(self.blocker_issues[number])
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        self._fail_if_routed("POST", path)
        if path == CREATE_REF and self.branch_sha is not None:
            raise http_error(422, path)
        self.writes.append(("POST", path, payload or {}))
        return json_response({})

    def patch(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        self._fail_if_routed("PATCH", path)
        self.writes.append(("PATCH", path, payload or {}))
        return json_response({})

    def delete(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        self._fail_if_routed("DELETE", path)
        self.writes.append(("DELETE", path, payload or {}))
        return json_response({})


def claim(fake: FakeGitHub) -> implementer_claim.ClaimOutcome:
    client = cast(GitHubClient, fake)
    return implementer_claim.claim_branch(client, client, REPO, ISSUE, RUN_ID)


def test_free_branch_is_created_at_main():
    fake = FakeGitHub()
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.CLAIMED
    assert outcome.branch == BRANCH
    assert fake.writes == [("POST", CREATE_REF, {"ref": f"refs/heads/{BRANCH}", "sha": MAIN_SHA})]


@pytest.mark.parametrize(
    "pull",
    [
        pull_request(number=7, body="Closes #12"),
        pull_request(number=7, state="closed", merged_at="2026-11-01T00:00:00Z", body="closes #12"),
    ],
    ids=["open", "merged"],
)
@pytest.mark.parametrize("branch_sha", [None, OLD_SHA], ids=["no-branch", "branch-exists"])
def test_a_pull_request_closing_the_issue_stops_without_writes(pull, branch_sha):
    fake = FakeGitHub(pulls=[pull], branch_sha=branch_sha)
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.PR_EXISTS
    assert outcome.pull_request == 7
    assert fake.writes == []


def test_an_open_pull_request_on_the_branch_stops_even_without_closes():
    # The stop rule's draft pull request need not say "Closes #<n>".
    pull = pull_request(
        number=9, body="Draft: checks stay red", head_label=f"fabiandistler:{BRANCH}"
    )
    fake = FakeGitHub(pulls=[pull], branch_sha=AHEAD_SHA, ahead_by=2)
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.PR_EXISTS
    assert outcome.pull_request == 9
    assert fake.writes == []


@pytest.mark.parametrize(
    "pull",
    [
        pull_request(body="Closes #123"),
        pull_request(body="See `Closes #12` in the docs"),
        pull_request(body=None),
        pull_request(state="closed", body="Closes #12"),
        pull_request(head_label=f"someone-else:{BRANCH}"),
    ],
    ids=["other-issue", "quoted", "null-body", "closed-unmerged", "fork-branch"],
)
def test_other_pull_requests_do_not_hold_the_issue(pull):
    fake = FakeGitHub(pulls=[pull])
    assert claim(fake).outcome == implementer_claim.CLAIMED


def test_an_empty_branch_behind_main_is_fast_forwarded_without_force():
    fake = FakeGitHub(branch_sha=OLD_SHA, ahead_by=0)
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.RECLAIMED
    assert fake.compared == [f"/repos/{REPO}/compare/{MAIN_SHA}...{OLD_SHA}"]
    assert fake.writes == [("PATCH", UPDATE_REF, {"sha": MAIN_SHA, "force": False})]


def test_an_empty_branch_already_at_main_needs_no_write():
    fake = FakeGitHub(branch_sha=MAIN_SHA, ahead_by=0)
    assert claim(fake).outcome == implementer_claim.RECLAIMED
    assert fake.writes == []


@pytest.mark.parametrize(
    "pulls",
    [[], [pull_request(state="closed", body="Closes #12", head_label=f"fabiandistler:{BRANCH}")]],
    ids=["crashed-run", "pr-closed-unmerged"],
)
def test_a_branch_with_commits_goes_to_a_person(pulls):
    fake = FakeGitHub(pulls=pulls, branch_sha=AHEAD_SHA, ahead_by=3)
    outcome = claim(fake)
    assert outcome.outcome == implementer_claim.NEEDS_HUMAN
    assert [write[:2] for write in fake.writes] == [
        ("POST", COMMENTS),
        ("POST", LABELS),
        ("DELETE", REMOVE_LABEL),
    ]
    comment = fake.writes[0][2]["body"]
    assert comment.startswith("> *This was generated by AI.*\n")
    assert f"`{BRANCH}`" in comment
    assert "add `ready-for-agent` again" in comment
    assert fake.writes[1][2] == {"labels": ["ready-for-human"]}


def test_a_handoff_tolerates_a_label_that_is_already_gone():
    fake = FakeGitHub(
        branch_sha=AHEAD_SHA,
        ahead_by=1,
        errors={("DELETE", REMOVE_LABEL): http_error(404, REMOVE_LABEL)},
    )
    assert claim(fake).outcome == implementer_claim.NEEDS_HUMAN


@pytest.mark.parametrize(
    "route",
    [
        ("GET", PULLS),
        ("GET", MAIN_REF),
        ("POST", CREATE_REF),
    ],
    ids=["list-pulls", "read-main", "create-ref"],
)
def test_other_api_errors_before_the_claim_propagate_without_writes(route):
    fake = FakeGitHub(errors={route: http_error(503, route[1])})
    with pytest.raises(pr_github_client.FetchError):
        claim(fake)
    assert fake.writes == []


@pytest.mark.parametrize(
    "route",
    [
        ("GET", BRANCH_REF),
        ("GET", f"/repos/{REPO}/compare/{MAIN_SHA}...{AHEAD_SHA}"),
        ("POST", COMMENTS),
    ],
    ids=["read-branch", "compare", "comment"],
)
def test_other_api_errors_after_a_422_propagate_without_writes(route):
    fake = FakeGitHub(branch_sha=AHEAD_SHA, ahead_by=1, errors={route: http_error(500, route[1])})
    with pytest.raises(pr_github_client.FetchError) as caught:
        claim(fake)
    assert caught.value.status == 500
    assert fake.writes == []


def test_a_422_without_the_ref_is_not_an_existing_branch():
    fake = FakeGitHub(errors={("POST", CREATE_REF): http_error(422, CREATE_REF)})
    with pytest.raises(pr_github_client.FetchError) as caught:
        claim(fake)
    assert caught.value.status == 422
    assert fake.writes == []


def test_a_rejected_fast_forward_propagates():
    fake = FakeGitHub(
        branch_sha=OLD_SHA, errors={("PATCH", UPDATE_REF): http_error(422, UPDATE_REF)}
    )
    with pytest.raises(pr_github_client.FetchError):
        claim(fake)


def test_a_failed_label_removal_propagates():
    fake = FakeGitHub(
        branch_sha=AHEAD_SHA,
        ahead_by=1,
        errors={("DELETE", REMOVE_LABEL): http_error(403, REMOVE_LABEL)},
    )
    with pytest.raises(pr_github_client.FetchError):
        claim(fake)


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        (MAIN_REF, {"object": {}}),
        (PULLS, [{"number": 1}]),
    ],
    ids=["ref-without-sha", "pull-without-fields"],
)
def test_malformed_payloads_are_api_errors(route, payload):
    fake = FakeGitHub(canned_payloads={route: payload})
    with pytest.raises(pr_github_client.FetchError):
        claim(fake)


def test_a_malformed_comparison_is_an_api_error():
    compare = f"/repos/{REPO}/compare/{MAIN_SHA}...{OLD_SHA}"
    fake = FakeGitHub(branch_sha=OLD_SHA, canned_payloads={compare: {"ahead_by": "many"}})
    with pytest.raises(pr_github_client.FetchError):
        claim(fake)


# The command line: exit codes, JSON on stdout, and the RUN FAILED line.


OWN_WORKFLOW_REF = f"{REPO}/.github/workflows/implementer.yml@{MAIN}"


def run_main(
    monkeypatch, tmp_path, *options: str, workflow_ref: str | None = OWN_WORKFLOW_REF
) -> tuple[int, Path]:
    """Run main() with GITHUB_WORKFLOW_REF pinned; ``workflow_ref=None`` unsets it.

    Actions exports GITHUB_WORKFLOW_REF to every step and main() reads it, so a
    test that left it alone would list the runs of whatever workflow runs the
    suite (ci.yml in CI). Every test that gets past argument parsing comes here.
    """
    if workflow_ref is None:
        monkeypatch.delenv("GITHUB_WORKFLOW_REF", raising=False)
    else:
        monkeypatch.setenv("GITHUB_WORKFLOW_REF", workflow_ref)
    summary = tmp_path / "run-summary.md"
    code = implementer_claim.main(
        [
            *("--repo", REPO, "--issue", str(ISSUE), "--summary", str(summary)),
            *("--contract", str(tmp_path / "contract.md")),
            *options,
        ]
    )
    return code, summary


def run_cli(
    monkeypatch, tmp_path, fake, *options: str, workflow_ref: str | None = OWN_WORKFLOW_REF
) -> tuple[int, Path]:
    """Run main() against the fake, with both tokens and this run's id set."""
    monkeypatch.setattr(implementer_claim, "GitHubClient", lambda token: fake)
    monkeypatch.setenv("GH_TOKEN", "app-token")
    monkeypatch.setenv("ACTIONS_READ_TOKEN", "job-token")
    monkeypatch.setenv("GITHUB_RUN_ID", str(RUN_ID))
    return run_main(monkeypatch, tmp_path, *options, workflow_ref=workflow_ref)


def test_cli_ignores_the_workflow_that_runs_the_suite(monkeypatch, tmp_path):
    # CI runs the suite under ci.yml: every step inherits its GITHUB_WORKFLOW_REF.
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", f"{REPO}/.github/workflows/ci.yml@{MAIN}")
    code, _ = run_cli(monkeypatch, tmp_path, FakeGitHub())  # Its run list is implementer.yml.
    assert code == implementer_claim.EXIT_CONTINUE


@pytest.mark.parametrize(
    ("fake", "outcome", "expected_code"),
    [
        (FakeGitHub(), "claimed", 0),
        (FakeGitHub(branch_sha=OLD_SHA), "reclaimed", 0),
        (FakeGitHub(pulls=[pull_request(body="Closes #12")]), "pr-exists", 3),
        (FakeGitHub(branch_sha=AHEAD_SHA, ahead_by=1), "needs-human", 4),
    ],
    ids=["claimed", "reclaimed", "pr-exists", "needs-human"],
)
def test_cli_reports_each_outcome(monkeypatch, tmp_path, capsys, fake, outcome, expected_code):
    code, summary = run_cli(monkeypatch, tmp_path, fake)
    printed = json.loads(capsys.readouterr().out)
    assert code == expected_code
    assert printed["outcome"] == outcome
    assert printed["branch"] == BRANCH
    assert not summary.exists(), "only a failed claim writes the run summary"


def test_cli_failure_writes_the_line_that_turns_the_run_red(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(errors={("POST", CREATE_REF): http_error(503, CREATE_REF)})
    code, summary = run_cli(monkeypatch, tmp_path, fake)
    printed = json.loads(capsys.readouterr().out)
    assert code == implementer_claim.EXIT_FAILED
    assert printed["outcome"] == "failed"
    text = summary.read_text(encoding="utf-8")
    assert text == f"RUN FAILED: claim (GitHub API returned 503 for {CREATE_REF})\n"
    report, report_code = agent_run_report.build_report(text, None)
    assert report_code == agent_run_report.EXIT_RUN_FAILED
    assert "RUN FAILED: claim" in report


def test_cli_without_a_token_fails_the_claim(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    code, summary = run_main(monkeypatch, tmp_path)
    assert code == implementer_claim.EXIT_FAILED
    assert json.loads(capsys.readouterr().out)["reason"] == "GH_TOKEN is not set"
    assert summary.read_text(encoding="utf-8").startswith("RUN FAILED: claim (GH_TOKEN")


def test_failure_output_carries_no_issue_or_pull_request_text(monkeypatch, tmp_path, capsys):
    private_text = "Salary of Jane Doe"
    fake = FakeGitHub(
        pulls=[pull_request(body=private_text)],
        errors={("POST", CREATE_REF): http_error(500, CREATE_REF)},
    )
    _, summary = run_cli(monkeypatch, tmp_path, fake)
    out = capsys.readouterr()
    assert private_text not in out.out + out.err
    assert private_text not in summary.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "arguments",
    [
        ["--repo", "not-a-repo", "--issue", "12", "--summary", "s"],
        ["--repo", REPO, "--issue", "0", "--summary", "s"],
        ["--repo", REPO, "--issue", "1; rm -rf /", "--summary", "s"],
        ["--repo", REPO, "--issue", "12"],
        ["--repo", REPO, "--issue", "12", "--summary", "s"],
    ],
    ids=["bad-repo", "zero-issue", "non-numeric-issue", "missing-summary", "missing-contract"],
)
def test_cli_rejects_bad_usage_before_any_call(arguments, capsys):
    with pytest.raises(SystemExit) as caught:
        implementer_claim.main(arguments)
    assert caught.value.code == implementer_claim.EXIT_USAGE
