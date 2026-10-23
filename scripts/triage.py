#!/usr/bin/env python3
"""Model-free half of the issue-triage workflow.

The workflow runs this script on both sides of the model. `fetch` reads one
issue and its comments through `gh api` and writes a bounded JSON document
with HTML comments, CSS-hidden elements, zero-width characters and base64
blobs removed. `apply` validates a category/state decision against the label
mapping in docs/agents/triage-labels.md, re-reads the live issue, and adds
only the labels the documented policy allows and the issue lacks. Neither
subcommand comments, closes or assigns anything.

Stdlib only. Every GitHub call goes through the injected runner, so the tests
exercise the real argv without a network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LABELS_DOC = REPO_ROOT / "docs" / "agents" / "triage-labels.md"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_GITHUB = 3
EXIT_INVALID = 4

TITLE_LIMIT = 300
BODY_LIMIT = 6000
COMMENT_LIMIT = 2000
COMMENT_COUNT_LIMIT = 20
RELATED_LIMIT = 100
TRUNCATION_MARK = "\n[truncated]"

CATEGORY_ROLES = ("bug", "enhancement")
STATE_ROLES = ("needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix")
# The only roles the automation may ever write; the rest need a human.
APPLYABLE_ROLES = ("bug", "enhancement", "needs-triage", "ready-for-human")
DECISION_FIELDS = {"category", "state", "confidence", "reason"}
CATEGORY_THRESHOLD = 0.6
READY_THRESHOLD = 0.8

ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{100,}={0,2}")
ROLE_ROW = re.compile(r"^\|\s*`([a-z][a-z-]*)`\s*\|\s*`([a-z][a-z-]*)`\s*\|")
HIDDEN_STYLES = ("display:none", "visibility:hidden", "font-size:0", "opacity:0")
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
BLOCK_TAGS = {"br", "div", "li", "p", "tr"}


class TriageError(Exception):
    """Base class for failures the CLI reports as one stderr line."""


class UsageError(TriageError):
    pass


class GitHubError(TriageError):
    pass


class InvalidInput(TriageError):
    """The issue, decision or label mapping does not match its contract."""


@dataclass(frozen=True)
class GitHub:
    """Thin `gh api` wrapper. Tests inject a runner that records argv."""

    runner: Any

    def api(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        paginate: bool = False,
    ) -> Any:
        argv = ["api", "--method", method, path]
        if paginate:
            argv += ["--paginate", "--slurp"]
        stdin = None
        if body is not None:
            argv += ["--input", "-"]
            stdin = json.dumps(body)
        raw = self.runner(argv, stdin).strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GitHubError(f"gh api {path} returned invalid JSON") from exc


def run_gh(argv: list[str], stdin: str | None) -> str:
    proc = subprocess.run(  # noqa: S603 -- fixed gh argv, no shell
        ["gh", *argv],  # noqa: S607 -- gh resolves from PATH
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"gh exited with {proc.returncode}"
        raise GitHubError(detail)
    return proc.stdout


class _VisibleText(HTMLParser):
    """Keep visible text, drop comments, script/style and CSS-hidden elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style") or _hides(attrs):
            if tag not in VOID_TAGS:
                self.hidden.append(tag)
            return
        if not self.hidden and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _hides(attrs: list[tuple[str, str | None]]) -> bool:
    for name, value in attrs:
        if name == "hidden":
            return True
        if name == "style" and value:
            style = re.sub(r"\s+", "", value.lower())
            if any(rule in style for rule in HIDDEN_STYLES):
                return True
    return False


def sanitize(text: str, limit: int) -> str:
    """Strip hidden and encoded payloads, then cap the result."""
    parser = _VisibleText()
    parser.feed(text)
    parser.close()
    cleaned = "".join(parser.parts)
    cleaned = ZERO_WIDTH.sub("", cleaned)
    cleaned = BASE64_BLOB.sub("[base64 removed]", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - len(TRUNCATION_MARK)].rstrip() + TRUNCATION_MARK
    return cleaned


