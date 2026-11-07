"""Shared builders and fakes for the publish tests (test_pr_*.py of the publisher).

Every publish test builds its context, assessment and review here, and the live
tests serve ``fetch_context`` from ``FakeGitHub``; keep new fixtures in this one
place so the test modules stay small.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pr_github_client

SCRIPT = Path(__file__).resolve().parent / "pr_publish.py"
MARKER = "<!-- pr-review-bot -->"
# The login GITHUB_TOKEN writes as; only its comments can be the sticky comment.
BOT_AUTHOR = "github-actions[bot]"
BOT = "fabiandistler"

ACTION_KINDS = {
    "set_labels",
    "upsert_comment",
    "request_reviewer",
    "assign",
    "enable_auto_merge",
    "disable_auto_merge",
}


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
        "node_id": "PR_kwDOtest42",
        "title": "A change",
        "body": "",
        "author": "someone-else",
        "head_sha": "abc123",
        "head_ref": "fix/x",
        "base_ref": "main",
        "default_branch": "main",
        "draft": False,
        "fork": False,
        "mergeable": True,
        "auto_merge_active": False,
        "labels": [],
        "files": [file_entry("docs/guide.md")] if files is None else files,
        "diff": "",
        "diff_status": "complete",
        "base_files": {},
        "comments": [],
        "checks": {"checks": "success", "mermaid": "success", "secrets": "success"},
        "reviews": {"changes_requested": False},
    }
    context.update(overrides)
    return context


def make_assessment(**overrides: object) -> dict:
    assessment = {
        "schema_version": 1,
        "number": 42,
        "head_sha": "abc123",
        "risk": "low",
        "reasons": ["docs: docs/guide.md"],
        "auto_merge_eligible": True,
        "counts": {"files": 1, "additions": 1, "deletions": 0, "changed_lines": 1},
    }
    assessment.update(overrides)
    return assessment


def make_review(**overrides: object) -> dict:
    review = {
        "schema_version": 1,
        "number": 42,
        "head_sha": "abc123",
        "status": "ok",
        "risk": "low",
        "verdict": "pass",
        "summary": "The documentation change is accurate and complete.",
        "findings": [
            {
                "path": "docs/guide.md",
                "line": 12,
                "severity": "info",
                "message": "The heading could name the command it documents.",
                "suggestion": "Use the command name in the heading.",
            }
        ],
        "partial": False,
        "raw": None,
    }
    review.update(overrides)
    return review


def actions_of(plan: dict, kind: str) -> list[dict]:
    return [action for action in plan["actions"] if action["kind"] == kind]


def label_action(plan: dict) -> dict:
    labels = actions_of(plan, "set_labels")
    assert len(labels) == 1
    return labels[0]


def comment_action(plan: dict) -> dict:
    comments = actions_of(plan, "upsert_comment")
    assert len(comments) == 1
    return comments[0]


REPO = "fabiandistler/agents"
NUMBER = 42
PR_PATH = f"/repos/{REPO}/pulls/{NUMBER}"
FILES_PATH = f"{PR_PATH}/files"
COMMENTS_PATH = f"/repos/{REPO}/issues/{NUMBER}/comments"
REVIEWS_PATH = f"{PR_PATH}/reviews"
CONTENTS_PREFIX = f"/repos/{REPO}/contents/"


def json_response(payload: object) -> pr_github_client.Response:
    return pr_github_client.Response(status=200, body=json.dumps(payload).encode("utf-8"))


def pull_request(head_sha: str, labels: list[str]) -> dict:
    return {
        "title": "A change",
        "body": "",
        "user": {"login": "someone-else"},
        "head": {"sha": head_sha, "ref": "fix/x", "repo": {"full_name": REPO}},
        "base": {
            "sha": "base123",
            "ref": "main",
            "repo": {"full_name": REPO, "default_branch": "main"},
        },
        "node_id": "PR_kwDOtest42",
        "draft": False,
        "mergeable": True,
        "auto_merge": None,
        "labels": [{"name": label} for label in labels],
    }


# The `auto_merge` object of a pull request payload while auto-merge is on.
ACTIVE_AUTO_MERGE = {"merge_method": "merge", "enabled_by": {"login": "github-actions[bot]"}}


ISSUE_LABELS_PATH = f"/repos/{REPO}/issues/{NUMBER}/labels"
COMMENT_PREFIX = f"/repos/{REPO}/issues/comments/"


class FakeGitHub:
    """Serves ``fetch_context`` from canned payloads and records every write.

    Label and comment writes change what later fetches return, so a replan
    after a write sees the pull request as GitHub would.
    """

    def __init__(self, head_shas: list[str], labels: list[str] | None = None) -> None:
        self.head_shas = list(head_shas)
        self.labels = list(labels or [])
        self.calls: list[dict] = []
        self.pull_fetches = 0
        self.fail_paths: set[str] = set()
        # Fields to override in every pull request payload, e.g. mergeable.
        self.pull_overrides: dict = {}
        self.comments: list[dict] = []
        # The `errors` list every GraphQL mutation answers with; empty succeeds.
        self.graphql_errors: list[dict] = []

    def get(self, path: str, params: dict | None = None, accept: str | None = None):
        self.calls.append({"method": "GET", "path": path, "payload": None})
        if path == PR_PATH and accept is None:
            self.pull_fetches += 1
            payload = pull_request(self.head_shas.pop(0), self.labels)
            return json_response({**payload, **self.pull_overrides})
        if path == PR_PATH:
            return pr_github_client.Response(status=200, body=b"diff --git a/x b/x\n")
        if path == FILES_PATH:
            return json_response(
                [
                    {
                        "filename": "docs/guide.md",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 0,
                        "patch": "@@",
                    }
                ]
            )
        if path == COMMENTS_PATH:
            return json_response(
                [
                    {"id": comment["id"], "body": comment["body"], "user": {"login": BOT_AUTHOR}}
                    for comment in self.comments
                ]
            )
        if path == REVIEWS_PATH:
            return json_response([])
        if path.endswith("/check-runs"):
            return json_response({"check_runs": []})
        if path.startswith(CONTENTS_PREFIX):
            raise pr_github_client.FetchError("not found", status=404)
        if "/git/trees/" in path:
            return json_response({"tree": [], "truncated": False})
        raise AssertionError(f"unexpected GET {path}")

    def _write(self, method: str, path: str, payload: dict | None):
        self.calls.append({"method": method, "path": path, "payload": payload})
        if path in self.fail_paths:
            raise pr_github_client.FetchError("server error", status=500)
        self._track(method, path, payload or {})
        if path == "/graphql" and self.graphql_errors:
            return json_response({"data": None, "errors": self.graphql_errors})
        return pr_github_client.Response(status=200, body=b"{}")

    def _track(self, method: str, path: str, payload: dict) -> None:
        if method == "POST" and path == ISSUE_LABELS_PATH:
            self.labels += [label for label in payload["labels"] if label not in self.labels]
        elif method == "DELETE" and path.startswith(f"{ISSUE_LABELS_PATH}/"):
            name = urllib.parse.unquote(path.rsplit("/", 1)[-1])
            self.labels = [label for label in self.labels if label != name]
        elif method == "POST" and path == COMMENTS_PATH:
            self.comments.append({"id": 900 + len(self.comments), "body": payload["body"]})
        elif method == "PATCH" and path.startswith(COMMENT_PREFIX):
            comment_id = int(path.rsplit("/", 1)[-1])
            for comment in self.comments:
                if comment["id"] == comment_id:
                    comment["body"] = payload["body"]

    def post(self, path: str, payload: dict | None = None):
        return self._write("POST", path, payload)

    def patch(self, path: str, payload: dict | None = None):
        return self._write("PATCH", path, payload)

    def delete(self, path: str, payload: dict | None = None):
        return self._write("DELETE", path, payload)


def write_calls(fake: FakeGitHub) -> list[dict]:
    return [call for call in fake.calls if call["method"] != "GET"]


def write_json(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_cli(*args: str, **env: str) -> subprocess.CompletedProcess:
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PR_AUTO_MERGE", "GITHUB_TOKEN"}
    }
    clean_env.update(env)
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )


def offline_args(tmp_path: Path) -> list[str]:
    return [
        "--context",
        str(write_json(tmp_path, "context.json", make_context())),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    ]


def live_args(tmp_path: Path) -> list[str]:
    return [
        "--live",
        "--repo",
        REPO,
        "--pr",
        str(NUMBER),
        "--assessment",
        str(write_json(tmp_path, "assessment.json", make_assessment())),
        "--review",
        str(write_json(tmp_path, "review.json", make_review())),
    ]
