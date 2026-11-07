"""Test double for the GitHub REST fetcher (scripts/pr_github.py).

``FakeClient`` speaks the same ``get`` contract as ``GitHubClient`` and returns
``Response`` objects, so the ``test_pr_github*`` suites exercise pagination,
diff fetching and base-file budgeting without a network call.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pr_github
import pr_github_client

REPO = "fabiandistler/agents"
NUMBER = 42
PR_PATH = f"/repos/{REPO}/pulls/{NUMBER}"
FILES_PATH = f"{PR_PATH}/files"
COMMENTS_PATH = f"/repos/{REPO}/issues/{NUMBER}/comments"
REVIEWS_PATH = f"{PR_PATH}/reviews"
CONTENTS_PREFIX = f"/repos/{REPO}/contents/"
TREE_PATH = f"/repos/{REPO}/git/trees/base-sha"

SCRIPT = Path(__file__).resolve().parent / "pr_github.py"
DIFF_ACCEPT = "application/vnd.github.v3.diff"

OMITTED = object()


@dataclass
class Call:
    path: str
    params: dict
    accept: str | None


def json_response(payload: object, status: int = 200) -> pr_github_client.Response:
    return pr_github_client.Response(status=status, body=json.dumps(payload).encode("utf-8"))


def text_response(text: str, status: int = 200) -> pr_github_client.Response:
    return pr_github_client.Response(status=status, body=text.encode("utf-8"))


class FakeClient:
    """A routed fake for the read-only client surface."""

    def __init__(
        self,
        pr: dict | None = None,
        *,
        file_pages: tuple[list[dict], ...] = (),
        comment_pages: tuple[list[dict], ...] = (),
        review_pages: tuple[list[dict], ...] = (),
        diff: str = "",
        contents: dict[str, Any] | None = None,
        tree: object = None,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.pr = pull_request() if pr is None else pr
        self.file_pages = file_pages or ([],)
        self.comment_pages = comment_pages or ([],)
        self.review_pages = review_pages or ([],)
        self.diff = diff
        self.contents = contents or {}
        self.tree = {"sha": "base-sha", "tree": [], "truncated": False} if tree is None else tree
        self.errors = errors or {}
        self.calls: list[Call] = []

    def get(
        self, path: str, params: dict | None = None, accept: str | None = None
    ) -> pr_github_client.Response:
        params = dict(params or {})
        self.calls.append(Call(path, params, accept))
        # An error keyed "<path>#diff" fails only the raw diff request.
        error_key = f"{path}#diff" if accept == DIFF_ACCEPT else path
        if error_key in self.errors:
            raise self.errors[error_key]
        if path == PR_PATH:
            if accept == DIFF_ACCEPT:
                return text_response(self.diff)
            return json_response(self.pr)
        if path == FILES_PATH:
            return _page(self.file_pages, params)
        if path == COMMENTS_PATH:
            return _page(self.comment_pages, params)
        if path == REVIEWS_PATH:
            return _page(self.review_pages, params)
        if path == TREE_PATH:
            if params != {"recursive": "1"}:
                raise AssertionError("the base tree must be fetched recursively")
            return json_response(self.tree)
        if path.startswith(CONTENTS_PREFIX):
            content_path = path[len(CONTENTS_PREFIX) :]
            handler = self.contents.get(content_path)
            if handler is None:
                raise pr_github_client.FetchError(f"GitHub API returned 404 for {path}", status=404)
            return (
                handler
                if isinstance(handler, pr_github_client.Response)
                else json_response(handler)
            )
        raise AssertionError(f"unexpected GET {path}")

    def contents_calls(self) -> list[Call]:
        return [call for call in self.calls if call.path.startswith(CONTENTS_PREFIX)]


def _page(pages: tuple[list[dict], ...], params: dict) -> pr_github_client.Response:
    if params.get("per_page") != 100:
        raise AssertionError("pagination must request per_page=100")
    page = int(params.get("page", 1))
    if page > len(pages):
        raise AssertionError(f"page {page} requested but only {len(pages)} exist")
    return json_response(pages[page - 1])


def pull_request(**overrides: object) -> dict:
    payload = {
        "number": NUMBER,
        "title": "Fix docs",
        "body": "Body",
        "user": {"login": "fabiandistler"},
        "head": {
            "sha": "abc123",
            "ref": "fix/x",
            "repo": {"full_name": REPO},
        },
        "base": {
            "ref": "main",
            "sha": "base-sha",
            "repo": {"full_name": REPO, "default_branch": "main"},
        },
        "draft": False,
        "mergeable": True,
        "labels": [{"name": "do-not-merge"}],
    }
    payload.update(overrides)
    return payload


def api_file(
    path: str,
    *,
    status: str = "modified",
    additions: int = 1,
    deletions: int = 0,
    patch: object = OMITTED,
    previous: str | None = None,
) -> dict:
    entry = {
        "filename": path,
        "status": status,
        "additions": additions,
        "deletions": deletions,
    }
    if patch is not OMITTED:
        entry["patch"] = patch
    else:
        entry["patch"] = "@@ -1 +1 @@\n"
    if previous is not None:
        entry["previous_filename"] = previous
    return entry


def binary_api_file(path: str, *, additions: int = 1, deletions: int = 0) -> dict:
    entry = {
        "filename": path,
        "status": "modified",
        "additions": additions,
        "deletions": deletions,
    }
    # No patch key: GitHub omits it for binary content.
    return entry


def contents_response(text: str | bytes, *, encoding: str = "base64", type_: str = "file") -> dict:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return {
        "type": type_,
        "encoding": encoding,
        "size": len(data),
        "content": base64.b64encode(data).decode("ascii"),
    }


def tree_entry(path: str, type_: str = "blob") -> dict:
    return {"path": path, "mode": "100644", "type": type_, "sha": "0" * 40}


def fetch(client: FakeClient) -> dict:
    return pr_github.fetch_context(REPO, NUMBER, client=client)
