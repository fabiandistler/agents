#!/usr/bin/env python3
"""Fetch one pull request through the GitHub REST API as context JSON.

This is the only module in the PR review pipeline that talks to GitHub. The
context it emits is the fixed shape documented in the feature contract and
consumed by ``pr_risk.py``, ``pr_review.py`` and ``pr_publish.py``.

Live use reads ``GITHUB_TOKEN``; with an injected ``client`` no token is
needed, which is how the tests run without a network.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

SCHEMA_VERSION = 1
DEFAULT_BASE_URL = "https://api.github.com"
DIFF_ACCEPT = "application/vnd.github.v3.diff"
JSON_ACCEPT = "application/vnd.github+json"
USER_AGENT = "agents-pr-review"
API_VERSION = "2022-11-28"
PER_PAGE = 100
DIFF_LIMIT = 400 * 1024
BASE_FILE_LIMIT = 20
BASE_BYTES_LIMIT = 200 * 1024
STATUS_ALIASES = {"copied": "added", "changed": "modified", "unchanged": "modified"}

REPO_PATTERN = re.compile(r"^[^/\s]+/[^/\s]+$")

USAGE = """usage: pr_github.py --pr N --repo OWNER/REPO [--output FILE]

Fetch a pull request through the GitHub REST API and emit the context JSON
consumed by the risk policy and review pipeline. Reads GITHUB_TOKEN; without
--output the JSON goes to stdout.

  --pr N          pull request number
  --repo O/R      repository as OWNER/REPO
  --output FILE   write the context JSON to FILE instead of stdout
  -h, --help      show this message

examples:
  python3 scripts/pr_github.py --pr 42 --repo fabiandistler/agents --output context.json
  GITHUB_TOKEN=... python3 scripts/pr_github.py --pr 42 --repo o/r

exit: 0 context written | 2 usage | 3 output write failed |
      4 fetch failed | 5 missing GITHUB_TOKEN
"""


class FetchError(RuntimeError):
    """A GitHub request failed or returned an unusable payload."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class MissingTokenError(FetchError):
    """No token was supplied and no client was injected."""


@dataclass(frozen=True)
class Response:
    """The parts of an HTTP response this pipeline reads."""

    status: int
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class ReadClient(Protocol):
    """The read surface ``fetch_context`` needs; ``GitHubClient`` and fakes implement it."""

    def get(
        self,
        path: str,
        params: dict[str, object] | None = None,
        accept: str | None = None,
    ) -> Response: ...


