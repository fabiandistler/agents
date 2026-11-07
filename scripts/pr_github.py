#!/usr/bin/env python3
"""Fetch one pull request through the GitHub REST API as context JSON.

This module knows the context shape: which REST endpoints feed it and how
their payloads map onto it; ``pr_github_client.py`` carries the transport. The
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
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from pr_github_client import (
    REPO_PATTERN,
    FetchError,
    GitHubClient,
    MissingTokenError,
    ReadClient,
)

SCHEMA_VERSION = 1
DIFF_ACCEPT = "application/vnd.github.v3.diff"
PER_PAGE = 100
DIFF_LIMIT = 400 * 1024
BASE_FILE_LIMIT = 20
BASE_BYTES_LIMIT = 200 * 1024
BASE_PATH_LIMIT = 5000
STATUS_ALIASES = {"copied": "added", "changed": "modified", "unchanged": "modified"}

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


def _line_count(entry: dict, field: str) -> int:
    value = entry.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FetchError(f"GitHub API returned a changed file with a malformed {field!r} count")
    return value


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
    additions = _line_count(entry, "additions")
    deletions = _line_count(entry, "deletions")
    status = entry.get("status")
    if not isinstance(status, str) or not status:
        raise FetchError("GitHub API returned a changed file without a 'status'")
    status = STATUS_ALIASES.get(status, status)
    renamed_from = entry.get("previous_filename")
    return {
        "path": path,
        "status": status,
        "additions": additions,
        "deletions": deletions,
        # GitHub omits the patch for binary content and reports it as 0/0, so a
        # missing patch counts as binary unless the file is only renamed.
        "binary": entry.get("patch") is None
        and not (status == "renamed" and additions + deletions == 0),
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


def _diff(client: ReadClient, pr_path: str) -> tuple[str, str]:
    """Return the capped diff and its status: complete, truncated or unavailable.

    GitHub refuses a too-large diff (HTTP 406, ``too_large``); any failed
    request yields ``unavailable``, which the risk policy rates high.
    """
    try:
        response = client.get(pr_path, accept=DIFF_ACCEPT)
    except FetchError:
        return "", "unavailable"
    if len(response.body) > DIFF_LIMIT:
        return response.body[:DIFF_LIMIT].decode("utf-8", errors="replace"), "truncated"
    return response.body.decode("utf-8", errors="replace"), "complete"


def _base_paths(client: ReadClient, repo: str, base_sha: str) -> tuple[list[str], bool]:
    """Return the base tree's sorted file paths and whether the list is incomplete."""
    path = f"/repos/{repo}/git/trees/{urllib.parse.quote(base_sha, safe='')}"
    payload = _get_json(client, path, params={"recursive": "1"})
    entries = payload.get("tree") if isinstance(payload, dict) else None
    truncated = payload.get("truncated") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not isinstance(truncated, bool):
        raise FetchError(f"GitHub API returned an unexpected payload for {path}")
    paths: list[str] = []
    for entry in entries:
        entry_path = entry.get("path") if isinstance(entry, dict) else None
        entry_type = entry.get("type") if isinstance(entry, dict) else None
        if not isinstance(entry_path, str) or not entry_path or not isinstance(entry_type, str):
            raise FetchError(f"GitHub API returned a malformed tree entry for {path}")
        if entry_type == "blob":
            paths.append(entry_path)
    paths.sort()
    if len(paths) > BASE_PATH_LIMIT:
        return paths[:BASE_PATH_LIMIT], True
    return paths, truncated


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

    diff, diff_status = _diff(client, pr_path)

    base_sha = base.get("sha")
    if not isinstance(base_sha, str) or not base_sha:
        raise FetchError(f"GitHub API returned no base commit for {pr_path}")
    base_files = _base_files(client, repo, files, base_sha)
    base_paths, base_paths_truncated = _base_paths(client, repo, base_sha)

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
        "state": pull.get("state"),
        "head_sha": head_sha,
        "head_ref": head.get("ref") if isinstance(head.get("ref"), str) else "",
        "base_ref": base.get("ref") if isinstance(base.get("ref"), str) else "",
        "default_branch": default_branch if isinstance(default_branch, str) else "",
        "draft": bool(pull.get("draft")),
        "fork": fork,
        # The GraphQL id the auto-merge mutations take.
        "node_id": pull.get("node_id") if isinstance(pull.get("node_id"), str) else "",
        # null while GitHub is still computing it; the planner treats that as unknown.
        "mergeable": pull.get("mergeable") if isinstance(pull.get("mergeable"), bool) else None,
        "auto_merge_active": pull.get("auto_merge") is not None,
        "labels": labels,
        "files": files,
        "diff": diff,
        "diff_status": diff_status,
        "base_files": base_files,
        "base_paths": base_paths,
        "base_paths_truncated": base_paths_truncated,
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
