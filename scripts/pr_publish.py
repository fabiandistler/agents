#!/usr/bin/env python3
"""Plan the publish actions for one reviewed pull request.

The publisher is model-free. It reads the risk decision produced by
``pr_risk.py`` and the review artifact produced by ``pr_review.py``, re-runs the
risk policy on a fresh context, and emits the exact list of actions it would
take: label changes, one sticky comment, a reviewer request (or an assignment
when the maintainer authored the pull request), and an auto-merge enable or
disable. Nothing here writes to GitHub; the plan is the whole output.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pr_apply
import pr_github
import pr_risk

SCHEMA_VERSION = 1

BOT_LOGIN = "fabiandistler"
COMMENT_MARKER = "<!-- pr-review-bot -->"

RISK_PREFIX = "risk:"
VERDICT_PREFIX = "review:"
NEEDS_REVIEW = "needs-review"
DO_NOT_MERGE = "do-not-merge"
AUTO_MERGE_LABEL = "auto-merge:bot"
AUTO_MERGE_ENV = "PR_AUTO_MERGE"
AUTO_MERGE_METHOD = "merge"
AUTO_MERGE_DELETE_BRANCH = True
REQUIRED_CHECKS = ("checks", "mermaid", "secrets")

REVIEW_STATUSES = ("ok", "unavailable", "skipped")
VERDICTS = ("pass", "concerns", "block")
SEVERITIES = ("info", "warning", "blocker")

EXIT_OK = 0
EXIT_ACTION_FAILED = 1
EXIT_USAGE = 2
EXIT_BAD_INPUT = 3
EXIT_LIVE_FAILED = 4
EXIT_OUTSIDE_ACTIONS = 5


class ArtifactError(ValueError):
    """A file could not be read, or an artifact has the wrong shape."""


# --- Validation --------------------------------------------------------------


def _require_mapping(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ArtifactError(f"{name} is not a JSON object")
    if value.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ArtifactError(f"{name} has an unsupported schema_version")
    return value


def _validate_context(context: object) -> dict:
    context = _require_mapping(context, "context")
    repo = context.get("repo")
    if not isinstance(repo, str) or not pr_github.REPO_PATTERN.fullmatch(repo):
        raise ArtifactError("context is missing repo as OWNER/REPO")
    number = context.get("number")
    if isinstance(number, bool) or not isinstance(number, int):
        raise ArtifactError("context is missing an integer number")
    head_sha = context.get("head_sha")
    if not isinstance(head_sha, str) or not head_sha:
        raise ArtifactError("context is missing head_sha")
    reviews = context.get("reviews")
    if not isinstance(reviews, dict) or not isinstance(reviews.get("changes_requested"), bool):
        raise ArtifactError("context field 'reviews' must carry a boolean changes_requested")
    return context


def _validate_assessment(assessment: object) -> dict:
    assessment = _require_mapping(assessment, "assessment")
    head_sha = assessment.get("head_sha")
    if not isinstance(head_sha, str) or not head_sha:
        raise ArtifactError("assessment is missing head_sha")
    if assessment.get("risk") not in pr_risk.RISK_ORDER:
        raise ArtifactError("assessment risk must be low, medium or high")
    return assessment


def _validate_review(review: object) -> dict:
    review = _require_mapping(review, "review")
    status = review.get("status")
    if status not in REVIEW_STATUSES:
        raise ArtifactError("review status must be ok, unavailable or skipped")
    head_sha = review.get("head_sha")
    if head_sha is not None and (not isinstance(head_sha, str) or not head_sha):
        raise ArtifactError("review head_sha must be a non-empty string or null")
    if status == "ok":
        if review.get("risk") not in pr_risk.RISK_ORDER:
            raise ArtifactError("review risk must be low, medium or high")
        if review.get("verdict") not in VERDICTS:
            raise ArtifactError("review verdict must be pass, concerns or block")
    if not isinstance(review.get("partial", False), bool):
        raise ArtifactError("review partial must be a boolean")
    findings = review.get("findings", [])
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        raise ArtifactError("review findings must be a list of objects")
    for field in ("summary", "raw"):
        if not isinstance(review.get(field), (str, type(None))):
            raise ArtifactError(f"review {field} must be a string or null")
    return review


# --- Decisions ---------------------------------------------------------------


def _labels(context: dict) -> list[str]:
    labels = context.get("labels")
    if not isinstance(labels, list):
        return []
    return [label for label in labels if isinstance(label, str)]


def _raise_risk(current: str, candidate: str) -> str:
    return candidate if pr_risk.RISK_ORDER[candidate] > pr_risk.RISK_ORDER[current] else current


def _effective_risk(context: dict, review: dict) -> tuple[str, dict]:
    policy = pr_risk.classify_pull_request(context)
    if review["status"] != "ok":
        return policy["risk"], policy
    return _raise_risk(policy["risk"], review["risk"]), policy


def _verdict_label(review: dict) -> str | None:
    if review["status"] == "ok":
        return f"{VERDICT_PREFIX}{review['verdict']}"
    if review["status"] == "unavailable":
        return f"{VERDICT_PREFIX}unavailable"
    return None


def _needs_review(context: dict, risk: str, review: dict) -> bool:
    # A self-authored pull request cannot request the maintainer as a reviewer;
    # the assignment plus this label carry the signal instead.
    return (
        risk in (pr_risk.MEDIUM, pr_risk.HIGH)
        or review["status"] == "unavailable"
        or review.get("verdict") in ("concerns", "block")
        or context.get("author") == BOT_LOGIN
    )


def _plan_labels(
    context: dict,
    risk: str,
    review: dict,
    enable_auto_merge: bool,
    disable_auto_merge: bool,
) -> tuple[list[str], list[str]]:
    existing = _labels(context)
    add: list[str] = []
    remove: list[str] = []

    desired_risk = f"{RISK_PREFIX}{risk}"
    if desired_risk not in existing:
        add.append(desired_risk)
    remove.extend(
        label for label in existing if label.startswith(RISK_PREFIX) and label != desired_risk
    )

    desired_verdict = _verdict_label(review)
    if desired_verdict is None:
        remove.extend(label for label in existing if label.startswith(VERDICT_PREFIX))
    else:
        if desired_verdict not in existing:
            add.append(desired_verdict)
        remove.extend(
            label
            for label in existing
            if label.startswith(VERDICT_PREFIX) and label != desired_verdict
        )

    if _needs_review(context, risk, review):
        if NEEDS_REVIEW not in existing:
            add.append(NEEDS_REVIEW)
    elif NEEDS_REVIEW in existing:
        remove.append(NEEDS_REVIEW)

    if enable_auto_merge and AUTO_MERGE_LABEL not in existing:
        add.append(AUTO_MERGE_LABEL)
    if disable_auto_merge:
        remove.append(AUTO_MERGE_LABEL)

    return add, remove


def _auto_merge_enabled(value: object) -> bool:
    """The repository variable enables auto-merge only when it is exactly `true`."""
    return value is True or value == "true"


def _auto_merge_blocked(context: dict, risk: str, review: dict, enabled: bool) -> bool:
    if not enabled or risk != pr_risk.LOW:
        return True
    if review["status"] != "ok" or review["verdict"] != "pass":
        return True
    if review.get("partial") is not False:
        return True
    if context.get("fork") or context.get("draft"):
        return True
    if context.get("mergeable") is not True:
        return True
    base_ref = context.get("base_ref")
    default_branch = context.get("default_branch")
    if not isinstance(base_ref, str) or base_ref != default_branch:
        return True
    if context["reviews"]["changes_requested"]:
        return True
    if DO_NOT_MERGE in _labels(context):
        return True
    checks = context.get("checks")
    if not isinstance(checks, dict):
        return True
    return any(checks.get(name) != "success" for name in REQUIRED_CHECKS)


def _reviewer_action(context: dict) -> dict:
    if context.get("author") == BOT_LOGIN:
        return {"kind": "assign", "login": BOT_LOGIN}
    return {"kind": "request_reviewer", "login": BOT_LOGIN}


# --- Sticky comment ----------------------------------------------------------


def _single_line(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _render_finding(finding: dict) -> str:
    path = _single_line(finding.get("path")).replace("`", "'") or "(unknown file)"
    line = finding.get("line")
    location = f"{path}:{line}" if isinstance(line, int) and not isinstance(line, bool) else path
    severity = finding.get("severity")
    severity = severity if severity in SEVERITIES else "info"
    message = _single_line(finding.get("message")) or "(no message)"
    rendered = f"- `{location}` — **{severity}**: {message}"
    suggestion = _single_line(finding.get("suggestion"))
    if suggestion:
        rendered += f"\n  - Fix: {suggestion}"
    return rendered


def _fenced_block(text: str) -> list[str]:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}text", text.rstrip(), fence]


def _status_consequence(context: dict, status: str) -> str:
    if status == "unavailable":
        return "Auto-merge stays off until a review succeeds."
    if context.get("draft") is True:
        return "Auto-merge stays off until the pull request is ready for review."
    if context.get("fork") is True:
        return "Fork pull requests are never auto-merged."
    return "Auto-merge stays off until a review succeeds."


def _render_comment(context: dict, risk: str, policy: dict, review: dict) -> str:
    status = review["status"]
    lines = [COMMENT_MARKER]
    if status == "ok":
        lines.append(f"## Automated PR review: risk **{risk}**, verdict **{review['verdict']}**")
    else:
        lines.append(f"## Automated PR review: risk **{risk}**, review {status}")
    lines += ["", f"Reviewed commit `{context['head_sha'][:7]}`."]

    summary = _single_line(review.get("summary"))
    raw = review.get("raw")
    if status in ("unavailable", "skipped"):
        lines += ["", f"> {summary or f'Review {status}.'}", ">"]
        lines.append(f"> {_status_consequence(context, status)}")
    elif summary:
        lines += ["", summary]
    if status == "ok" and not summary and isinstance(raw, str) and raw.strip():
        lines += [
            "",
            "The model response could not be parsed, so it is shown verbatim:",
            "",
            *_fenced_block(raw),
        ]
    if review.get("partial") is True:
        lines += [
            "",
            (
                "> **Partial review.** The input was truncated, so parts of the diff were not "
                "reviewed. Auto-merge stays off."
            ),
        ]

    lines += ["", "**Risk reasons**", ""]
    lines += [f"- {_single_line(reason)}" for reason in policy["reasons"]]
    if risk != policy["risk"]:
        lines.append(f"- review: raised the risk from {policy['risk']} to {risk}")

    findings = review.get("findings") or []
    if status == "ok" and findings:
        lines += ["", "**Findings**", ""]
        lines += [_render_finding(finding) for finding in findings]

    lines += [
        "",
        "---",
        "Advisory only: this bot never approves a pull request and never merges one directly.",
    ]
    return "\n".join(lines)


def _sticky_comment(context: dict) -> dict | None:
    comments = context.get("comments")
    for comment in comments if isinstance(comments, list) else []:
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        if isinstance(body, str) and COMMENT_MARKER in body:
            return comment
    return None


def _comment_action(context: dict, risk: str, policy: dict, review: dict) -> dict | None:
    body = _render_comment(context, risk, policy, review)
    existing = _sticky_comment(context)
    if existing is not None and existing.get("body") == body:
        return None
    comment_id = existing.get("id") if existing is not None else None
    return {
        "kind": "upsert_comment",
        "comment_id": comment_id,
        "marker": COMMENT_MARKER,
        "body": body,
    }


# --- Plan --------------------------------------------------------------------


def _plan(
    context: dict,
    status: str,
    abort_reason: str | None,
    actions: list[dict],
    decision: dict,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": context["repo"],
        "number": context["number"],
        "head_sha": context["head_sha"],
        "status": status,
        "abort_reason": abort_reason,
        "decision": decision,
        "actions": actions,
    }


def _decision(risk: str, review: dict, auto_merge: str) -> dict:
    return {
        "risk": risk,
        "review_status": review["status"],
        "verdict": review.get("verdict") if review["status"] == "ok" else None,
        "auto_merge": auto_merge,
    }


def _aborted_decision(review: dict) -> dict:
    return {
        "risk": None,
        "review_status": review["status"],
        "verdict": None,
        "auto_merge": "off",
    }


def _is_stale(assessment: dict, review: dict, head_sha: str) -> bool:
    if assessment["head_sha"] != head_sha:
        return True
    return review["head_sha"] is not None and review["head_sha"] != head_sha


def plan_publish(
    context: dict,
    assessment: dict,
    review: dict,
    auto_merge: bool | str | None = False,
) -> dict:
    """Return the planned actions for one pull request; never writes.

    ``auto_merge`` is the repository variable: only ``True`` or the string
    ``"true"`` enables auto-merge planning; ``None`` (unset) keeps it off.
    """
    context = _validate_context(context)
    assessment = _validate_assessment(assessment)
    review = _validate_review(review)

    if _is_stale(assessment, review, context["head_sha"]):
        return _plan(
            context,
            "aborted",
            "head_sha_changed",
            [],
            _aborted_decision(review),
        )

    risk, policy = _effective_risk(context, review)
    enable_auto_merge = not _auto_merge_blocked(
        context, risk, review, _auto_merge_enabled(auto_merge)
    )
    disable_auto_merge = not enable_auto_merge and AUTO_MERGE_LABEL in _labels(context)
    add, remove = _plan_labels(context, risk, review, enable_auto_merge, disable_auto_merge)

    actions: list[dict] = []
    if add or remove:
        actions.append({"kind": "set_labels", "add": add, "remove": remove})
    comment = _comment_action(context, risk, policy, review)
    if comment is not None:
        actions.append(comment)
    actions.append(_reviewer_action(context))
    if enable_auto_merge:
        actions.append(
            {
                "kind": "enable_auto_merge",
                "method": AUTO_MERGE_METHOD,
                "delete_branch": AUTO_MERGE_DELETE_BRANCH,
            }
        )
        auto_merge_state = "enabled"
    elif disable_auto_merge:
        actions.append({"kind": "disable_auto_merge"})
        auto_merge_state = "disabled"
    else:
        auto_merge_state = "off"
    return _plan(
        context,
        "planned",
        None,
        actions,
        _decision(risk, review, auto_merge_state),
    )


def _aborted_write_plan(plan: dict, fresh: dict) -> dict:
    head_sha = fresh.get("head_sha")
    return {
        **plan,
        "head_sha": head_sha if isinstance(head_sha, str) and head_sha else plan["head_sha"],
        "status": "aborted",
        "abort_reason": "head_sha_changed",
        "decision": {**plan["decision"], "risk": None, "verdict": None, "auto_merge": "off"},
        "actions": [],
    }


def _fetch_context(repo: str, number: int, token: str | None, client=None) -> dict:
    if client is None:
        return pr_github.fetch_context(repo, number, token=token)
    return pr_github.fetch_context(repo, number, token=token, client=client)


def publish_live(
    repo: str,
    number: int,
    assessment: dict,
    review: dict,
    write: bool = False,
    client=None,
):
    """Fetch, plan and optionally apply one pull request.

    Without ``write`` the return value is the plan. With ``write`` it is the
    plan when the plan aborts, otherwise the results wrapper. ``client`` is a
    ``GitHubClient`` or a fake implementing ``get/post/patch/delete``; both
    fetches and the writes use it, so tests never touch the network.
    """
    assessment = _validate_assessment(assessment)
    review = _validate_review(review)
    token = os.environ.get("GITHUB_TOKEN") or None
    if write and client is None and token is None:
        raise pr_github.MissingTokenError("GITHUB_TOKEN is not set")

    context = _fetch_context(repo, number, token, client)
    plan = plan_publish(context, assessment, review, auto_merge=os.environ.get(AUTO_MERGE_ENV))
    if not write or plan["status"] == "aborted":
        return plan

    fresh = _fetch_context(repo, number, token, client)
    if fresh.get("head_sha") != plan["head_sha"]:
        return _aborted_write_plan(plan, fresh)

    writer = client if client is not None else pr_github.GitHubClient(token)
    results = pr_apply.apply_plan(plan, writer)
    return {
        "schema_version": SCHEMA_VERSION,
        "plan": plan,
        "results": results,
        "ok": all(result["ok"] for result in results),
    }


# --- CLI ---------------------------------------------------------------------

USAGE = """usage: pr_publish.py --context FILE --assessment FILE --review FILE
       pr_publish.py --live --repo OWNER/REPO --pr N --assessment FILE --review FILE [--write]

