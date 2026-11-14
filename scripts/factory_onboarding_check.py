#!/usr/bin/env python3
"""Read-only check of a repository that calls the factory's reusable workflows.

docs/agents/factory-onboarding.md is the runbook; this script is its last
manual step. It prints one tab-separated line per onboarding item,
``<STATUS>\\t<item>\\t<detail>``, with STATUS ``OK``, ``MISSING`` or
``CANNOT-VERIFY``:

- ``labels``: the five state labels exist.
- ``visibility``, ``rulesets``: public or private, and what follows for the
  brakes (no request for the rulesets line).
- ``app-installation``, ``secret:CLAUDE_CODE_OAUTH_TOKEN``, ``actions-policy``:
  never readable with a session token (401/403), so always CANNOT-VERIFY.
- ``caller:<factory file>``: a workflow on the default branch calls it with
  ``permissions: {}``, the required inputs and secrets passed by name.
- ``pin``: every caller pins the same 40-hex SHA, and it is on agents ``main``.

Standard library only; GET requests only. Callers are scanned line by line for
the forms the runbook's templates use, not parsed as YAML. Details name files,
refs, labels and statuses, never file content or the token.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import re
import sys
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass

from issue_triage_policy import STATE_LABELS
from pr_github_client import REPO_PATTERN, FetchError, GitHubClient, ReadClient, get_json, paginate

FACTORY_REPO = "fabiandistler/agents"
FACTORY_BRANCH = "main"
WORKFLOWS_DIR = ".github/workflows"
# The name of the secret, not its value.
OAUTH_SECRET = "CLAUDE_CODE_OAUTH_TOKEN"  # noqa: S105

# Factory workflow -> the `required: true` inputs and secrets of its
# `workflow_call` block. scripts/test_factory_onboarding_check.py keeps this
# equal to the workflow files.
REQUIREMENTS: dict[str, dict[str, tuple[str, ...]]] = {
    "factory-implementer.yml": {"inputs": ("check_command",), "secrets": (OAUTH_SECRET,)},
    "factory-pr-review.yml": {"inputs": (), "secrets": (OAUTH_SECRET,)},
    "factory-issue-triage.yml": {"inputs": (), "secrets": (OAUTH_SECRET,)},
    "factory-triage-label.yml": {"inputs": (), "secrets": ()},
}

OK = "OK"
MISSING = "MISSING"
CANNOT_VERIFY = "CANNOT-VERIFY"

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_USAGE = 2
EXIT_API = 3

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
USES_LINE = re.compile(
    r"^\s*uses:\s*[\"']?" + re.escape(FACTORY_REPO) + r"/\.github/workflows/"
    r"(?P<file>[A-Za-z0-9._-]+)@(?P<ref>[A-Za-z0-9._/-]+)"
)
TOP_LEVEL_EMPTY_PERMISSIONS = re.compile(r"^permissions:\s*\{\s*\}\s*(#.*)?$", re.MULTILINE)
SECRETS_INHERIT = re.compile(r"^\s*secrets:\s*inherit\s*(#.*)?$", re.MULTILINE)
BLOCK_START = re.compile(r"^(?P<indent>\s*)(?P<block>with|secrets):\s*(#.*)?$")
BLOCK_KEY = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_-]+):\s*\S")

HELP = """\
usage: factory_onboarding_check.py --repo OWNER/NAME

Read-only check of a repository that calls the factory's reusable workflows
(docs/agents/factory-onboarding.md). Prints <STATUS>\\t<item>\\t<detail> lines,
STATUS one of OK, MISSING, CANNOT-VERIFY. Reads GH_TOKEN from the environment.

  --repo OWNER/NAME  the target repository
  -h, --help         show this help

Examples:
  GH_TOKEN=$(gh auth token) python3 scripts/factory_onboarding_check.py --repo octo/dotfiles
  python3 scripts/factory_onboarding_check.py --repo octo/tools | grep -v '^OK'

Exit: 0 no MISSING line (CANNOT-VERIFY allowed), 1 a MISSING line,
      2 usage error (bad --repo, no GH_TOKEN), 3 GitHub API error.
