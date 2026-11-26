#!/usr/bin/env python3
"""Fetch the PR text, the linked issue and the CI status of the current branch.

usage: gather_inputs.py --out DIR [--repo DIR] [--pr N | --from-json FILE]

Detects the forge from the `origin` remote (GitHub or Azure DevOps) and reads
the pull request of the current branch, or --pr N, through `gh api` or `az`.
  --out DIR   writes inputs.json (the manifest, also printed), pr.md, issue.md, ci.json
  --repo DIR  the repository (default: the current directory)
  --from-json FILE  import GitHub evidence without a remote or forge CLI: a JSON
              object with pr (number, title, body, base.ref, head.sha, optional
              merge_status), issues (number, title, body, comments [{body}] on
              each issue), check_runs (name, status, conclusion), optional
              statuses (context, state); [] for a checked, empty list.
ci.json: {"state": "green"|"failing"|"pending"|"none", "checks": [{name, state}]}
inputs.json: pr.merge_status "clean"|"conflicts"|"unknown" (default unknown);
"unchecked": [{"input": "pr"|"issue"|"ci", "reason": ...}], one per input it
could not read; the caller falls back to text the reviewer supplies.

exit codes: 0 all three inputs read; 1 usage error; 2 not a git repository;
3 manifest written, some input unchecked.

examples:
  python3 scripts/gather_inputs.py --out "$(mktemp -d)"
  python3 scripts/gather_inputs.py --repo ~/src/app --from-json forge.json --out /tmp/rd.x1
"""

# The CLIs authenticate themselves (gh's login or GH_TOKEN in the environment,
# az's login); this script passes no credential and never prints the remote URL,
# which may carry one.

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import cli

EXIT_OK, EXIT_NOT_GIT, EXIT_UNCHECKED = 0, 2, 3

# GitHub closing keywords; the issue the PR claims to implement.
CLOSING = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)\b", re.IGNORECASE)

GITHUB_GREEN = {"success", "neutral", "skipped"}

MERGE_STATUSES = ("clean", "conflicts", "unknown")
# GitHub's `mergeable` is null while it computes the test merge in the background.
GITHUB_MERGE_STATUS = {True: "clean", False: "conflicts"}
# Azure's other mergeStatus values (notSet, queued, rejectedByPolicy, failure)
# say nothing about conflicts, so they map to unknown.
AZURE_MERGE_STATUS = {"succeeded": "clean", "conflicts": "conflicts"}


class ForgeError(Exception):
    """A forge CLI is missing or a call failed; the message names which."""