Plan the labels, the sticky comment, the reviewer and the auto-merge decision
for one pull request. Prints JSON on stdout; --write applies the plan.

  --context FILE      fresh context JSON from pr_github.py
  --assessment FILE   risk decision JSON from pr_risk.py
  --review FILE       review artifact JSON from pr_review.py
  --live              re-fetch the context from GitHub; needs GITHUB_TOKEN
  --repo O/R          repository as OWNER/REPO (with --live)
  --pr N              pull request number (with --live)
  --write             apply the plan; needs --live and GITHUB_ACTIONS=true
  -h, --help          show this message

env: PR_AUTO_MERGE=true enables auto-merge planning; any other value keeps it off.

examples:
  python3 scripts/pr_publish.py --context c.json --assessment a.json --review r.json
  python3 scripts/pr_publish.py --live --repo fabiandistler/agents --pr 42 \\
      --assessment a.json --review r.json --write

exit: 0 plan or write result | 1 a write action failed | 2 usage |
      3 bad input/artifact | 4 live fetch failed | 5 --write outside GitHub Actions
"""

VALUE_FLAGS = ("--context", "--pr", "--repo", "--assessment", "--review")


class UsageError(Exception):
    """The command line was not usable."""


def _parse_arguments(argv: list[str]) -> dict:
    options: dict[str, object] = {
        "context": None,
        "live": False,
        "pr": None,
        "repo": None,
        "assessment": None,
        "review": None,
        "write": False,
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
        if name == "--write":
            if separator:
                raise UsageError("--write takes no value")
            options["write"] = True
            index += 1
            continue
        if name not in VALUE_FLAGS:
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

    for required in ("assessment", "review"):
        if options[required] is None:
            raise UsageError(f"--{required} is required")

    has_context = isinstance(options["context"], str)
    has_live = options["live"] is True
    if has_context and has_live:
        raise UsageError("--context and --live are mutually exclusive")
    if not has_context and not has_live:
        raise UsageError("one of --context or --live is required")
    if options["write"] is True and not has_live:
        raise UsageError("--write requires --live")
    if not has_live:
        if options["pr"] is not None or options["repo"] is not None:
            raise UsageError("--pr and --repo are only valid with --live")
        return options

    if options["pr"] is None or options["repo"] is None:
        raise UsageError("--live requires --pr and --repo")
    try:
        number = int(str(options["pr"]))
    except ValueError as error:
        raise UsageError("--pr must be a positive integer") from error
    if number <= 0:
        raise UsageError("--pr must be a positive integer")
    options["pr"] = number
    if not pr_github.REPO_PATTERN.fullmatch(str(options["repo"])):
        raise UsageError("--repo must be OWNER/REPO")
    return options


def _read_json(path: str, flag: str) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ArtifactError(f"cannot read {flag}: {error}") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ArtifactError(f"{flag} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ArtifactError(f"{flag} must contain a JSON object")
    return payload


def main(argv: list[str] | None = None, client=None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    try:
        options = _parse_arguments(arguments)
    except UsageError as error:
        print(f"pr_publish.py: {error}", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        return EXIT_USAGE
    if options.get("help"):
        print(USAGE, end="")
        return EXIT_OK

    if options["write"] is True and os.environ.get("GITHUB_ACTIONS") != "true":
        print(
            "pr_publish.py: --write is only available inside GitHub Actions",
            file=sys.stderr,
        )
        return EXIT_OUTSIDE_ACTIONS

    try:
        assessment = _read_json(str(options["assessment"]), "--assessment")
        review = _read_json(str(options["review"]), "--review")
        if options["live"] is True:
            try:
                payload = publish_live(
                    str(options["repo"]),
                    int(options["pr"]),
                    assessment,
                    review,
                    write=options["write"] is True,
                    client=client,
                )
            except pr_github.FetchError as error:
                print(f"pr_publish.py: live fetch failed: {error}", file=sys.stderr)
                return EXIT_LIVE_FAILED
        else:
            context = _read_json(str(options["context"]), "--context")
            payload = plan_publish(
                context,
                assessment,
                review,
                auto_merge=os.environ.get(AUTO_MERGE_ENV),
            )
    except (ArtifactError, pr_apply.PlanError) as error:
        print(f"pr_publish.py: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT

    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    if options["write"] is True and payload.get("ok") is False:
        return EXIT_ACTION_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