def build_document(
    issue: dict[str, Any],
    comments: list[dict[str, Any]],
    related: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    author = issue.get("user") or {}
    selected = comments[-COMMENT_COUNT_LIMIT:]
    return {
        "number": issue["number"],
        "title": sanitize(issue.get("title") or "", TITLE_LIMIT),
        "body": sanitize(issue.get("body") or "", BODY_LIMIT),
        "state": issue.get("state"),
        "labels": [label["name"] for label in issue.get("labels") or []],
        "author": author.get("login"),
        "author_type": author.get("type"),
        "created_at": issue.get("created_at"),
        "url": issue.get("html_url"),
        "comments_total": len(comments),
        "comments": [
            {
                "author": (comment.get("user") or {}).get("login"),
                "created_at": comment.get("created_at"),
                "body": sanitize(comment.get("body") or "", COMMENT_LIMIT),
            }
            for comment in selected
        ],
        "related_open_issues": related or [],
    }


def related_issues(issues: list[dict[str, Any]], current_number: int) -> list[dict[str, Any]]:
    """Open issue titles the classifier may compare against for duplicates."""
    related = []
    for item in issues:
        if "pull_request" in item or item.get("number") == current_number:
            continue
        related.append(
            {
                "number": item["number"],
                "title": sanitize(item.get("title") or "", TITLE_LIMIT),
            }
        )
        if len(related) == RELATED_LIMIT:
            break
    return related


def load_label_mapping(path: Path = DEFAULT_LABELS_DOC) -> dict[str, str]:
    """Read the role-to-label table from the one documented mapping."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidInput(f"cannot read label mapping {path}") from exc
    mapping: dict[str, str] = {}
    for line in text.splitlines():
        match = ROLE_ROW.match(line)
        if match:
            mapping[match.group(1)] = match.group(2)
    required = (*CATEGORY_ROLES, *STATE_ROLES)
    missing = [role for role in required if role not in mapping]
    if missing:
        raise InvalidInput(f"label mapping {path} is missing roles: {', '.join(missing)}")
    if len(set(mapping.values())) != len(mapping):
        raise InvalidInput(f"label mapping {path} maps two roles to one label")
    return mapping


def validate_decision(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InvalidInput("decision is not a JSON object")
    if raw.get("fallback") is True:
        reason = raw.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidInput("fallback decision needs a reason")
        return {"fallback": True, "reason": reason.strip()}
    unknown = sorted(set(raw) - DECISION_FIELDS)
    if unknown:
        raise InvalidInput(f"decision has unknown fields: {', '.join(unknown)}")
    missing = sorted(DECISION_FIELDS - set(raw))
    if missing:
        raise InvalidInput(f"decision is missing fields: {', '.join(missing)}")
    category = raw["category"]
    state = raw["state"]
    confidence = raw["confidence"]
    reason = raw["reason"]
    if category not in (*CATEGORY_ROLES, "unclear"):
        raise InvalidInput(f"invalid category: {category!r}")
    if state not in ("needs-triage", "ready-for-human"):
        raise InvalidInput(f"invalid state: {state!r}")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise InvalidInput("confidence must be a number between 0 and 1")
    if not 0 <= confidence <= 1:
        raise InvalidInput("confidence must be a number between 0 and 1")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise InvalidInput("reason must be one non-empty sentence of at most 500 characters")
    return {
        "category": category,
        "state": state,
        "confidence": float(confidence),
        "reason": reason.strip(),
    }


def target_labels(decision: dict[str, Any], mapping: dict[str, str]) -> list[str]:
    """Derive the labels policy allows, ignoring the model's state when it conflicts."""
    if decision.get("fallback"):
        return []
    confidence = decision["confidence"]
    clear = decision["category"] in CATEGORY_ROLES and confidence >= CATEGORY_THRESHOLD
    labels = [mapping[decision["category"]]] if clear else []
    state_role = "ready-for-human" if clear and confidence >= READY_THRESHOLD else "needs-triage"
    labels.append(mapping[state_role])
    if not set(labels) <= {mapping[role] for role in APPLYABLE_ROLES}:
        raise InvalidInput("decision asks for a human-only label")
    return labels


def apply_decision(
    gh: GitHub,
    repo: str,
    issue_number: int,
    decision: dict[str, Any],
    mapping: dict[str, str],
    *,
    dry_run: bool = False,
) -> tuple[dict[str, Any], str]:
    """Return the result object and its Markdown summary. Write labels unless dry-run."""
    issue = gh.api(f"/repos/{repo}/issues/{issue_number}")
    if "pull_request" in issue:
        raise InvalidInput(f"#{issue_number} is a pull request, not an issue")
    present = [label["name"] for label in issue.get("labels") or []]
    result: dict[str, Any] = {
        "issue": issue_number,
        "title": issue.get("title"),
        "decision": decision,
        "labels_before": present,
        "labels_added": [],
        "status": "skipped",
        "skip_reason": None,
    }

    state_roles = [role for role in STATE_ROLES if mapping[role] in present]
    if issue.get("state") != "open":
        result["skip_reason"] = f"issue is {issue.get('state')}"
    elif len(state_roles) > 1:
        names = ", ".join(mapping[role] for role in state_roles)
        result["skip_reason"] = f"issue carries conflicting state labels: {names}"
    else:
        wanted = target_labels(decision, mapping)
        if state_roles and mapping[state_roles[0]] not in wanted:
            result["skip_reason"] = f"issue already carries state label {mapping[state_roles[0]]}"
        else:
            existing_categories = [role for role in CATEGORY_ROLES if mapping[role] in present]
            if existing_categories:
                category_labels = {mapping[role] for role in CATEGORY_ROLES}
                wanted = [label for label in wanted if label not in category_labels]
            to_add = [label for label in wanted if label not in present]
            if not wanted:
                result["skip_reason"] = "classifier produced no decision"
            elif not to_add:
                result["skip_reason"] = "labels already present"
            elif dry_run:
                result["status"] = "dry-run"
                result["labels_added"] = to_add
            else:
                gh.api(
                    f"/repos/{repo}/issues/{issue_number}/labels",
                    method="POST",
                    body={"labels": to_add},
                )
                result["status"] = "applied"
                result["labels_added"] = to_add

    return result, summary_markdown(result)


def summary_markdown(result: dict[str, Any]) -> str:
    decision = result["decision"]
    lines = [f"### Issue #{result['issue']}: {result['title']}", ""]
    if decision.get("fallback"):
        lines.append(f"- Classifier: fallback, no labels applied ({decision['reason']})")
    else:
        lines += [
            f"- Category: `{decision['category']}`",
            f"- State asked: `{decision['state']}`",
            f"- Confidence: {decision['confidence']:.2f}",
            f"- Reason: {decision['reason']}",
        ]
    added = ", ".join(f"`{label}`" for label in result["labels_added"]) or "none"
    lines += [
        f"- Labels added: {added}",
        f"- Outcome: {result['status']}"
        + (f" ({result['skip_reason']})" if result["skip_reason"] else ""),
        "",
    ]
    return "\n".join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_repo(explicit: str | None) -> str:
    repo = explicit or os.environ.get("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", repo):
        raise UsageError("pass --repo OWNER/NAME or set GITHUB_REPOSITORY")
    return repo


def _print_error(message: str) -> None:
    print(f"triage: {message}", file=sys.stderr)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="triage.py",
        description="Fetch and sanitize a GitHub issue, then validate and apply a triage decision.",
        epilog="exit: 0 done or skipped, 2 usage, 3 gh or label-map failure, 4 invalid issue or decision",
    )
    parser.add_argument("--repo", help="OWNER/NAME; defaults to $GITHUB_REPOSITORY")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="fetch, sanitize and write one issue as JSON")
    fetch.add_argument("--issue", type=int, required=True)
    fetch.add_argument("--output", type=Path, required=True)

    apply = sub.add_parser("apply", help="validate a decision and add its labels")
    apply.add_argument("--issue", type=int, required=True)
    apply.add_argument("--decision", type=Path, required=True)
    apply.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    apply.add_argument(
        "--summary-file", type=Path, help="append a Markdown section, e.g. $GITHUB_STEP_SUMMARY"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, gh: GitHub | None = None) -> int:
    args = parse_args(argv)
    client = gh or GitHub(run_gh)
    try:
        repo = resolve_repo(args.repo)
        if args.command == "fetch":
            issue = client.api(f"/repos/{repo}/issues/{args.issue}")
            if "pull_request" in issue:
                raise InvalidInput(f"#{args.issue} is a pull request, not an issue")
            comments = client.api(f"/repos/{repo}/issues/{args.issue}/comments?per_page=100") or []
            open_issues = (
                client.api(
                    f"/repos/{repo}/issues?state=open&per_page=100&sort=created&direction=desc"
                )
                or []
            )
            document = build_document(issue, comments, related_issues(open_issues, args.issue))
            write_json(args.output, document)
            print(json.dumps({"issue": args.issue, "output": str(args.output)}))
            return EXIT_OK

        mapping = load_label_mapping()
        try:
            raw = json.loads(args.decision.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidInput(f"cannot read decision {args.decision}") from exc
        decision = validate_decision(raw)
        result, summary = apply_decision(
            client, repo, args.issue, decision, mapping, dry_run=args.dry_run
        )
        if args.summary_file:
            with args.summary_file.open("a", encoding="utf-8") as handle:
                handle.write(summary)
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_OK
    except UsageError as exc:
        _print_error(str(exc))
        return EXIT_USAGE
    except InvalidInput as exc:
        _print_error(str(exc))
        return EXIT_INVALID
    except GitHubError as exc:
        _print_error(str(exc))
        return EXIT_GITHUB


if __name__ == "__main__":
    sys.exit(main())
