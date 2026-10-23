"""Tests for the GitHub REST fetcher (scripts/pr_github.py).

Every test injects a fake client; none performs a network call. The fake
speaks the same ``get`` contract as ``GitHubClient`` and returns ``Response``
objects so pagination, diff fetching and base-file budgeting are exercised.
"""

from __future__ import annotations

import base64
import io
import json
import subprocess
import sys
import urllib.error
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import Any, cast

import pr_github
import pytest

REPO = "fabiandistler/agents"
NUMBER = 42
PR_PATH = f"/repos/{REPO}/pulls/{NUMBER}"
FILES_PATH = f"{PR_PATH}/files"
COMMENTS_PATH = f"/repos/{REPO}/issues/{NUMBER}/comments"
REVIEWS_PATH = f"{PR_PATH}/reviews"
CHECK_RUNS_PATH = f"/repos/{REPO}/commits/abc123/check-runs"
CONTENTS_PREFIX = f"/repos/{REPO}/contents/"

SCRIPT = Path(__file__).resolve().parent / "pr_github.py"
DIFF_ACCEPT = "application/vnd.github.v3.diff"

_MISSING = object()


@dataclass
class Call:
    path: str
    params: dict
    accept: str | None


def json_response(payload: object, status: int = 200) -> pr_github.Response:
    return pr_github.Response(status=status, body=json.dumps(payload).encode("utf-8"))


def text_response(text: str, status: int = 200) -> pr_github.Response:
    return pr_github.Response(status=status, body=text.encode("utf-8"))


class FakeClient:
    """A routed fake for the read-only client surface."""

    def __init__(
        self,
        pr: dict | None = None,
        *,
        file_pages: tuple[list[dict], ...] = (),
        comment_pages: tuple[list[dict], ...] = (),
        review_pages: tuple[list[dict], ...] = (),
        check_run_pages: tuple[list[dict], ...] = (),
        diff: str = "",
        contents: dict[str, Any] | None = None,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.pr = pull_request() if pr is None else pr
        self.file_pages = file_pages or ([],)
        self.comment_pages = comment_pages or ([],)
        self.review_pages = review_pages or ([],)
        self.check_run_pages = check_run_pages or ([],)
        self.diff = diff
        self.contents = contents or {}
        self.errors = errors or {}
        self.calls: list[Call] = []

    def get(
        self, path: str, params: dict | None = None, accept: str | None = None
    ) -> pr_github.Response:
        params = dict(params or {})
        self.calls.append(Call(path, params, accept))
        if path in self.errors:
            raise self.errors[path]
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
        if path == CHECK_RUNS_PATH:
            return _check_run_page(self.check_run_pages, params)
        if path.startswith(CONTENTS_PREFIX):
            content_path = path[len(CONTENTS_PREFIX) :]
            handler = self.contents.get(content_path)
            if handler is None:
                raise pr_github.FetchError(f"GitHub API returned 404 for {path}", status=404)
            return handler if isinstance(handler, pr_github.Response) else json_response(handler)
        raise AssertionError(f"unexpected GET {path}")

    def contents_calls(self) -> list[Call]:
        return [call for call in self.calls if call.path.startswith(CONTENTS_PREFIX)]


def _page(pages: tuple[list[dict], ...], params: dict) -> pr_github.Response:
    assert params.get("per_page") == 100
    page = int(params.get("page", 1))
    if page > len(pages):
        raise AssertionError(f"page {page} requested but only {len(pages)} exist")
    return json_response(pages[page - 1])


def _check_run_page(pages: tuple[list[dict], ...], params: dict) -> pr_github.Response:
    assert params.get("per_page") == 100
    page = int(params.get("page", 1))
    if page > len(pages):
        raise AssertionError(f"page {page} requested but only {len(pages)} exist")
    return json_response(
        {"total_count": sum(len(items) for items in pages), "check_runs": pages[page - 1]}
    )


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
    patch: object = _MISSING,
    previous: str | None = None,
) -> dict:
    entry = {
        "filename": path,
        "status": status,
        "additions": additions,
        "deletions": deletions,
    }
    if patch is not _MISSING:
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


def fetch(client: FakeClient) -> dict:
    return pr_github.fetch_context(REPO, NUMBER, client=client)