"""


@dataclass(frozen=True)
class Caller:
    """One workflow file on the default branch that calls a factory workflow."""

    path: str
    ref: str
    text: str


class _Parser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return HELP

    def format_usage(self) -> str:
        return HELP.splitlines()[0] + "\n"


def _repo(value: str) -> str:
    if not REPO_PATTERN.match(value):
        raise argparse.ArgumentTypeError("expected OWNER/NAME")
    return value


def _contents_path(repo: str, path: str) -> str:
    return f"/repos/{repo}/contents/{urllib.parse.quote(path)}"


def _line(status: str, item: str, detail: str) -> tuple[str, str, str]:
    return (status, item, detail)


def label_line(client: ReadClient, repo: str) -> tuple[str, str, str]:
    names = {label.get("name") for label in paginate(client, f"/repos/{repo}/labels")}
    absent = [label for label in STATE_LABELS if label not in names]
    if absent:
        return _line(MISSING, "labels", "absent: " + ", ".join(absent))
    return _line(OK, "labels", "all five state labels exist")


def rulesets_line(private: bool) -> tuple[str, str, str]:
    if private:
        return _line(
            OK,
            "rulesets",
            "no rulesets on GitHub Free: no check can be required; the push guard is the brake",
        )
    return _line(
        CANNOT_VERIFY,
        "rulesets",
        "a ruleset requiring the checks and the pull_request_target event policy are set by hand",
    )


def manual_lines(repo: str) -> list[tuple[str, str, str]]:
    """The items no session token can read; each names the page to check."""
    settings = f"https://github.com/{repo}/settings"
    return [
        _line(
            CANNOT_VERIFY,
            "app-installation",
            "check by hand that the Claude GitHub App covers the repository: "
            f"{settings}/installations",
        ),
        _line(
            CANNOT_VERIFY,
            f"secret:{OAUTH_SECRET}",
            f"check by hand that the repository secret exists: {settings}/secrets/actions",
        ),
        _line(
            CANNOT_VERIFY,
            "actions-policy",
            f"check by hand that {FACTORY_REPO}/.github/workflows/* is allowed: {settings}/actions",
        ),
    ]


def _decode(payload: object, path: str) -> str:
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise FetchError(f"GitHub API returned an unexpected payload for {path}")
    try:
        return base64.b64decode(str(payload.get("content", ""))).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as error:
        raise FetchError(f"GitHub API returned undecodable content for {path}") from error


def workflow_files(client: ReadClient, repo: str, branch: str) -> list[str]:
    """The `.yml`/`.yaml` files in `.github/workflows/` on ``branch``; none on a 404."""
    path = _contents_path(repo, WORKFLOWS_DIR)
    try:
        listing = get_json(client, path, params={"ref": branch})
    except FetchError as error:
        if error.status == 404:
            return []
        raise
    if not isinstance(listing, list):
        raise FetchError(f"GitHub API returned an unexpected payload for {path}")
    return sorted(
        entry["path"]
        for entry in listing
        if isinstance(entry, dict)
        and entry.get("type") == "file"
        and isinstance(entry.get("path"), str)
        and entry["path"].endswith((".yml", ".yaml"))
    )


def find_callers(client: ReadClient, repo: str, branch: str) -> dict[str, Caller]:
    """Factory workflow file -> the first caller of it on ``branch``."""
    callers: dict[str, Caller] = {}
    for path in workflow_files(client, repo, branch):
        api_path = _contents_path(repo, path)
        text = _decode(get_json(client, api_path, params={"ref": branch}), api_path)
        for line in text.splitlines():
            match = USES_LINE.match(line)
            if match and match["file"] in REQUIREMENTS and match["file"] not in callers:
                callers[match["file"]] = Caller(path, match["ref"], text)
    return callers


def _passed_keys(text: str) -> dict[str, set[str]]:
    """The keys under every `with:` and `secrets:` block, by block name."""
    passed: dict[str, set[str]] = {"with": set(), "secrets": set()}
    block: str | None = None
    block_indent = 0
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if block is not None and indent > block_indent:
            key = BLOCK_KEY.match(line)
            if key:
                passed[block].add(key["key"])
            continue
        block = None
        start = BLOCK_START.match(line)
        if start:
            block, block_indent = start["block"], len(start["indent"])
    return passed


def caller_line(factory_file: str, caller: Caller | None, branch: str) -> tuple[str, str, str]:
    item = f"caller:{factory_file}"
    if caller is None:
        return _line(MISSING, item, f"no workflow on {branch} calls it")
    problems: list[str] = []
    if not TOP_LEVEL_EMPTY_PERMISSIONS.search(caller.text):
        problems.append("no top-level permissions: {}")
    if SECRETS_INHERIT.search(caller.text):
        problems.append("uses secrets: inherit")
    passed = _passed_keys(caller.text)
    required = REQUIREMENTS[factory_file]
    for secret in required["secrets"]:
        if secret not in passed["secrets"]:
            problems.append(f"does not pass secret {secret}")
    for name in required["inputs"]:
        if name not in passed["with"]:
            problems.append(f"does not pass input {name}")
    if problems:
        return _line(MISSING, item, f"{caller.path}: " + "; ".join(problems))
    return _line(OK, item, caller.path)


def pin_line(client: ReadClient, callers: dict[str, Caller]) -> tuple[str, str, str]:
    if not callers:
        return _line(MISSING, "pin", "no caller to read a pin from")
    by_file = sorted((caller.path, caller.ref) for caller in callers.values())
    not_sha = [f"{path}@{ref}" for path, ref in by_file if not FULL_SHA.match(ref)]
    if not_sha:
        return _line(MISSING, "pin", "not a full commit SHA: " + ", ".join(not_sha))
    refs = {ref for _, ref in by_file}
    if len(refs) > 1:
        return _line(
            MISSING,
            "pin",
            "callers pin different SHAs: " + ", ".join(f"{p}@{r}" for p, r in by_file),
        )
    sha = refs.pop()
    path = f"/repos/{FACTORY_REPO}/compare/{FACTORY_BRANCH}...{sha}"
    try:
        comparison = get_json(client, path)
    except FetchError as error:
        if error.status == 404:
            return _line(MISSING, "pin", f"{sha} not found in {FACTORY_REPO}")
        raise
    if not isinstance(comparison, dict):
        raise FetchError(f"GitHub API returned an unexpected payload for {path}")
    status = comparison.get("status")
    if status in ("behind", "identical"):
        return _line(OK, "pin", f"{sha} is on {FACTORY_REPO} {FACTORY_BRANCH}")
    return _line(MISSING, "pin", f"{sha} is not on {FACTORY_REPO} {FACTORY_BRANCH} ({status})")


def check(client: ReadClient, repo: str) -> Iterator[tuple[str, str, str]]:
    """Every onboarding line, in the runbook's order."""
    meta = get_json(client, f"/repos/{repo}")
    if not isinstance(meta, dict):
        raise FetchError(f"GitHub API returned an unexpected payload for /repos/{repo}")
    private = bool(meta.get("private"))
    branch = meta.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise FetchError(f"GitHub API returned no default branch for /repos/{repo}")
    yield label_line(client, repo)
    yield _line(OK, "visibility", "private" if private else "public")
    yield rulesets_line(private)
    yield from manual_lines(repo)
    callers = find_callers(client, repo, branch)
    for factory_file in REQUIREMENTS:
        yield caller_line(factory_file, callers.get(factory_file), branch)
    yield pin_line(client, callers)


def main(argv: list[str] | None = None, client: ReadClient | None = None) -> int:
    parser = _Parser(prog="factory_onboarding_check.py", add_help=True)
    parser.add_argument("--repo", required=True, type=_repo)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return EXIT_OK if exit_.code == 0 else EXIT_USAGE
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("factory_onboarding_check.py: GH_TOKEN is not set", file=sys.stderr)
        return EXIT_USAGE
    client = client or GitHubClient(token)
    found_missing = False
    try:
        for status, item, detail in check(client, args.repo):
            found_missing = found_missing or status == MISSING
            print(f"{status}\t{item}\t{detail}", flush=True)
    except FetchError as error:
        print(f"factory_onboarding_check.py: {error}", file=sys.stderr)
        return EXIT_API
    return EXIT_MISSING if found_missing else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
