"""Check a PR's closing declarations against GitHub's resolved issue links."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REFERENCE = r"(?:https://github\.com/[\w.-]+/[\w.-]+/issues/|[\w.-]+/[\w.-]+#|#)[1-9]\d*"
CLOSING = re.compile(
    rf"\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s*:?\s+({REFERENCE})", re.IGNORECASE
)
CONTINUATION = re.compile(rf"\s*(?:,\s*(?:and\s+)?|and\s+)({REFERENCE})", re.IGNORECASE)
QUERY = """query($owner:String!,$name:String!,$number:Int!,$cursor:String) {
  repository(owner:$owner,name:$name) {
    defaultBranchRef { name }
    pullRequest(number:$number) {
      body baseRefName headRefOid
      closingIssuesReferences(first:100,after:$cursor) {
        nodes { number repository { nameWithOwner } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}"""


class GitHubError(Exception):
    """The live pull-request snapshot could not be obtained consistently."""


def issue_link_errors(body: str, repo: str, linked: set[str], *, default_base: bool) -> list[str]:
    """Compare closing intent, including accidentally comma-joined issues."""
    prose = _prose(body)
    declared: set[str] = set()
    malformed: list[str] = []
    for closing in CLOSING.finditer(prose):
        first = _reference(closing[1], repo)
        declared.add(first)
        position = closing.end()
        while following := CONTINUATION.match(prose, position):
            reference = _reference(following[1], repo)
            declared.add(reference)
            malformed.append(
                f"{_display(reference, repo)} needs its own closing keyword; "
                f"use 'Closes {_display(first, repo)}, closes {_display(reference, repo)}'"
            )
            position = following.end()
    errors = list(dict.fromkeys(malformed))
    if not declared and not re.search(r"\bno[ -]issue\b", prose, re.IGNORECASE):
        errors.append("Add a closing issue declaration or an explicit 'no issue' statement")
    if default_base:
        missing = declared - linked
        extra = linked - declared
        if missing:
            errors.append(
                "Unlinked closing issues: " + ", ".join(_display(x, repo) for x in sorted(missing))
            )
        if extra:
            errors.append(
                "Closing links absent from the body: "
                + ", ".join(_display(x, repo) for x in sorted(extra))
            )
    return errors


def read_pull_request(repo: str, number: int) -> tuple[dict[str, str], set[str]]:
    """Read all native closing links without mixing changing PR snapshots."""
    owner, name = repo.split("/")
    cursor = None
    seen_cursors: set[str] = set()
    linked: set[str] = set()
    snapshot = None
    while True:
        payload = _query({"owner": owner, "name": name, "number": number, "cursor": cursor})
        try:
            repository = payload["data"]["repository"]
            pull = repository["pullRequest"]
            current = {key: pull[key] for key in ("body", "baseRefName", "headRefOid")}
            current["defaultBranch"] = repository["defaultBranchRef"]["name"]
            if not all(isinstance(value, str) for value in current.values()):
                raise TypeError
            connection = pull["closingIssuesReferences"]
            nodes = connection["nodes"]
            if not isinstance(nodes, list):
                raise TypeError
            for node in nodes:
                issue_number = node["number"]
                issue_repo = node["repository"]["nameWithOwner"]
                if (
                    type(issue_number) is not int
                    or issue_number <= 0
                    or not isinstance(issue_repo, str)
                ):
                    raise TypeError
                _repo(issue_repo)
                linked.add(f"{issue_repo.lower()}#{issue_number}")
            page = connection["pageInfo"]
            if type(page["hasNextPage"]) is not bool:
                raise TypeError
            next_cursor = page["endCursor"]
        except (KeyError, TypeError, ValueError) as error:
            raise GitHubError("GitHub response has an invalid pull-request shape") from error
        if snapshot is not None and current != snapshot:
            raise GitHubError("Pull request changed while reading closing links; rerun the check")
        snapshot = current
        if not page["hasNextPage"]:
            return snapshot, linked
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
            raise GitHubError("GitHub returned invalid closing-link pagination")
        seen_cursors.add(next_cursor)
        cursor = next_cursor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Examples:\n  python3 scripts/check_pr_issue_links.py --repo owner/repo --pr 1\n"
        "  python3 scripts/check_pr_issue_links.py --repo owner/repo --pr 1 --output links.json\n"
        "Exit: 0 pass | 1 policy failure | 2 usage error | 3 API/stale snapshot | 4 report write failure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", required=True, type=_repo, help="base owner/repository")
    parser.add_argument("--pr", required=True, type=_positive, help="pull request number")
    parser.add_argument("--expected-head", help="reject a changed head commit")
    parser.add_argument("--output", type=Path, help="write the full JSON report")
    args = parser.parse_args(argv)
    try:
        snapshot, linked = read_pull_request(args.repo, args.pr)
        if args.expected_head and snapshot["headRefOid"] != args.expected_head:
            raise GitHubError("Pull request head changed; rerun the check on the current head")
        default_base = snapshot["baseRefName"] == snapshot["defaultBranch"]
        errors = issue_link_errors(snapshot["body"], args.repo, linked, default_base=default_base)
    except GitHubError as error:
        sys.stderr.write(str(error) + "\n")
        return 3
    report = {
        "status": "fail" if errors else "pass",
        "native_comparison": "checked" if default_base else "skipped_non_default_base",
        "linked_issues": sorted(linked),
        "errors": errors,
    }
    if args.output:
        try:
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError:
            sys.stderr.write("Cannot write the report to --output\n")
            return 4
    print(json.dumps({key: report[key] for key in ("status", "native_comparison")}))
    for error in errors[:10]:
        sys.stderr.write(error + "\n")
    if len(errors) > 10:
        sys.stderr.write("Additional violations omitted; use --output for the full report\n")
    return int(bool(errors))


def _prose(body: str) -> str:
    body = re.sub(r"<!--.*?(?:-->|$)", "", body, flags=re.DOTALL)
    lines = []
    fence = ""
    for line in body.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = ""
        elif marker:
            fence = marker[1]
        elif not line.startswith(("    ", "\t")):
            lines.append(line)
    return re.sub(r"(`+).*?\1", "", "\n".join(lines), flags=re.DOTALL)


def _reference(reference: str, repo: str) -> str:
    reference = re.sub(r"^https://github\.com/", "", reference, flags=re.IGNORECASE).replace(
        "/issues/", "#"
    )
    return (repo + reference if reference.startswith("#") else reference).lower()


def _display(reference: str, repo: str) -> str:
    prefix = repo.lower() + "#"
    return reference[len(repo) :] if reference.startswith(prefix) else reference


def _repo(value: str) -> str:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", value):
        raise ValueError("repo must be owner/repository")
    return value


def _positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("pr must be positive")
    return number


def _query(variables: dict[str, object]) -> dict:
    executable = shutil.which("gh")
    if executable is None:
        raise GitHubError("GitHub CLI is required for a live check")
    try:
        # External input stays in JSON stdin; the executable and arguments are fixed.
        response = subprocess.run(  # noqa: S603
            [executable, "api", "graphql", "--input", "-"],
            input=json.dumps({"query": QUERY, "variables": variables}),
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise GitHubError("GitHub closing-link request timed out") from error
    if response.returncode:
        raise GitHubError("GitHub closing-link request failed; verify read access and retry")
    try:
        payload = json.loads(response.stdout)
    except json.JSONDecodeError as error:
        raise GitHubError("GitHub response must be JSON") from error
    if not isinstance(payload, dict) or payload.get("errors"):
        raise GitHubError("GitHub closing-link query failed")
    return payload


if __name__ == "__main__":
    sys.exit(main())
