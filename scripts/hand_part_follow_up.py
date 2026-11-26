"""Track sections of a merged implementer PR that a maintainer must apply by hand."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from factory_handoff import (
    APP_LOGIN,
    HAND_PART,
    HAND_PART_HEADING,
    READY_FOR_HUMAN,
    WORKFLOW_BOT_LOGIN,
    format_marker,
    read_markers,
)
from pr_cli import read_json_object, repo_argument
from pr_github import comment_entry
from pr_github_client import FetchError, GitHubClient, ReadClient, Response, paginate
from rework_policy import HEAD_SHA, linked_issue

_HEADING = re.compile(r"^#{1,2}(?:[ \t]+|$)")
_FENCE = re.compile(r"^ {0,3}((?:[-+*]|[0-9]{1,9}[.)])[ \t]+)?(`{3,}|~{3,})(.*)$")
_HTML_COMMENT = re.compile(r"<!--.*?(?:-->|$)")


class FollowUpClient(ReadClient, Protocol):
    def post(self, path: str, payload: dict[str, object]) -> Response: ...


@dataclass(frozen=True)
class FollowUp:
    title: str
    body: str
    marker: str


@dataclass(frozen=True)
class Plan:
    source_issue: int
    follow_ups: tuple[FollowUp, ...]


def plan_follow_ups(event: dict, repo: str) -> Plan | None:
    """Plan a follow-up for each hand-applied section in a qualifying PR event."""
    pull = event.get("pull_request")
    if event.get("action") != "closed" or not isinstance(pull, dict):
        return None
    if pull.get("merged") is not True:
        return None
    user = pull.get("user") or {}
    head_repo = (pull.get("head") or {}).get("repo") or {}
    if user.get("login") != APP_LOGIN or user.get("type") != "Bot":
        return None
    if head_repo.get("full_name", "").lower() != repo.lower():
        return None
    source_issue = linked_issue(pull, repo)
    if source_issue is None:
        return None

    pr = pull.get("number")
    sha = pull.get("merge_commit_sha")
    if type(pr) is not int or pr < 1 or not isinstance(sha, str) or not HEAD_SHA.fullmatch(sha):
        raise ValueError("Merged pull request requires a valid number and merge commit SHA")
    follow_ups = tuple(
        _follow_up(pr, source_issue, sha, index, title, text)
        for index, (title, text) in enumerate(_sections(pull.get("body") or ""), start=1)
    )
    return Plan(source_issue, follow_ups) if follow_ups else None


def publish_follow_ups(client: FollowUpClient, repo: str, plan: Plan) -> list[int]:
    """Create missing issues and repair links left unwritten by an interrupted run."""
    issues_path = f"/repos/{repo}/issues"
    comments_path = f"{issues_path}/{plan.source_issue}/comments"
    # Search across states and labels. A maintainer may have closed or relabeled the issue.
    previous_issues = paginate(client, issues_path, {"state": "all", "creator": WORKFLOW_BOT_LOGIN})
    issue_numbers = {
        marker: _issue_number(entry)
        for entry, marker in _marked_entries(previous_issues)
        if "pull_request" not in entry
    }
    linked = {marker for _, marker in _marked_entries(paginate(client, comments_path))}
    created = []
    for follow_up in plan.follow_ups:
        number = issue_numbers.get(follow_up.marker)
        if number is None:
            response = client.post(
                issues_path,
                {"title": follow_up.title, "body": follow_up.body, "labels": [READY_FOR_HUMAN]},
            )
            try:
                number = _issue_number(response.json())
            except ValueError as error:
                raise FetchError("GitHub returned an invalid issue creation response") from error
            created.append(number)
        if follow_up.marker not in linked:
            client.post(
                comments_path,
                {"body": f"{follow_up.marker}\n\nTracked the hand-applied work in #{number}."},
            )
    return created


def main(argv: list[str] | None = None, client: FollowUpClient | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Examples:\n"
            "  hand_part_follow_up.py --repo owner/repo --event merge.json --dry-run\n"
            "  hand_part_follow_up.py --repo owner/repo --event merge.json --write\n"
            "Exit: 0 success | 1 invalid event or failed GitHub request | 2 usage error"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", required=True, type=repo_argument, help="OWNER/REPO")
    parser.add_argument("--event", required=True, help="pull_request event JSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print planned issue titles (default)")
    mode.add_argument("--write", action="store_true", help="create issues and links using GH_TOKEN")
    args = parser.parse_args(argv)
    try:
        plan = plan_follow_ups(read_json_object(args.event, "--event"), args.repo)
        if plan is None:
            print(json.dumps({"planned": 0}))
        elif args.write:
            if client is None:
                token = os.environ.get("GH_TOKEN")
                if not token:
                    raise FetchError("GH_TOKEN is required for --write")
                client = GitHubClient(token)
            print(json.dumps({"created": publish_follow_ups(client, args.repo, plan)}))
        else:
            print(json.dumps({"titles": [follow_up.title for follow_up in plan.follow_ups]}))
    except (FetchError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


def _follow_up(pr: int, source: int, sha: str, index: int, title: str, text: str) -> FollowUp:
    marker = format_marker(HAND_PART, pr=pr, section=index)
    body = (
        f"{marker}\n\nHand-applied work from PR #{pr} for issue #{source} "
        f"(merge commit `{sha}`).\n\n"
    )
    return FollowUp(f"Apply by hand: {title} from #{pr}", body + text, marker)


def _sections(body: str) -> Iterator[tuple[str, str]]:
    start = 0
    title = ""
    for offset, line in _section_headings(body):
        if title:
            yield title, body[start:offset]
        heading = HAND_PART_HEADING.fullmatch(re.sub(r"[ \t]+#+[ \t]*$", "", line))
        start = offset
        title = heading["title"] if heading else ""
    if title:
        yield title, body[start:]


def _section_headings(body: str) -> Iterator[tuple[int, str]]:
    """Find top-level section boundaries without losing offsets into the original body."""
    fence, list_indent = "", ""
    in_comment = False
    offset = 0
    for raw_line in body.splitlines(keepends=True):
        line_start = offset
        offset += len(raw_line)
        line = raw_line.rstrip("\r\n")
        if fence and list_indent and line.strip() and not line.startswith(list_indent):
            fence, list_indent = "", ""
        marker = _FENCE.fullmatch(line.removeprefix(list_indent))
        if fence:
            if marker and not marker[1] and marker[2].startswith(fence) and not marker[3].strip():
                fence, list_indent = "", ""
            continue
        if in_comment:
            in_comment = "-->" not in line
            continue
        # Check a fence before HTML comments, which can be code in a fence's info string.
        if marker and (marker[2][0] == "~" or "`" not in marker[3]):
            fence = marker[2]
            list_indent = " " * marker.start(2) if marker[1] else ""
            continue
        in_comment = any(not match[0].endswith("-->") for match in _HTML_COMMENT.finditer(line))
        if _HEADING.match(line):
            yield line_start, _HTML_COMMENT.sub("", line)


def _marked_entries(entries: list[dict]) -> Iterator[tuple[dict, str]]:
    for entry in entries:
        for match in read_markers(HAND_PART, [comment_entry(entry)]):
            yield entry, format_marker(HAND_PART, **match.markers[0])


def _issue_number(entry: object) -> int:
    number = entry.get("number") if isinstance(entry, dict) else None
    if type(number) is not int or number < 1:
        raise FetchError("GitHub response is missing a valid issue number")
    return number


if __name__ == "__main__":
    sys.exit(main())