def run_cli(repo: Path, argv: list[str]) -> Any:
    """Run a forge CLI in the repository and parse its JSON stdout."""
    if shutil.which(argv[0]) is None:
        raise ForgeError(f"{argv[0]} is not installed")
    proc = subprocess.run(  # noqa: S603 -- fixed CLI argv, no shell, no secret.
        argv, cwd=repo, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        # Its stderr stays unread: forge error text may quote the PR or the issue.
        raise ForgeError(f"{' '.join(argv[:3])} failed (exit {proc.returncode})")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        raise ForgeError(f"{' '.join(argv[:3])} returned no JSON") from err


def remote_host(url: str) -> str:
    """The host of a git remote: https://host/..., ssh://user@host/..., or user@host:path."""
    if "://" in url:
        return (urlsplit(url).hostname or "").lower()
    match = re.match(r"^[^@/]+@([^:/]+):", url)
    return match.group(1).lower() if match else ""


def detect_forge(url: str) -> str:
    if not url:
        return "none"
    host = remote_host(url)
    if host == "github.com":
        return "github"
    if host in ("dev.azure.com", "ssh.dev.azure.com") or host.endswith(".visualstudio.com"):
        return "azure"
    return "unknown"


def github_slug(url: str) -> tuple[str, str]:
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not match:
        raise ForgeError("cannot read owner and repository from the GitHub remote")
    return match.group(1), match.group(2)


def overall(states: list[str]) -> str:
    if "failing" in states:
        return "failing"
    if "pending" in states:
        return "pending"
    if "green" in states:
        return "green"
    return "none"


class Inputs:
    """The files written so far and what could not be read."""

    def __init__(self, out: Path, forge: str):
        self.out = out
        self.manifest: dict = {
            "forge": forge,
            "pr": None,
            "issues": [],
            "files": {},
            "unchecked": [],
        }

    def _write(self, key: str, name: str, text: str) -> None:
        (self.out / name).write_bytes(text.encode("utf-8"))
        self.manifest["files"][key] = name

    def write_pr(self, info: dict, text: str) -> None:
        self._write("pr", "pr.md", text)
        self.manifest["pr"] = info

    def write_issues(self, issues: list[tuple[str, str, str]]) -> None:
        parts = [f"# {issue_id} {title}\n\n{body}\n" for issue_id, title, body in issues]
        self._write("issue", "issue.md", "\n".join(parts))
        self.manifest["issues"] = [issue_id for issue_id, _, _ in issues]

    def write_checks(self, checks: list[dict]) -> None:
        ci = {"state": overall([check["state"] for check in checks]), "checks": checks}
        self._write("ci", "ci.json", json.dumps(ci, indent=2) + "\n")

    def unchecked(self, key: str, reason: str) -> None:
        self.manifest["unchecked"].append({"input": key, "reason": reason})


def github_checks(runs: list[dict], statuses: list[dict]) -> list[dict]:
    checks = []
    for run in runs:
        if run.get("status") != "completed":
            state = "pending"
        elif run.get("conclusion") in GITHUB_GREEN:
            state = "green"
        else:
            state = "failing"
        checks.append({"name": run["name"], "state": state})
    status_state = {"success": "green", "pending": "pending"}
    for status in statuses:
        state = status_state.get(status["state"], "failing")
        checks.append({"name": status["context"], "state": state})
    return checks


class GitHub:
    """Reads through `gh api` (REST): the GraphQL-backed porcelain fails in some sessions."""

    def __init__(self, repo: Path, url: str):
        self.repo = repo
        self.owner, name = github_slug(url)
        self.base = f"repos/{self.owner}/{name}"

    def api(self, endpoint: str) -> Any:
        return run_cli(self.repo, ["gh", "api", f"{self.base}/{endpoint}"])

    def pull(self, branch: str, number: int | None) -> dict:
        if number is None:
            pulls = self.api(f"pulls?head={self.owner}:{branch}&state=open")
            if not pulls:
                raise ForgeError(
                    "no open pull request for the current branch in this repository;"
                    " for a pull request from a fork, pass --pr N"
                )
            # The list endpoint omits `mergeable`; the single-PR endpoint has it.
            number = pulls[0]["number"]
        return self.api(f"pulls/{number}")

    @staticmethod
    def summary(pull: dict) -> tuple[dict, str]:
        info = {
            "number": pull["number"],
            "target_branch": pull["base"]["ref"],
            "head_sha": pull["head"]["sha"],
            "merge_status": GITHUB_MERGE_STATUS.get(pull.get("mergeable"), "unknown"),
        }
        return info, f"# {pull['title']}\n\n{pull.get('body') or ''}\n"

    def issues(self, pull: dict) -> list[tuple[str, str, str]]:
        ids = list(dict.fromkeys(CLOSING.findall(pull.get("body") or "")))
        found = []
        for issue_id in ids:
            issue = self.api(f"issues/{issue_id}")
            found.append((issue_id, issue["title"], issue.get("body") or ""))
        return found

    no_issue = "the PR text names no closing issue (Closes #n)"

    def checks(self, pull: dict) -> list[dict]:
        sha = pull["head"]["sha"]
        runs = self.api(f"commits/{sha}/check-runs?per_page=100").get("check_runs", [])
        statuses = self.api(f"commits/{sha}/status").get("statuses", [])
        return github_checks(runs, statuses)


# Azure policy types that report CI: build validation and external status checks.
AZURE_CI_POLICIES = {"Build", "Status"}
AZURE_STATE = {
    "approved": "green",
    "notApplicable": "skipped",
    "queued": "pending",
    "running": "pending",
}


class Azure:
    """Reads through `az repos` / `az boards`; --detect takes org, project and repo from git."""

    def __init__(self, repo: Path):
        self.repo = repo

    def az(self, *args: str) -> Any:
        return run_cli(self.repo, ["az", *args, "--detect", "true", "--output", "json"])

    def pull(self, branch: str, number: int | None) -> dict:
        if number is not None:
            return self.az("repos", "pr", "show", "--id", str(number))
        pulls = self.az("repos", "pr", "list", "--source-branch", branch, "--status", "active")
        if not pulls:
            raise ForgeError("no active pull request for the current branch")
        return pulls[0]

    @staticmethod
    def summary(pull: dict) -> tuple[dict, str]:
        info = {
            "number": pull["pullRequestId"],
            "target_branch": pull["targetRefName"].removeprefix("refs/heads/"),
            "head_sha": pull["lastMergeSourceCommit"]["commitId"],
            "merge_status": AZURE_MERGE_STATUS.get(pull.get("mergeStatus"), "unknown"),
        }
        return info, f"# {pull['title']}\n\n{pull.get('description') or ''}\n"

    def issues(self, pull: dict) -> list[tuple[str, str, str]]:
        number = str(pull["pullRequestId"])
        found = []
        for linked in self.az("repos", "pr", "work-item", "list", "--id", number):
            item_id = str(linked["id"])
            item = self.az(
                "boards",
                "work-item",
                "show",
                "--id",
                item_id,
                "--fields",
                "System.Title,System.Description",
                # `--expand` defaults to `all`, and the service rejects any
                # expand together with `--fields`.
                "--expand",
                "none",
            )
            fields = item.get("fields", {})
            found.append(
                (item_id, fields.get("System.Title", ""), fields.get("System.Description") or "")
            )
        return found

    no_issue = "the pull request has no linked work item"

    def checks(self, pull: dict) -> list[dict]:
        number = str(pull["pullRequestId"])
        checks = []
        for record in self.az("repos", "pr", "policy", "list", "--id", number):
            config = record.get("configuration", {})
            type_name = config.get("type", {}).get("displayName")
            if type_name not in AZURE_CI_POLICIES:
                continue
            name = config.get("settings", {}).get("displayName") or type_name
            checks.append({"name": name, "state": AZURE_STATE.get(record["status"], "failing")})
        return checks


def gather(forge: GitHub | Azure, branch: str, pr_number: int | None, inputs: Inputs) -> None:
    """Read each input on its own, so one failed call leaves the others intact."""
    try:
        pull = forge.pull(branch, pr_number)
    except ForgeError as err:
        for key in ("pr", "issue", "ci"):
            inputs.unchecked(key, str(err))
        return
    inputs.write_pr(*forge.summary(pull))

    try:
        issues = forge.issues(pull)
    except ForgeError as err:
        inputs.unchecked("issue", str(err))
    else:
        if issues:
            inputs.write_issues(issues)
        else:
            inputs.unchecked("issue", forge.no_issue)

    try:
        checks = forge.checks(pull)
    except ForgeError as err:
        inputs.unchecked("ci", str(err))
    else:
        inputs.write_checks(checks)


def json_field(record: Any, name: str, expected: type | tuple[type, ...]) -> Any:
    if not isinstance(record, dict) or name not in record or not isinstance(record[name], expected):
        raise ForgeError(f"missing or invalid {name} field in --from-json")
    value = record[name]
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as err:
            raise ForgeError(f"invalid Unicode in {name} field in --from-json") from err
    return value


def json_number(record: dict) -> int:
    number = json_field(record, "number", int)
    if isinstance(number, bool) or number < 1:
        raise ForgeError("number in --from-json must be a positive integer")
    return number


def json_pull(envelope: dict) -> tuple[dict, str]:
    pull = json_field(envelope, "pr", dict)
    json_number(pull)
    json_field(pull, "title", str)
    json_field(pull, "body", (str, type(None)))
    for parent, field in (("base", "ref"), ("head", "sha")):
        if not json_field(json_field(pull, parent, dict), field, str).strip():
            raise ForgeError(f"{parent}.{field} in --from-json must be non-empty")
    merge_status = json_field(pull, "merge_status", str) if "merge_status" in pull else "unknown"
    if merge_status not in MERGE_STATUSES:
        raise ForgeError("merge_status in --from-json must be clean, conflicts or unknown")
    info, text = GitHub.summary(pull)
    info["merge_status"] = merge_status
    return info, text


def json_issues(envelope: dict) -> list[tuple[str, str, str]]:
    issues = []
    for issue in json_field(envelope, "issues", list):
        number = json_number(issue)
        title = json_field(issue, "title", str)
        body = json_field(issue, "body", (str, type(None))) or ""
        comments = json_field(issue, "comments", list)
        parts = [body]
        parts.extend(f"## Comment\n\n{json_field(comment, 'body', str)}" for comment in comments)
        issues.append((str(number), title, "\n\n".join(parts)))
    if not issues:
        raise ForgeError("--from-json supplies no linked issue")
    return issues


def json_checks(envelope: dict) -> list[dict]:
    runs = json_field(envelope, "check_runs", list)
    for run in runs:
        json_field(run, "name", str)
        if json_field(run, "status", str) == "completed":
            json_field(run, "conclusion", str)
    statuses = json_field(envelope, "statuses", list) if "statuses" in envelope else []
    for status in statuses:
        json_field(status, "context", str)
        json_field(status, "state", str)
    return github_checks(runs, statuses)


def gather_json(source: Path, inputs: Inputs) -> None:
    try:
        envelope = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        envelope = None
    if not isinstance(envelope, dict):
        for key in ("pr", "issue", "ci"):
            inputs.unchecked(key, "cannot read --from-json as a JSON object")
        return

    try:
        inputs.write_pr(*json_pull(envelope))
    except ForgeError as err:
        inputs.unchecked("pr", str(err))
    try:
        inputs.write_issues(json_issues(envelope))
    except ForgeError as err:
        inputs.unchecked("issue", str(err))
    try:
        inputs.write_checks(json_checks(envelope))
    except ForgeError as err:
        inputs.unchecked("ci", str(err))


def gather_remote(repo: Path, out: Path, pr_number: int | None) -> Inputs:
    url = (cli.git(repo, "remote", "get-url", "origin") or "").strip()
    kind = detect_forge(url)
    inputs = Inputs(out, kind)
    branch = (cli.git(repo, "branch", "--show-current") or "").strip()
    try:
        forge = GitHub(repo, url) if kind == "github" else Azure(repo) if kind == "azure" else None
    except ForgeError as err:
        forge, reason = None, str(err)
    else:
        reason = "the remote is neither GitHub nor Azure DevOps"
    if forge is None:
        for key in ("pr", "issue", "ci"):
            inputs.unchecked(key, reason)
    else:
        gather(forge, branch, pr_number, inputs)
    return inputs


def main(argv: list[str] | None = None) -> int:
    parser = cli.parser(__doc__, "gather_inputs.py")
    parser.add_argument("--out", required=True)
    parser.add_argument("--repo", default=".")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pr", type=int)
    mode.add_argument("--from-json", type=Path)
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if cli.git(repo, "rev-parse", "--git-dir") is None:
        print("gather_inputs.py: --repo is not inside a git repository", file=sys.stderr)
        return EXIT_NOT_GIT
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.from_json is None:
        inputs = gather_remote(repo, out, args.pr)
    else:
        inputs = Inputs(out, "github")
        gather_json(args.from_json, inputs)

    text = json.dumps(inputs.manifest, indent=2) + "\n"
    (out / "inputs.json").write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return EXIT_UNCHECKED if inputs.manifest["unchecked"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
