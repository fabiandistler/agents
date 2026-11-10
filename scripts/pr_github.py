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
import os
import sys
import urllib.parse
from typing import Any, TypeGuard

import pr_cli
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

USAGE = f"""usage: pr_github.py --pr N --repo OWNER/REPO [--output FILE]

Fetch a pull request through the GitHub REST API and write the context JSON
consumed by the risk policy and review pipeline. Reads GITHUB_TOKEN. Stdout
gets a short JSON summary; the full context (diff included) only goes to FILE.

  --pr N          pull request number
  --repo O/R      repository as OWNER/REPO
  --output FILE   write the full context JSON to FILE
  -h, --help      show this message

examples:
  python3 scripts/pr_github.py --pr 42 --repo fabiandistler/agents --output context.json
  GITHUB_TOKEN=... python3 scripts/pr_github.py --pr 42 --repo o/r

{pr_cli.exit_help(0, 2, 4, 5, 6)}
"""


def is_line_count(value: object) -> TypeGuard[int]:
    """Whether ``value`` is a usable additions or deletions count of a changed file."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _line_count(entry: dict, field: str) -> int:
    value = entry.get(field)
    if not is_line_count(value):
        raise FetchError(f"GitHub API returned a changed file with a malformed {field!r} count")
    return value


def get_json(client: ReadClient, path: str, params: dict[str, object] | None = None) -> Any:
    """GET ``path`` and decode the JSON body; ``FetchError`` on anything else."""
    response = client.get(path, params=params)
    try:
        return response.json()
    except ValueError as error:
        raise FetchError(f"GitHub API returned invalid JSON for {path}") from error


def paginate(client: ReadClient, path: str) -> list[dict]:
    """GET every page of the list at ``path``; each item must be a JSON object."""
    items: list[dict] = []
    page = 1
    while True:
        page_items = get_json(client, path, params={"per_page": PER_PAGE, "page": page})
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
    user = entry.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    # The author tells the bot's sticky comment apart from a human one quoting its marker.
    return {
        "id": entry.get("id"),
        "body": body if isinstance(body, str) else "",
        "author": login if isinstance(login, str) else "",
    }


# The review states that set or clear a reviewer's change request. A COMMENTED
# review leaves it in place, and a PENDING one is not submitted yet.
DECIDING_REVIEW_STATES = frozenset({"APPROVED", "CHANGES_REQUESTED", "DISMISSED"})


def _review_state(reviews: list[dict]) -> dict[str, bool]:
    latest: dict[str, str] = {}
    for review in reviews:
        state = review.get("state")
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if state not in DECIDING_REVIEW_STATES or not isinstance(login, str) or not login:
            continue
        latest[login] = state
    return {"changes_requested": any(state == "CHANGES_REQUESTED" for state in latest.values())}


def _labels(pull: dict, pr_path: str) -> list[str]:
    """The label names; an unreadable list fails, since it could hide do-not-merge."""
    raw = pull.get("labels")
    if not isinstance(raw, list):
        raise FetchError(f"GitHub API returned no 'labels' list for {pr_path}")
    names: list[str] = []
    for label in raw:
        name = label.get("name") if isinstance(label, dict) else None
        if not isinstance(name, str) or not name:
            raise FetchError(f"GitHub API returned a malformed entry in 'labels' for {pr_path}")
        names.append(name)
    return names


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
    payload = get_json(client, path, params={"recursive": "1"})
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
    pull = get_json(client, pr_path)
    if not isinstance(pull, dict):
        raise FetchError(f"GitHub API returned an unexpected payload for {pr_path}")

    files = [_map_file(entry) for entry in paginate(client, f"{pr_path}/files")]
    comments = [
        _comment(entry) for entry in paginate(client, f"/repos/{repo}/issues/{number}/comments")
    ]
    reviews = _review_state(paginate(client, f"{pr_path}/reviews"))

    head_value = pull.get("head")
    head = head_value if isinstance(head_value, dict) else {}
    base_value = pull.get("base")
    base = base_value if isinstance(base_value, dict) else {}
    head_sha_value = head.get("sha")
    head_sha = head_sha_value if isinstance(head_sha_value, str) else ""

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
    labels = _labels(pull, pr_path)
    # The GraphQL id the auto-merge mutations take; without it no disable works.
    node_id = pull.get("node_id")
    if not isinstance(node_id, str) or not node_id:
        raise FetchError(f"GitHub API returned no 'node_id' for {pr_path}")

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
        "node_id": node_id,
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
        "reviews": reviews,
    }


def _summary(context: dict, output: str | None) -> dict:
    """The bounded stdout view of a context: identity, flags and sizes, no diff."""
    return {
        "repo": context["repo"],
        "number": context["number"],
        "head_sha": context["head_sha"],
        "draft": context["draft"],
        "fork": context["fork"],
        "files": len(context["files"]),
        "diff_status": context["diff_status"],
        "diff_bytes": len(context["diff"].encode("utf-8")),
        "base_files": len(context["base_files"]),
        "base_paths": len(context["base_paths"]),
        "comments": len(context["comments"]),
        "output": output,
    }


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = pr_cli.parse_flags(arguments, ("--pr", "--repo", "--output"))
        if options is not None:
            pr_cli.require_pull_request(options)
    except pr_cli.UsageError as error:
        return pr_cli.usage_failure("pr_github.py", USAGE, error)
    if options is None:
        print(USAGE, end="")
        return pr_cli.EXIT_OK

    token = os.environ.get("GITHUB_TOKEN") or None
    try:
        context = fetch_context(str(options["repo"]), int(str(options["pr"])), token=token)
    except MissingTokenError as error:
        print(f"pr_github.py: {error}", file=sys.stderr)
        return pr_cli.EXIT_MISSING_TOKEN
    except FetchError as error:
        print(f"pr_github.py: fetch failed: {error}", file=sys.stderr)
        return pr_cli.EXIT_FETCH_FAILED
    output = options["output"] if isinstance(options["output"], str) else None
    if output is not None and not pr_cli.write_json_file(
        "pr_github.py", "--output", output, context
    ):
        return pr_cli.EXIT_OUTPUT_FAILED
    pr_cli.print_json(_summary(context, output))
    return pr_cli.EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