def test_fetch_context_maps_every_contract_field():
    client = FakeClient(
        pull_request(draft=True, mergeable=False, labels=[{"name": "risk:low"}, {"name": "x"}]),
        file_pages=(
            [
                api_file("scripts/modified.py", patch="@@ -1 +1 @@\n"),
                binary_api_file("assets/logo.png", additions=5),
                api_file("docs/old.md", status="removed", additions=0, deletions=4),
                api_file("scripts/new_name.py", status="renamed", previous="scripts/old_name.py"),
                api_file("docs/new.md", status="added", additions=2, patch="@@ -0,0 +1 @@\n"),
            ],
        ),
        comment_pages=(
            [
                {"id": 1, "body": "first", "user": {"login": "someone"}},
                {"id": 2, "body": None},
            ],
        ),
        review_pages=(
            [
                {
                    "user": {"login": "a"},
                    "state": "APPROVED",
                    "submitted_at": "2026-01-01T00:00:00Z",
                },
                {
                    "user": {"login": "b"},
                    "state": "CHANGES_REQUESTED",
                    "submitted_at": "2026-01-01T00:00:00Z",
                },
            ],
        ),
        check_run_pages=(
            [
                {"name": "checks", "conclusion": "success", "status": "completed"},
                {"name": "mermaid", "conclusion": None, "status": "in_progress"},
            ],
        ),
        diff="diff --git a/x b/x\n",
        contents={
            "scripts/modified.py": contents_response("print('x')\n"),
            "scripts/old_name.py": contents_response("old\n"),
        },
    )

    context = fetch(client)

    assert context["schema_version"] == 1
    assert context["repo"] == REPO
    assert context["number"] == NUMBER
    assert context["title"] == "Fix docs"
    assert context["body"] == "Body"
    assert context["author"] == "fabiandistler"
    assert context["head_sha"] == "abc123"
    assert context["head_ref"] == "fix/x"
    assert context["base_ref"] == "main"
    assert context["default_branch"] == "main"
    assert context["draft"] is True
    assert context["fork"] is False
    assert context["mergeable"] is False
    assert context["labels"] == ["risk:low", "x"]
    assert context["files"] == [
        {
            "path": "scripts/modified.py",
            "status": "modified",
            "additions": 1,
            "deletions": 0,
            "binary": False,
            "renamed_from": None,
        },
        {
            "path": "assets/logo.png",
            "status": "modified",
            "additions": 5,
            "deletions": 0,
            "binary": True,
            "renamed_from": None,
        },
        {
            "path": "docs/old.md",
            "status": "removed",
            "additions": 0,
            "deletions": 4,
            "binary": False,
            "renamed_from": None,
        },
        {
            "path": "scripts/new_name.py",
            "status": "renamed",
            "additions": 1,
            "deletions": 0,
            "binary": False,
            "renamed_from": "scripts/old_name.py",
        },
        {
            "path": "docs/new.md",
            "status": "added",
            "additions": 2,
            "deletions": 0,
            "binary": False,
            "renamed_from": None,
        },
    ]
    assert context["diff"] == "diff --git a/x b/x\n"
    assert context["base_files"] == {
        "scripts/modified.py": "print('x')\n",
        "scripts/new_name.py": "old\n",
    }
    assert context["comments"] == [{"id": 1, "body": "first"}, {"id": 2, "body": ""}]
    assert context["checks"] == {"checks": "success", "mermaid": "in_progress"}
    assert context["reviews"] == {"changes_requested": True}


def test_non_object_item_in_a_paginated_list_fails_safe():
    malformed_page = cast(list[dict], [api_file("docs/guide.md"), "junk"])
    client = FakeClient(file_pages=(malformed_page,))

    with pytest.raises(pr_github.FetchError):
        fetch(client)