class GitHubClient:
    """A small stdlib REST client with injectable transport for tests."""

    def __init__(
        self,
        token: str | None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener: Callable[..., Any] = opener or urllib.request.urlopen

    def get(
        self,
        path: str,
        params: dict[str, object] | None = None,
        accept: str | None = None,
    ) -> Response:
        return self._request("GET", path, params=params, accept=accept)

    def post(self, path: str, payload: dict[str, object] | None = None) -> Response:
        return self._request("POST", path, payload=payload)

    def patch(self, path: str, payload: dict[str, object] | None = None) -> Response:
        return self._request("PATCH", path, payload=payload)

    def delete(self, path: str, payload: dict[str, object] | None = None) -> Response:
        return self._request("DELETE", path, payload=payload)

    def graphql(self, query: str, variables: dict[str, object] | None = None) -> Any:
        response = self.post("/graphql", {"query": query, "variables": variables or {}})
        return response.json()

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, object] | None = None,
        accept: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> Response:
        url = self.base_url + path
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        headers = {
            "Accept": accept or JSON_ACCEPT,
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        # base_url is fixed; repo and number are validated before this call.
        request = urllib.request.Request(  # noqa: S310
            url, data=data, headers=headers, method=method
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                return Response(
                    status=response.status,
                    body=response.read(),
                    headers=dict(response.headers),
                )
        except urllib.error.HTTPError as error:
            raise FetchError(
                f"GitHub API returned {error.code} for {path}", status=error.code
            ) from error
        except urllib.error.URLError as error:
            raise FetchError(f"GitHub API request failed for {path}: {error.reason}") from error


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


def _get_json(client: ReadClient, path: str, params: dict[str, object] | None = None) -> Any:
    response = client.get(path, params=params)
    try:
        return response.json()
    except ValueError as error:
        raise FetchError(f"GitHub API returned invalid JSON for {path}") from error


def _paginate(client: ReadClient, path: str, key: str | None = None) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        payload = _get_json(client, path, params={"per_page": PER_PAGE, "page": page})
        if key is not None:
            if not isinstance(payload, dict):
                raise FetchError(f"GitHub API returned an unexpected payload for {path}")
            page_items = payload.get(key)
        else:
            page_items = payload
        if not isinstance(page_items, list):
            raise FetchError(f"GitHub API returned an unexpected payload for {path}")
        for item in page_items:
            if not isinstance(item, dict):
                raise FetchError(f"GitHub API returned a non-object item for {path}")
            items.append(item)
        if len(page_items) < PER_PAGE:
            return items
        page += 1


def _map_file(entry: dict) -> dict:
    path = entry.get("filename")
    if not isinstance(path, str) or not path:
        raise FetchError("GitHub API returned a changed file without a filename")
    additions = _count(entry.get("additions"))
    deletions = _count(entry.get("deletions"))
    status = entry.get("status")
    if not isinstance(status, str) or not status:
        status = "modified"
    status = STATUS_ALIASES.get(status, status)
    renamed_from = entry.get("previous_filename")
    return {
        "path": path,
        "status": status,
        "additions": additions,
        "deletions": deletions,
        "binary": entry.get("patch") is None and additions + deletions > 0,
        "renamed_from": renamed_from if isinstance(renamed_from, str) and renamed_from else None,
    }


def _comment(entry: dict) -> dict:
    body = entry.get("body")
    return {"id": entry.get("id"), "body": body if isinstance(body, str) else ""}


def _check_map(runs: list[dict]) -> dict[str, str]:
    checks: dict[str, str] = {}
    for run in runs:
        name = run.get("name")
        if not isinstance(name, str) or not name:
            continue
        conclusion = run.get("conclusion")
        status = run.get("status")
        if isinstance(conclusion, str):
            checks[name] = conclusion
        elif isinstance(status, str):
            checks[name] = status
        else:
            checks[name] = "unknown"
    return checks


def _review_state(reviews: list[dict]) -> dict[str, bool]:
    latest: dict[str, str] = {}
    for review in reviews:
        state = review.get("state")
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if (
            not isinstance(state, str)
            or state == "PENDING"
            or not isinstance(login, str)
            or not login
        ):
            continue
        latest[login] = state
    return {"changes_requested": any(state == "CHANGES_REQUESTED" for state in latest.values())}


def _base_files(
    client: ReadClient,
    repo: str,
    files: list[dict],
    base_sha: str,
) -> dict[str, str]:
    base_files: dict[str, str] = {}
    total_bytes = 0
    for entry in files:
        if len(base_files) >= BASE_FILE_LIMIT:
            break
        if entry["status"] not in {"modified", "renamed"} or entry["binary"]:
            continue
        source_path = entry["renamed_from"] or entry["path"]
        quoted = urllib.parse.quote(source_path, safe="/")
        path = f"/repos/{repo}/contents/{quoted}"
        try:
            response = client.get(path, params={"ref": base_sha})
        except FetchError as error:
            if error.status == 404:
                continue
            raise
        try:
            payload = response.json()
        except ValueError as error:
            raise FetchError(f"GitHub API returned invalid JSON for {path}") from error
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "file" or payload.get("encoding") != "base64":
            continue
        content = payload.get("content")
        if not isinstance(content, str):
            continue
        size = payload.get("size")
        size_is_known = isinstance(size, int) and not isinstance(size, bool)
        if size_is_known and size > BASE_BYTES_LIMIT - total_bytes:
            continue
        try:
            content_bytes = base64.b64decode("".join(content.split()), validate=True)
        except (binascii.Error, ValueError):
            continue
        if len(content_bytes) > BASE_BYTES_LIMIT - total_bytes:
            continue
        if b"\x00" in content_bytes:
            continue
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            continue
        base_files[entry["path"]] = text
        total_bytes += len(content_bytes)
    return base_files


def fetch_context(
    repo: str,
    number: int,
    token: str | None = None,
    client: ReadClient | None = None,
) -> dict:
    """Fetch the full context JSON for one pull request."""
    if client is None:
        if not isinstance(token, str) or not token:
            raise MissingTokenError("GITHUB_TOKEN is not set and no client was injected")
        client = GitHubClient(token)
    if not isinstance(repo, str) or not REPO_PATTERN.fullmatch(repo):
        raise ValueError("repo must be OWNER/REPO")
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        raise ValueError("pull request number must be a positive integer")

    pr_path = f"/repos/{repo}/pulls/{number}"
    pull = _get_json(client, pr_path)
    if not isinstance(pull, dict):
        raise FetchError(f"GitHub API returned an unexpected payload for {pr_path}")

    files = [_map_file(entry) for entry in _paginate(client, f"{pr_path}/files")]
    comments = [
        _comment(entry) for entry in _paginate(client, f"/repos/{repo}/issues/{number}/comments")
    ]
    reviews = _review_state(_paginate(client, f"{pr_path}/reviews"))

    head_value = pull.get("head")
    head = head_value if isinstance(head_value, dict) else {}
    base_value = pull.get("base")
    base = base_value if isinstance(base_value, dict) else {}
    head_sha_value = head.get("sha")
    head_sha = head_sha_value if isinstance(head_sha_value, str) else ""
    checks: dict[str, str] = {}
    if head_sha:
        check_runs = _paginate(
            client,
            f"/repos/{repo}/commits/{head_sha}/check-runs",
            key="check_runs",
        )
        checks = _check_map(check_runs)

    diff_response = client.get(pr_path, accept=DIFF_ACCEPT)
    diff = diff_response.body[:DIFF_LIMIT].decode("utf-8", errors="replace")

    base_sha_value = base.get("sha")
    base_sha = base_sha_value if isinstance(base_sha_value, str) else ""
    base_files = _base_files(client, repo, files, base_sha) if base_sha else {}

    head_repo_value = head.get("repo")
    head_repo = head_repo_value if isinstance(head_repo_value, dict) else {}
    head_full_name = head_repo.get("full_name")
    fork = not isinstance(head_full_name, str) or head_full_name.lower() != repo.lower()

    base_repo_value = base.get("repo")
    base_repo = base_repo_value if isinstance(base_repo_value, dict) else {}
    labels: list[str] = []
    for label in pull.get("labels") or []:
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            labels.append(label["name"])
        elif isinstance(label, str):
            labels.append(label)

    user_value = pull.get("user")
    user = user_value if isinstance(user_value, dict) else {}

    default_branch = base_repo.get("default_branch")

    return {
        "schema_version": SCHEMA_VERSION,
        "repo": repo,
        "number": number,
        "title": pull.get("title") if isinstance(pull.get("title"), str) else "",
        "body": pull.get("body") if isinstance(pull.get("body"), str) else "",
        "author": user.get("login") if isinstance(user.get("login"), str) else "",
        "head_sha": head_sha,
        "head_ref": head.get("ref") if isinstance(head.get("ref"), str) else "",
        "base_ref": base.get("ref") if isinstance(base.get("ref"), str) else "",
        "default_branch": default_branch if isinstance(default_branch, str) else "",
        "draft": bool(pull.get("draft")),
        "fork": fork,
        "mergeable": pull.get("mergeable") is True,
        "labels": labels,
        "files": files,
        "diff": diff,
        "base_files": base_files,
        "comments": comments,
        "checks": checks,
        "reviews": reviews,
    }


class UsageError(Exception):
    """The command line was not usable."""


def _parse_arguments(argv: list[str]) -> dict:
    options: dict[str, object] = {"pr": None, "repo": None, "output": None}
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-h", "--help"):
            return {"help": True}
        name, separator, inline = argument.partition("=")
        if name not in {"--pr", "--repo", "--output"}:
            raise UsageError(f"unknown argument: {argument}")
        if separator:
            value = inline
            index += 1
        else:
            if index + 1 >= len(argv):
                raise UsageError(f"{name} needs a value")
            value = argv[index + 1]
            index += 2
        if not value:
            raise UsageError(f"{name} needs a value")
        options[name[2:]] = value

    if options["pr"] is None or options["repo"] is None:
        raise UsageError("--pr and --repo are required")
    try:
        number = int(str(options["pr"]))
    except ValueError as error:
        raise UsageError("--pr must be a positive integer") from error
    if number <= 0:
        raise UsageError("--pr must be a positive integer")
    options["pr"] = number
    if not REPO_PATTERN.fullmatch(str(options["repo"])):
        raise UsageError("--repo must be OWNER/REPO")
    return options


def _emit(context: dict, output: str | None) -> int:
    text = json.dumps(context, indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
        return 0
    try:
        Path(output).write_text(text, encoding="utf-8")
    except OSError as error:
        print(f"pr_github.py: cannot write --output: {error}", file=sys.stderr)
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = _parse_arguments(arguments)
    except UsageError as error:
        print(f"pr_github.py: {error}", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        return 2
    if options.get("help"):
        print(USAGE, end="")
        return 0

    token = os.environ.get("GITHUB_TOKEN") or None
    try:
        context = fetch_context(str(options["repo"]), int(str(options["pr"])), token=token)
    except MissingTokenError as error:
        print(f"pr_github.py: {error}", file=sys.stderr)
        return 5
    except FetchError as error:
        print(f"pr_github.py: fetch failed: {error}", file=sys.stderr)
        return 4
    return _emit(context, options["output"] if isinstance(options["output"], str) else None)


if __name__ == "__main__":
    raise SystemExit(main())
