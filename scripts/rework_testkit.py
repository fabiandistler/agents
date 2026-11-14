"""Shared fixtures for the Rework gate suites: a passing set of gate facts and a routed fake API.

``facts()`` returns inputs on which ``rework_policy.decide`` proceeds; each test
breaks one of them. ``FakeGitHub`` routes the gate's REST calls and records
every write.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import pr_github_client

REPO = "fabiandistler/agents"
PR = 42
ISSUE = 12
HEAD = "a" * 40
OTHER_HEAD = "b" * 40
THIRD_HEAD = "c" * 40
REVIEW_RUN = 900
OWN_RUN = 1000
BOT = "github-actions[bot]"

PR_COMMENTS = f"/repos/{REPO}/issues/{PR}/comments"
ISSUE_PATH = f"/repos/{REPO}/issues/{ISSUE}"
REWORK_RUNS = f"/repos/{REPO}/actions/workflows/rework.yml/runs"


def finding(message: str = "Missing test") -> dict:
    return {"path": "scripts/x.py", "line": 3, "severity": "warning", "message": message}


def review(**overrides: object) -> dict:
    payload = {
        "number": PR,
        "head_sha": HEAD,
        "status": "ok",
        "verdict": "concerns",
        "findings": [finding()],
    }
    payload.update(overrides)
    return payload


def context(**overrides: object) -> dict:
    payload = {"number": PR, "head_sha": HEAD, "fork": False}
    payload.update(overrides)
    return payload


def run(**overrides: object) -> dict:
    payload = {
        "id": REVIEW_RUN,
        "path": ".github/workflows/pr-review.yml",
        "conclusion": "success",
        "event": "pull_request_target",
        # A pull_request_target run carries the pull request's head commit.
        "head_sha": HEAD,
    }
    payload.update(overrides)
    return payload


def head(ref: str = f"agent/issue-{ISSUE}", sha: str = HEAD, repo: str = REPO) -> dict:
    return {"ref": ref, "sha": sha, "repo": {"full_name": repo}}


def pull(**overrides: object) -> dict:
    payload = {
        "number": PR,
        "state": "open",
        "draft": False,
        "body": f"Closes #{ISSUE}\n",
        "user": {"login": "claude[bot]", "type": "Bot"},
        "head": head(),
        "base": {"ref": "main", "repo": {"full_name": REPO}},
        "labels": [{"name": "review:concerns"}],
    }
    payload.update(overrides)
    return payload


def issue(**overrides: object) -> dict:
    payload = {"number": ISSUE, "state": "open", "labels": [{"name": "ready-for-agent"}]}
    payload.update(overrides)
    return payload


def comment(body: str, author: str = BOT) -> dict:
    return {"id": 1, "body": body, "author": author}


def marker(round_number: int, head: str) -> str:
    return f"<!-- rework-round:{round_number} head:{head} -->"


def facts(**overrides: object) -> dict:
    payload = {
        "repo": REPO,
        "run": run(),
        "review": review(),
        "context": context(),
        "pull": pull(),
        "issue": issue(),
        "comments": [],
    }
    payload.update(overrides)
    return payload


def json_response(payload: object) -> pr_github_client.Response:
    return pr_github_client.Response(status=200, body=json.dumps(payload).encode("utf-8"))


def gate_job(name: str = "gate", status: str = "in_progress", started: str = "") -> dict:
    return {"name": name, "status": status, "started_at": started or "2026-11-14T10:00:00Z"}


@dataclass
class FakeGitHub:
    """Routes the gate's REST calls; ``comments`` are REST comment payloads."""

    run: dict = field(default_factory=run)
    pull: dict = field(default_factory=pull)
    issue: dict = field(default_factory=issue)
    comments: list[dict] = field(default_factory=list)
    jobs: dict[int, list[dict]] = field(default_factory=lambda: {OWN_RUN: [gate_job()]})
    review_runs: list[dict] = field(default_factory=list)
    missing_label: bool = False
    failing_label_add: bool = False
    writes: list[tuple[str, str, dict | None]] = field(default_factory=list)

    def get(
        self, path: str, params: dict | None = None, accept: str | None = None
    ) -> pr_github_client.Response:
        params = params or {}
        if path == f"/repos/{REPO}/actions/runs/{REVIEW_RUN}":
            return json_response(self.run)
        if path == f"/repos/{REPO}/pulls/{PR}":
            return json_response(self.pull)
        if path == ISSUE_PATH:
            return json_response(self.issue)
        if path == PR_COMMENTS:
            return json_response(self.comments if params.get("page") == 1 else [])
        if path == REWORK_RUNS:
            runs = [{"id": run_id} for run_id in self.jobs]
            return json_response({"total_count": len(runs), "workflow_runs": runs})
        if (match := re.fullmatch(rf"/repos/{REPO}/actions/runs/(\d+)/jobs", path)) is not None:
            jobs = self.jobs[int(match[1])]
            return json_response({"total_count": len(jobs), "jobs": jobs})
        if path == f"/repos/{REPO}/actions/workflows/pr-review.yml/runs":
            if params["head_sha"] != self.pull["head"]["sha"]:
                raise AssertionError("runs must be listed for the live head")
            if params["event"] != "pull_request_target":
                raise AssertionError("only pull request reviews count")
            return json_response({"total_count": 1, "workflow_runs": self.review_runs})
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        self.writes.append(("POST", path, payload))
        if self.failing_label_add and path == f"{ISSUE_PATH}/labels":
            raise pr_github_client.FetchError(f"GitHub API returned 502 for {path}", status=502)
        if path == PR_COMMENTS and payload is not None:
            # A posted comment is seen by the next run, as on GitHub.
            self.comments.append({"id": 9, "body": payload["body"], "user": {"login": BOT}})
        return json_response({})

    def patch(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        self.writes.append(("PATCH", path, payload))
        return json_response({})

    def delete(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        self.writes.append(("DELETE", path, payload))
        if self.missing_label:
            raise pr_github_client.FetchError(f"GitHub API returned 404 for {path}", status=404)
        return json_response({})


def rest_comment(body: str, login: str = BOT) -> dict:
    return {"id": 3, "body": body, "user": {"login": login}}