def test_files_comments_reviews_and_check_runs_are_paginated():
    first_files = [
        api_file(f"docs/page-{index}.md", status="added", patch="@@ -0,0 +1 @@\n")
        for index in range(100)
    ]
    client = FakeClient(
        file_pages=(
            first_files,
            [api_file("docs/last.md", status="added", patch="@@ -0,0 +1 @@\n")],
        ),
        comment_pages=(
            [{"id": index, "body": "x"} for index in range(100)],
            [{"id": 100, "body": "y"}],
        ),
        review_pages=(
            [{"user": {"login": f"u{index}"}, "state": "COMMENTED"} for index in range(100)],
            [{"user": {"login": "late"}, "state": "CHANGES_REQUESTED"}],
        ),
        check_run_pages=(
            [{"name": f"check-{index}", "conclusion": "success"} for index in range(100)],
            [{"name": "last", "conclusion": "success"}],
        ),
    )

    context = fetch(client)

    assert len(context["files"]) == 101
    assert len(context["comments"]) == 101
    assert context["reviews"] == {"changes_requested": True}
    assert len(context["checks"]) == 101
    assert context["checks"]["last"] == "success"

    for prefix in (FILES_PATH, COMMENTS_PATH, REVIEWS_PATH, CHECK_RUNS_PATH):
        pages = [call.params["page"] for call in client.calls if call.path == prefix]
        assert pages == [1, 2], prefix
        assert all(call.params["per_page"] == 100 for call in client.calls if call.path == prefix)


def test_raw_diff_is_fetched_with_its_own_accept_header_and_capped():
    client = FakeClient(diff="a" * 500_000)

    context = fetch(client)

    assert len(context["diff"]) == 400 * 1024
    diff_calls = [call for call in client.calls if call.accept == DIFF_ACCEPT]
    assert len(diff_calls) == 1
    assert diff_calls[0].path == PR_PATH


def test_base_files_are_capped_at_twenty_files():
    files = [api_file(f"scripts/file-{index}.py") for index in range(25)]
    contents = {f"scripts/file-{index}.py": contents_response("x") for index in range(25)}
    client = FakeClient(file_pages=(files,), contents=contents)

    context = fetch(client)

    assert len(context["base_files"]) == 20
    assert list(context["base_files"]) == [f"scripts/file-{index}.py" for index in range(20)]
    assert len(client.contents_calls()) == 20


def test_base_files_stop_at_the_byte_budget():
    limit = 200 * 1024
    client = FakeClient(
        file_pages=(
            [
                api_file("scripts/big.py"),
                api_file("scripts/one-byte.py"),
            ],
        ),
        contents={
            "scripts/big.py": contents_response("a" * limit),
            "scripts/one-byte.py": contents_response("b"),
        },
    )

    context = fetch(client)

    assert context["base_files"] == {"scripts/big.py": "a" * limit}
    assert len(client.contents_calls()) == 2


def test_a_single_file_over_the_byte_budget_is_skipped():
    client = FakeClient(
        file_pages=([api_file("scripts/huge.py")],),
        contents={"scripts/huge.py": contents_response("a" * (200 * 1024 + 1))},
    )

    assert fetch(client)["base_files"] == {}


def test_removed_binary_and_added_files_are_not_fetched():
    client = FakeClient(
        file_pages=(
            [
                api_file("docs/removed.md", status="removed", deletions=3),
                binary_api_file("docs/logo.png", additions=2),
                api_file("docs/added.md", status="added", patch="@@ -0,0 +1 @@\n"),
                api_file("docs/kept.md"),
            ],
        ),
        contents={"docs/kept.md": contents_response("kept")},
    )

    context = fetch(client)

    assert context["base_files"] == {"docs/kept.md": "kept"}
    assert [call.path for call in client.contents_calls()] == [f"{CONTENTS_PREFIX}docs/kept.md"]


def test_renamed_files_read_the_previous_path_at_the_base_commit():
    client = FakeClient(
        file_pages=([api_file("scripts/new.py", status="renamed", previous="scripts/old.py")],),
        contents={"scripts/old.py": contents_response("old")},
    )

    context = fetch(client)

    assert context["base_files"] == {"scripts/new.py": "old"}
    (call,) = client.contents_calls()
    assert call.path == f"{CONTENTS_PREFIX}scripts/old.py"
    assert call.params == {"ref": "base-sha"}


@pytest.mark.parametrize(
    "payload",
    [
        contents_response("x", encoding="none"),
        contents_response(b"\xff\xfe", type_="file"),
        json_response({"type": "submodule", "encoding": "base64", "size": 1, "content": "eA=="}),
        json_response({"type": "file", "encoding": "base64", "size": 300_000, "content": "eA=="}),
        json_response({"type": "file", "encoding": "base64", "size": 1}),
    ],
)
def test_unusable_base_content_is_skipped(payload):
    client = FakeClient(
        file_pages=([api_file("scripts/odd.py")],),
        contents={"scripts/odd.py": payload},
    )

    assert fetch(client)["base_files"] == {}


