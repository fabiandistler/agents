"""Shared fakes and builders for the writer tests (test_pr_apply*.py).

``FakeClient`` records the method, path and payload of every call so the tests
assert the exact HTTP conversation; no test performs a network call.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pr_actions
import pr_github_client

REPO = "fabiandistler/agents"
NUMBER = 42
LABELS_PATH = f"/repos/{REPO}/labels"
ISSUE_LABELS_PATH = f"/repos/{REPO}/issues/{NUMBER}/labels"
ISSUE_COMMENTS_PATH = f"/repos/{REPO}/issues/{NUMBER}/comments"
REVIEWERS_PATH = f"/repos/{REPO}/pulls/{NUMBER}/requested_reviewers"
ASSIGNEES_PATH = f"/repos/{REPO}/issues/{NUMBER}/assignees"
BOT = pr_actions.BOT_LOGIN

SCRIPT = Path(__file__).resolve().parent / "pr_apply.py"


class FakeClient:
    """A routed fake for the write surface, recording every call."""

    def __init__(self, handler=None) -> None:
        self.calls: list[dict] = []
        self.handler = handler

    def _call(self, method: str, path: str, payload: dict | None) -> pr_github_client.Response:
        self.calls.append({"method": method, "path": path, "payload": payload})
        if self.handler is not None:
            outcome = self.handler(method, path, payload)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return pr_github_client.Response(status=200, body=b"{}")

    def post(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        return self._call("POST", path, payload)

    def patch(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        return self._call("PATCH", path, payload)

    def delete(self, path: str, payload: dict | None = None) -> pr_github_client.Response:
        return self._call("DELETE", path, payload)


def make_plan(actions: list[dict] | None = None, **overrides: object) -> dict:
    plan = {
        "schema_version": 1,
        "repo": REPO,
        "number": NUMBER,
        "head_sha": "abc123",
        "status": "planned",
        "abort_reason": None,
        "actions": [] if actions is None else actions,
        "decision": {
            "risk": "low",
            "review_status": "ok",
            "verdict": "pass",
            "auto_merge": "off",
        },
    }
    plan.update(overrides)
    return plan


def calls_of(client: FakeClient, method: str) -> list[dict]:
    return [call for call in client.calls if call["method"] == method]


def paths(client: FakeClient) -> list[tuple[str, str]]:
    return [(call["method"], call["path"]) for call in client.calls]


def only_result(results: list[dict]) -> dict:
    assert len(results) == 1
    return results[0]


def write_plan(tmp_path: Path, plan: dict, name: str = "plan.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def run_cli(*args: str, **env: str) -> subprocess.CompletedProcess:
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GITHUB_ACTIONS", "GITHUB_TOKEN"}
    }
    clean_env.update(env)
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )
