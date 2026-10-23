#!/usr/bin/env python3
"""Deterministic risk policy for pull requests.

The policy is a pure function over the context produced by ``pr_github.py``.
It classifies every changed path, applies size, deletion, rename, binary and
metadata escalations, and emits one JSON decision. The result is a floor: a
later review may raise the risk, never lower it.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pr_github

SCHEMA_VERSION = 1

LOW = "low"
MEDIUM = "medium"
HIGH = "high"

RISK_ORDER = {LOW: 0, MEDIUM: 1, HIGH: 2}

# Ordered most-specific first. When several rules match one path, the highest
# risk wins; among equal risks the first rule supplies the reason label.
PATH_RULES = (
    # The triage automation is always high, whatever else matches.
    (re.compile(r"^scripts/pr_merge_guard\.py$"), HIGH, "guard-script"),
    (re.compile(r"^scripts/secret_read_guard\.py$"), HIGH, "guard-script"),
    (re.compile(r"^plugins/(?:merge-guard|secret-guard)(?:/|$)"), HIGH, "guard-script"),
    (re.compile(r"^scripts/(?:pr_|test_pr_)"), HIGH, "triage-automation"),
    # Workflows, installer, gates, build scripts and their hooks.
    (re.compile(r"^\.github/"), HIGH, "workflow"),
    (re.compile(r"^install\.sh$"), HIGH, "installer"),
    (re.compile(r"^scripts/check_[^/]*$"), HIGH, "gate-script"),
    (re.compile(r"^scripts/quick_validate\.py$"), HIGH, "gate-script"),
    (re.compile(r"^scripts/require_python\.sh$"), HIGH, "gate-script"),
    (re.compile(r"^scripts/catalogue\.py$"), HIGH, "gate-script"),
    (re.compile(r"^scripts/build_[^/]*\.py$"), HIGH, "build-script"),
    (re.compile(r"^scripts/opencode/"), HIGH, "hook-script"),
    (re.compile(r"^plugins/[^/]+/hooks/"), HIGH, "hook-settings"),
    # Configuration and dependency pins.
    (re.compile(r"^\.claude/settings\.json$"), HIGH, "hook-settings"),
    (re.compile(r"^\.pre-commit-config\.yaml$"), HIGH, "hook-settings"),
    (re.compile(r"^conftest\.py$"), HIGH, "test-config"),
    (re.compile(r"^(?:ruff\.toml|pyrightconfig\.json)$"), HIGH, "lint-config"),
    (re.compile(r"^pyproject\.toml$"), HIGH, "project-config"),
    (
        re.compile(r"(?:^|/)[^/]*\.requirements\.txt$|^(?:package|package-lock)\.json$"),
        HIGH,
        "dependency-pins",
    ),
    # Medium: skills, instructions, agent docs, mirror, tests and support code.
    (
        re.compile(r"^plugins/(?![^/]+/hooks/)(?!(?:merge-guard|secret-guard)/)"),
        MEDIUM,
        "plugins",
    ),
    (re.compile(r"^\.claude/"), MEDIUM, "claude-mirror"),
    (re.compile(r"^skills/"), MEDIUM, "skills"),
    (re.compile(r"^instructions/"), MEDIUM, "instructions"),
    (re.compile(r"^docs/agents/"), MEDIUM, "agent-docs"),
    (re.compile(r"^skills\.json$"), MEDIUM, "catalogue"),
    (re.compile(r"^scripts/test_[^/]*\.py$"), MEDIUM, "tests"),
    (re.compile(r"^scripts/test_install\.sh$"), MEDIUM, "tests"),
    (
        re.compile(r"^scripts/(?:vendor_mattpocock_skills\.py|skill_audit_select\.py)$"),
        MEDIUM,
        "scripts",
    ),
    (re.compile(r"^maintenance/(?!reports/)"), MEDIUM, "maintenance"),
    # Low: documentation and generated reports.
    (re.compile(r"^(?:README|MAINTENANCE|GLOSSARY)\.md$"), LOW, "docs"),
    (re.compile(r"^docs/(?!agents/)"), LOW, "docs"),
    (re.compile(r"^maintenance/reports/"), LOW, "maintenance-reports"),
)


def _classify_path(path: str) -> tuple[str, str]:
    """Return the risk and reason label of the strongest matching path rule."""
    best_risk = None
    best_label = "unknown"
    for pattern, risk, label in PATH_RULES:
        if not pattern.search(path):
            continue
        if best_risk is None or RISK_ORDER[risk] > RISK_ORDER[best_risk]:
            best_risk = risk
            best_label = label
    if best_risk is None:
        return HIGH, "unknown"
    return best_risk, best_label


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


def _raise_risk(current: str, candidate: str) -> str:
    return candidate if RISK_ORDER[candidate] > RISK_ORDER[current] else current


def _is_critical_deletion(path: str) -> bool:
    guarded_prefixes = (
        "skills/",
        ".github/workflows/",
        "plugins/merge-guard/",
        "plugins/secret-guard/",
    )
    return (
        path.startswith(guarded_prefixes)
        or path == "install.sh"
        or path in {"scripts/pr_merge_guard.py", "scripts/secret_read_guard.py"}
    )


def classify_pull_request(context: dict) -> dict:
    """Classify one pull request from its changed files and metadata.

    Returns the decision JSON documented in the feature contract. An empty or
    unreadable file list is high risk, never an error.
    """
    if not isinstance(context, dict):
        raise TypeError("context must be a mapping")

    entries: list[dict] = []
    reasons: list[str] = []
    reasons_unreadable = False
    raw_files = context.get("files")
    if not isinstance(raw_files, list):
        reasons_unreadable = True
        if raw_files is None:
            reasons.append("unreadable-file-list: files is missing or null")
        else:
            reasons.append("unreadable-file-list: files is not a list")
    else:
        for index, entry in enumerate(raw_files):
            path = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(path, str) or not path:
                reasons_unreadable = True
                reasons.append(f"unreadable-file-list: entry at index {index} has no path")
                continue
            entries.append(entry)

    additions = sum(_count(entry.get("additions")) for entry in entries)
    deletions = sum(_count(entry.get("deletions")) for entry in entries)
    changed_lines = additions + deletions

    risk = HIGH if reasons_unreadable else LOW
    if not entries:
        reasons.append("empty-file-list: no changed files")
        risk = HIGH

    for entry in entries:
        path_risk, label = _classify_path(entry["path"])
        reasons.append(f"{label}: {entry['path']}")
        risk = _raise_risk(risk, path_risk)

    if changed_lines > 1000:
        reasons.append(f"size: {changed_lines} changed lines > 1000")
        risk = HIGH
    elif changed_lines > 300:
        reasons.append(f"size: {changed_lines} changed lines > 300")
        risk = _raise_risk(risk, MEDIUM)

    if len(entries) > 50:
        reasons.append(f"count: {len(entries)} files > 50")
        risk = HIGH
    elif len(entries) > 20:
        reasons.append(f"count: {len(entries)} files > 20")
        risk = _raise_risk(risk, MEDIUM)

    for entry in entries:
        path = entry["path"]
        status = entry.get("status")
        if status == "removed":
            if _is_critical_deletion(path):
                reasons.append(f"critical-deletion: {path}")
                risk = HIGH
            else:
                reasons.append(f"deletion: {path}")
                risk = _raise_risk(risk, MEDIUM)
        if status == "renamed" or entry.get("renamed_from"):
            renamed_from = entry.get("renamed_from")
            if renamed_from:
                reasons.append(f"rename: {renamed_from} -> {path}")
            else:
                reasons.append(f"rename: {path}")
            risk = _raise_risk(risk, MEDIUM)
        if entry.get("binary") is True:
            reasons.append(f"binary: {path}")
            risk = HIGH

    fork = bool(context.get("fork"))
    draft = bool(context.get("draft"))
    if fork:
        reasons.append("fork: head repository differs from base")
        risk = HIGH
    if draft:
        reasons.append("draft: auto-merge disabled")

    return {
        "schema_version": SCHEMA_VERSION,
        "number": context.get("number"),
        "head_sha": context.get("head_sha"),
        "risk": risk,
        "reasons": reasons,
        "auto_merge_eligible": risk == LOW and not fork and not draft,
        "counts": {
            "files": len(entries),
            "additions": additions,
            "deletions": deletions,
            "changed_lines": changed_lines,
        },
    }


REPO_PATTERN = pr_github.REPO_PATTERN

USAGE = """usage: pr_risk.py --context FILE [--output FILE]
       pr_risk.py --live --pr N --repo OWNER/REPO [--output FILE]

Classify a pull request as low, medium or high risk from its changed paths
and metadata. Prints the decision JSON on stdout unless --output is given.

  --context FILE   read a context JSON produced by pr_github.py (offline)
  --live           fetch the context from GitHub; needs GITHUB_TOKEN
  --pr N           pull request number (with --live)
  --repo O/R       repository as OWNER/REPO (with --live)
  --output FILE    write the decision JSON to FILE instead of stdout
  -h, --help       show this message

examples:
  python3 scripts/pr_risk.py --context context.json
  python3 scripts/pr_risk.py --live --pr 42 --repo fabiandistler/agents

exit: 0 decision produced | 2 usage | 3 input malformed or output write failed |
      4 live fetch failed | 5 missing token
"""


class UsageError(Exception):
    """The command line was not usable."""


def _parse_arguments(argv: list[str]) -> dict:
    options: dict[str, object] = {
        "context": None,
        "live": False,
        "pr": None,
        "repo": None,
        "output": None,
    }
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-h", "--help"):
            return {"help": True}
        name, separator, inline = argument.partition("=")
        if name == "--live":
            if separator:
                raise UsageError("--live takes no value")
            options["live"] = True
            index += 1
            continue
        if name not in {"--context", "--pr", "--repo", "--output"}:
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

    has_context = isinstance(options["context"], str)
    has_live = options["live"] is True
    if has_context and has_live:
        raise UsageError("--context and --live are mutually exclusive")
    if not has_context and not has_live:
        raise UsageError("one of --context or --live is required")
    if has_live:
        if options["pr"] is None or options["repo"] is None:
            raise UsageError("--live requires --pr and --repo")
        try:
            number = int(str(options["pr"]))
        except ValueError as error:
            raise UsageError("--pr must be a positive integer") from error
        if number <= 0:
            raise UsageError("--pr must be a positive integer")
        options["pr"] = number
        if not REPO_PATTERN.fullmatch(str(options["repo"])):
            raise UsageError("--repo must be OWNER/REPO")
    elif options["pr"] is not None or options["repo"] is not None:
        raise UsageError("--pr and --repo are only valid with --live")
    return options


def _read_context(path: str) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"cannot read --context: {error}") from error
    try:
        context = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"--context is not valid JSON: {error}") from error
    if not isinstance(context, dict):
        raise TypeError("--context must contain a JSON object")
    return context


def _emit(decision: dict, output: str | None) -> int:
    text = json.dumps(decision, indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
        return 0
    try:
        Path(output).write_text(text, encoding="utf-8")
    except OSError as error:
        print(f"pr_risk.py: cannot write --output: {error}", file=sys.stderr)
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = _parse_arguments(arguments)
    except UsageError as error:
        print(f"pr_risk.py: {error}", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        return 2
    if options.get("help"):
        print(USAGE, end="")
        return 0

    if options["live"] is True:
        try:
            context = pr_github.fetch_context(
                str(options["repo"]),
                int(options["pr"]),
                token=os.environ.get("GITHUB_TOKEN") or None,
            )
        except pr_github.MissingTokenError as error:
            print(f"pr_risk.py: {error}", file=sys.stderr)
            return 5
        except pr_github.FetchError as error:
            print(f"pr_risk.py: live fetch failed: {error}", file=sys.stderr)
            return 4
    else:
        try:
            context = _read_context(str(options["context"]))
        except (ValueError, TypeError) as error:
            print(f"pr_risk.py: {error}", file=sys.stderr)
            return 3

    try:
        decision = classify_pull_request(context)
    except TypeError as error:
        print(f"pr_risk.py: malformed context: {error}", file=sys.stderr)
        return 3
    return _emit(decision, options["output"] if isinstance(options["output"], str) else None)


if __name__ == "__main__":
    raise SystemExit(main())