def test_base_file_404_is_skipped_but_other_fetch_errors_propagate():
    missing = FakeClient(
        file_pages=([api_file("scripts/missing.py")],),
        errors={f"{CONTENTS_PREFIX}scripts/missing.py": pr_github.FetchError("404", status=404)},
    )
    assert fetch(missing)["base_files"] == {}

    broken = FakeClient(
        file_pages=([api_file("scripts/broken.py")],),
        errors={f"{CONTENTS_PREFIX}scripts/broken.py": pr_github.FetchError("500", status=500)},
    )
    with pytest.raises(pr_github.FetchError):
        fetch(broken)


@pytest.mark.parametrize(
    ("entry", "binary"),
    [
        (api_file("a.py", patch="@@ -1 +1 @@\n", additions=1), False),
        (binary_api_file("b.png", additions=3), True),
        (binary_api_file("c.txt", additions=0, deletions=0), False),
        (api_file("d.py", patch="", additions=1), False),
        (binary_api_file("e.bin", additions=0, deletions=2), True),
    ],
)
def test_binary_detection_fails_safe_when_the_patch_is_missing(entry, binary):
    client = FakeClient(file_pages=([entry],), contents={entry["filename"]: contents_response("")})

    (file,) = fetch(client)["files"]

    assert file["binary"] is binary


def test_missing_patch_with_zero_changes_is_not_binary():
    entry = {
        "filename": "scripts/mode-only.sh",
        "status": "modified",
        "additions": 0,
        "deletions": 0,
    }
    client = FakeClient(file_pages=([entry],))

    (file,) = fetch(client)["files"]

    assert file["binary"] is False


def test_check_run_without_a_conclusion_maps_to_its_status():
    client = FakeClient(
        check_run_pages=(
            [
                {"name": "queued", "conclusion": None, "status": "queued"},
                {"name": "done", "conclusion": "success", "status": "completed"},
                {"conclusion": "success", "status": "completed"},
            ],
        ),
    )

    context = fetch(client)

    assert context["checks"] == {"queued": "queued", "done": "success"}


@pytest.mark.parametrize(
    ("reviews", "changes_requested"),
    [
        ([], False),
        ([{"user": {"login": "a"}, "state": "APPROVED"}], False),
        ([{"user": {"login": "a"}, "state": "CHANGES_REQUESTED"}], True),
        (
            [
                {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "a"}, "state": "APPROVED"},
            ],
            False,
        ),
        (
            [
                {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "b"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "c"}, "state": "COMMENTED"},
            ],
            True,
        ),
        (
            [
                {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "a"}, "state": "PENDING"},
            ],
            True,
        ),
        (
            [
                {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "a"}, "state": "DISMISSED"},
            ],
            False,
        ),
    ],
)
def test_reviews_use_the_latest_submitted_state_per_user(reviews, changes_requested):
    client = FakeClient(review_pages=(reviews,))

    assert fetch(client)["reviews"] == {"changes_requested": changes_requested}


@pytest.mark.parametrize(
    ("head_repo", "fork"),
    [
        ({"full_name": REPO}, False),
        ({"full_name": "someone/agents"}, True),
        (None, True),
    ],
)
def test_fork_is_detected_from_the_head_repository(head_repo, fork):
    client = FakeClient(pull_request(head={"sha": "abc123", "ref": "fix/x", "repo": head_repo}))

    assert fetch(client)["fork"] is fork


def test_missing_token_without_an_injected_client_raises_before_any_request(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(pr_github.MissingTokenError):
        pr_github.fetch_context(REPO, NUMBER)

    with pytest.raises(pr_github.MissingTokenError):
        pr_github.fetch_context(REPO, NUMBER, token="")


class FakeHTTPResponse:
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None) -> None:
        self._body = body
        self.status = status
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def test_github_client_sends_auth_and_parses_json():
    captured = {}

    def opener(request, timeout=None):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeHTTPResponse(b'{"ok": true}')

    client = pr_github.GitHubClient("s3cret-token", opener=opener)

    response = client.get("/repos/o/r", params={"page": 2})

    assert response.json() == {"ok": True}
    request = captured["request"]
    assert request.full_url == "https://api.github.com/repos/o/r?page=2"
    assert request.get_header("Authorization") == "Bearer s3cret-token"
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert captured["timeout"] == 30


