#!/usr/bin/env python3
"""Fetch the PR text, the linked issue and the CI status of the current branch.

usage: gather_inputs.py --out DIR [--repo DIR] [--pr N]

Detects the forge from the `origin` remote (GitHub or Azure DevOps) and reads
the pull request of the current branch, or --pr N, through `gh api` or `az`.
  --out DIR   where to write inputs.json (the manifest, also printed), pr.md,
              issue.md and ci.json
  --repo DIR  the repository (default: the current directory)
ci.json: {"state": "green"|"failing"|"pending"|"none", "checks": [{name, state}]}
inputs.json "unchecked": [{"input": "pr"|"issue"|"ci", "reason": ...}], one per
input it could not read; the caller falls back to text the reviewer supplies.

exit codes: 0 all three inputs read; 1 usage error; 2 not a git repository;
3 manifest written, some input unchecked.

examples:
  python3 scripts/gather_inputs.py --out "$(mktemp -d)"
  python3 scripts/gather_inputs.py --repo ~/src/app --pr 42 --out /tmp/rd.x1
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

    def write(self, key: str, name: str, text: str) -> None:
        (self.out / name).write_text(text, encoding="utf-8")
        self.manifest["files"][key] = name

    def unchecked(self, key: str, reason: str) -> None:
        self.manifest["unchecked"].append({"input": key, "reason": reason})


class GitHub:
    """Reads through `gh api` (REST): the GraphQL-backed porcelain fails in some sessions."""

    def __init__(self, repo: Path, url: str):
        self.repo = repo
        self.owner, name = github_slug(url)
        self.base = f"repos/{self.owner}/{name}"

    def api(self, endpoint: str) -> Any:
        return run_cli(self.repo, ["gh", "api", f"{self.base}/{endpoint}"])

    def pull(self, branch: str, number: int | None) -> dict:
        if number is not None:
            return self.api(f"pulls/{number}")
        pulls = self.api(f"pulls?head={self.owner}:{branch}&state=open")
        if not pulls:
            raise ForgeError(
                "no open pull request for the current branch in this repository;"
                " for a pull request from a fork, pass --pr N"
            )
        return pulls[0]

    @staticmethod
    def summary(pull: dict) -> tuple[dict, str]:
        info = {
            "number": pull["number"],
            "target_branch": pull["base"]["ref"],
            "head_sha": pull["head"]["sha"],
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
        checks = []
        for run in self.api(f"commits/{sha}/check-runs?per_page=100").get("check_runs", []):
            if run.get("status") != "completed":
                state = "pending"
            elif run.get("conclusion") in GITHUB_GREEN:
                state = "green"
            else:
                state = "failing"
            checks.append({"name": run["name"], "state": state})
        status_state = {"success": "green", "pending": "pending"}
        for status in self.api(f"commits/{sha}/status").get("statuses", []):
            state = status_state.get(status["state"], "failing")
            checks.append({"name": status["context"], "state": state})
        return checks


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
    info, text = forge.summary(pull)
    inputs.manifest["pr"] = info
    inputs.write("pr", "pr.md", text)

    try:
        issues = forge.issues(pull)
    except ForgeError as err:
        inputs.unchecked("issue", str(err))
    else:
        if issues:
            inputs.manifest["issues"] = [issue_id for issue_id, _, _ in issues]
            parts = [f"# {issue_id} {title}\n\n{body}\n" for issue_id, title, body in issues]
            inputs.write("issue", "issue.md", "\n".join(parts))
        else:
            inputs.unchecked("issue", forge.no_issue)

    try:
        checks = forge.checks(pull)
    except ForgeError as err:
        inputs.unchecked("ci", str(err))
    else:
        ci = {"state": overall([c["state"] for c in checks]), "checks": checks}
        inputs.write("ci", "ci.json", json.dumps(ci, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = cli.parser(__doc__, "gather_inputs.py")
    parser.add_argument("--out", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--pr", type=int)
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if cli.git(repo, "rev-parse", "--git-dir") is None:
        print("gather_inputs.py: --repo is not inside a git repository", file=sys.stderr)
        return EXIT_NOT_GIT
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

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
        gather(forge, branch, args.pr, inputs)

    text = json.dumps(inputs.manifest, indent=2) + "\n"
    (out / "inputs.json").write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return EXIT_UNCHECKED if inputs.manifest["unchecked"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
