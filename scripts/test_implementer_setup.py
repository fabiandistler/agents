"""The claim called as a reusable workflow: workflow file, job name and branch prefix."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import implementer_claim
import pr_github_client
import pytest
from implementer_setup import ImplementerSetup
from pr_github_client import GitHubClient
from test_implementer_claim import (
    AHEAD_SHA,
    BRANCH,
    CREATE_REF,
    ISSUE,
    JOB_START,
    MAIN,
    MAIN_SHA,
    OLD_SHA,
    OWN_WORKFLOW_REF,
    PULLS,
    REPO,
    RUN_ID,
    FakeGitHub,
    pull_request,
    run_cli,
)

SCRIPT = Path(implementer_claim.__file__).resolve()
CALLER_REF = f"other/repo/.github/workflows/agent.yml@{MAIN}"
FACTORY_BRANCH = f"factory/issue-{ISSUE}"
FACTORY = ImplementerSetup(branch_prefix="factory/issue-")


def called_job(name: str, started_at: str = JOB_START) -> dict:
    return {"name": name, "status": "in_progress", "started_at": started_at}


def last_report(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("workflow_ref", [None, OWN_WORKFLOW_REF], ids=["unset", "implementer"])
def test_without_options_the_run_list_is_implementer_yml(monkeypatch, tmp_path, workflow_ref):
    fake = FakeGitHub()  # Its run list route is implementer.yml; any other GET fails.
    code, _ = run_cli(monkeypatch, tmp_path, fake, workflow_ref=workflow_ref)
    assert code == implementer_claim.EXIT_CONTINUE


def test_the_caller_workflow_ref_names_the_run_list(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(workflow_file="agent.yml")
    code, _ = run_cli(monkeypatch, tmp_path, fake, workflow_ref=CALLER_REF)
    assert code == implementer_claim.EXIT_CONTINUE
    assert last_report(capsys)["outcome"] == "claimed"


def test_the_workflow_file_option_wins_over_the_workflow_ref(monkeypatch, tmp_path):
    fake = FakeGitHub(workflow_file="factory.yaml")
    code, _ = run_cli(
        monkeypatch, tmp_path, fake, "--workflow-file", "factory.yaml", workflow_ref=CALLER_REF
    )
    assert code == implementer_claim.EXIT_CONTINUE


@pytest.mark.parametrize(
    ("other_job", "outcome"),
    [("call / implement", implementer_claim.AT_CAPACITY), ("call / other", "claimed")],
    ids=["called-implement", "called-other"],
)
def test_a_called_job_counts_by_its_own_name(other_job, outcome):
    fake = FakeGitHub(
        jobs={
            RUN_ID: [called_job("call / implement")],
            4999: [called_job(other_job, started_at="2026-11-10T09:55:00Z")],
        }
    )
    client = cast(GitHubClient, fake)
    setup = ImplementerSetup(job_name="implement")
    assert implementer_claim.claim_branch(client, client, REPO, ISSUE, RUN_ID, setup).outcome == (
        outcome
    )


def test_the_job_name_option_reaches_the_capacity_gate(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(
        jobs={
            RUN_ID: [called_job("factory / build")],
            4999: [called_job("factory / build", started_at="2026-11-10T09:55:00Z")],
        }
    )
    code, _ = run_cli(monkeypatch, tmp_path, fake, "--job-name", "build")
    assert code == implementer_claim.EXIT_AT_CAPACITY
    assert last_report(capsys)["outcome"] == implementer_claim.AT_CAPACITY


def test_a_job_whose_name_only_ends_like_the_job_name_does_not_count():
    fake = FakeGitHub(jobs={RUN_ID: [called_job("call / reimplement")]})
    client = cast(GitHubClient, fake)
    with pytest.raises(pr_github_client.FetchError, match="no working implement job"):
        implementer_claim.claim_branch(client, client, REPO, ISSUE, RUN_ID)


def claim_factory(fake: FakeGitHub) -> implementer_claim.ClaimOutcome:
    client = cast(GitHubClient, fake)
    return implementer_claim.claim_branch(client, client, REPO, ISSUE, RUN_ID, FACTORY)


def test_the_branch_prefix_names_the_claimed_branch(monkeypatch, tmp_path, capsys):
    fake = FakeGitHub(branch=FACTORY_BRANCH)
    code, _ = run_cli(monkeypatch, tmp_path, fake, "--branch-prefix", "factory/issue-")
    assert code == implementer_claim.EXIT_CONTINUE
    assert last_report(capsys)["branch"] == FACTORY_BRANCH
    assert fake.writes == [
        ("POST", CREATE_REF, {"ref": f"refs/heads/{FACTORY_BRANCH}", "sha": MAIN_SHA})
    ]


def test_the_branch_prefix_names_the_reclaimed_branch():
    fake = FakeGitHub(branch=FACTORY_BRANCH, branch_sha=OLD_SHA)
    outcome = claim_factory(fake)
    assert (outcome.outcome, outcome.branch) == (implementer_claim.RECLAIMED, FACTORY_BRANCH)
    assert fake.writes == [
        (
            "PATCH",
            f"/repos/{REPO}/git/refs/heads/{FACTORY_BRANCH}",
            {"sha": MAIN_SHA, "force": False},
        )
    ]


def test_the_handoff_comment_names_the_prefixed_branch():
    fake = FakeGitHub(branch=FACTORY_BRANCH, branch_sha=AHEAD_SHA, ahead_by=1)
    outcome = claim_factory(fake)
    assert (outcome.outcome, outcome.branch) == (implementer_claim.NEEDS_HUMAN, FACTORY_BRANCH)
    comment = fake.writes[0][2]["body"]
    assert f"`{FACTORY_BRANCH}`" in comment
    assert BRANCH not in comment


def test_an_open_pull_request_on_the_prefixed_branch_holds_the_issue():
    fake = FakeGitHub(
        branch=FACTORY_BRANCH,
        pulls=[
            pull_request(number=8, body="Draft", head_label=f"fabiandistler:{BRANCH}"),
            pull_request(number=9, body="Draft", head_label=f"fabiandistler:{FACTORY_BRANCH}"),
        ],
    )
    outcome = claim_factory(fake)
    assert (outcome.outcome, outcome.pull_request) == (implementer_claim.PR_EXISTS, 9)
    assert fake.writes == []


@pytest.mark.parametrize(
    ("options", "workflow_ref", "reason"),
    [
        (("--workflow-file", "../agent.yml"), None, "--workflow-file"),
        (("--workflow-file", "workflows/agent.yml"), None, "--workflow-file"),
        (("--workflow-file", "agent.json"), None, "--workflow-file"),
        (("--workflow-file", "agent.yml?x=1"), None, "--workflow-file"),
        (("--workflow-file", ""), None, "--workflow-file"),
        ((), "agent.yml", "GITHUB_WORKFLOW_REF"),
        ((), "other/repo/.github/workflows/agent.json@refs/heads/main", "GITHUB_WORKFLOW_REF"),
        (("--branch-prefix", "agent/issue"), None, "--branch-prefix"),
        (("--branch-prefix", "agent issue-"), None, "--branch-prefix"),
        (("--branch-prefix", "agent/issue-;x/"), None, "--branch-prefix"),
        (("--branch-prefix", "-"), None, "--branch-prefix"),
    ],
    ids=[
        "parent-dir",
        "path",
        "not-yaml",
        "query",
        "empty",
        "ref-without-path",
        "ref-not-yaml",
        "prefix-without-separator",
        "prefix-space",
        "prefix-semicolon",
        "prefix-only-dash",
    ],
)
def test_invalid_setup_fails_before_any_call(
    monkeypatch, tmp_path, capsys, options, workflow_ref, reason
):
    fake = FakeGitHub(errors={("GET", PULLS): AssertionError("no call may happen")})
    code, summary = run_cli(monkeypatch, tmp_path, fake, *options, workflow_ref=workflow_ref)
    report = last_report(capsys)
    assert code == implementer_claim.EXIT_FAILED
    assert report["outcome"] == "failed"
    assert report["reason"].startswith(reason)
    assert summary.read_text(encoding="utf-8").startswith(f"RUN FAILED: claim ({reason}")
    assert fake.writes == []


def test_the_script_runs_from_another_checkout(tmp_path):
    # The reusable workflow runs it from $RUNNER_TEMP/factory/scripts/ while the
    # working directory is the target repository: its siblings must still import.
    summary = tmp_path / "run-summary.md"
    environment = {"PATH": os.environ.get("PATH", ""), "GITHUB_RUN_ID": str(RUN_ID)}
    completed = subprocess.run(  # noqa: S603 -- a fixed interpreter and this repository's script.
        [
            *(sys.executable, str(SCRIPT), "--repo", REPO, "--issue", str(ISSUE)),
            *("--summary", str(summary), "--contract", str(tmp_path / "contract.md")),
            *("--workflow-file", "agent.yml", "--branch-prefix", "factory/issue-"),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.stderr == ""
    assert completed.returncode == implementer_claim.EXIT_FAILED
    assert json.loads(completed.stdout) == {"outcome": "failed", "reason": "GH_TOKEN is not set"}