@pytest.mark.parametrize(
    ("method", "payload"),
    [
        ("post", {"a": 1}),
        ("patch", {"a": 1}),
        ("delete", None),
    ],
)
def test_client_write_helpers_send_the_named_method(method, payload):
    captured = {}

    def opener(request, timeout=None):
        captured["request"] = request
        return FakeHTTPResponse(b"{}")

    client = pr_github.GitHubClient("token", opener=opener)

    getattr(client, method)("/repos/o/r/thing", payload)

    request = captured["request"]
    assert request.get_method() == method.upper()
    if payload is None:
        assert request.data is None
    else:
        assert json.loads(request.data) == payload


def test_graphql_posts_the_query_and_returns_the_response_body():
    captured = {}

    def opener(request, timeout=None):
        captured["request"] = request
        return FakeHTTPResponse(b'{"data": {"viewer": {"login": "me"}}}')

    client = pr_github.GitHubClient("token", opener=opener)

    result = client.graphql("query { viewer { login } }", {"n": 1})

    assert result == {"data": {"viewer": {"login": "me"}}}
    request = captured["request"]
    assert request.full_url == "https://api.github.com/graphql"
    assert json.loads(request.data) == {
        "query": "query { viewer { login } }",
        "variables": {"n": 1},
    }


def test_http_error_becomes_fetch_error_without_leaking_the_token():
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            Message(),
            io.BytesIO(b'{"message": "nope"}'),
        )

    client = pr_github.GitHubClient("s3cret-token", opener=opener)

    with pytest.raises(pr_github.FetchError) as info:
        client.get("/repos/o/r")

    assert info.value.status == 403
    assert "403" in str(info.value)
    assert "s3cret-token" not in str(info.value)


def test_network_error_becomes_fetch_error():
    def opener(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    client = pr_github.GitHubClient("token", opener=opener)

    with pytest.raises(pr_github.FetchError) as info:
        client.get("/repos/o/r")

    assert "connection refused" in str(info.value)


def test_cli_writes_the_context_and_exits_zero(tmp_path, monkeypatch, capsys):
    context = {"schema_version": 1, "number": NUMBER, "files": []}
    monkeypatch.setattr(pr_github, "fetch_context", lambda repo, number, token=None: context)
    output = tmp_path / "context.json"

    code = pr_github.main(["--pr", str(NUMBER), "--repo", REPO, "--output", str(output)])

    assert code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == context
    assert capsys.readouterr().out == ""


def test_cli_prints_the_context_to_stdout(monkeypatch, capsys):
    context = {"schema_version": 1, "number": NUMBER, "files": []}
    monkeypatch.setattr(pr_github, "fetch_context", lambda repo, number, token=None: context)

    code = pr_github.main(["--pr", str(NUMBER), "--repo", REPO])

    assert code == 0
    assert json.loads(capsys.readouterr().out) == context


def test_cli_maps_missing_token_to_exit_five(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    code = pr_github.main(["--pr", str(NUMBER), "--repo", REPO])

    assert code == 5


def test_cli_maps_fetch_failure_to_exit_four(monkeypatch):
    def fail(repo, number, token=None):
        raise pr_github.FetchError("boom")

    monkeypatch.setattr(pr_github, "fetch_context", fail)

    assert pr_github.main(["--pr", str(NUMBER), "--repo", REPO]) == 4


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--pr", str(NUMBER)],
        ["--repo", REPO],
        ["--pr", "zero", "--repo", REPO],
        ["--pr", "0", "--repo", REPO],
        ["--pr", str(NUMBER), "--repo", "no-slash"],
        ["--pr", str(NUMBER), "--repo", REPO, "--unknown"],
    ],
)
def test_cli_usage_errors_exit_two(argv):
    assert pr_github.main(argv) == 2


def test_cli_output_write_failure_exits_three(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pr_github,
        "fetch_context",
        lambda repo, number, token=None: {"schema_version": 1, "files": []},
    )

    assert pr_github.main(["--pr", str(NUMBER), "--repo", REPO, "--output", str(tmp_path)]) == 3


def test_cli_help_is_short_and_documents_exit_codes():
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and script path, no shell
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert len(result.stdout.splitlines()) < 25
    assert "usage:" in result.stdout
    assert "exit:" in result.stdout
    assert result.stderr == ""
