"""Render the review bot's sticky pull request comment.

One comment per pull request carries the risk, the verdict, the summary, the
risk reasons and the findings. It is found again by its marker and its author,
the workflow bot, and updated in place; an unchanged body plans no action.
"""

from __future__ import annotations

import re

COMMENT_MARKER = "<!-- pr-review-bot -->"
# The login the workflow's GITHUB_TOKEN writes as. A comment by anyone else is
# never the sticky comment, even when it quotes the marker.
COMMENT_AUTHOR = "github-actions[bot]"
SEVERITIES = ("info", "warning", "blocker")


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


def _render_comment(
    context: dict, risk: str, policy: dict, review: dict, auto_merge_state: str
) -> str:
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

    if auto_merge_state == "refused":
        lines += [
            "",
            (
                "> **Auto-merge could not be armed.** GitHub reports the pull request as "
                "already mergeable, so it waits for a human merge."
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
        if (
            comment.get("author") == COMMENT_AUTHOR
            and isinstance(body, str)
            and COMMENT_MARKER in body
        ):
            return comment
    return None


def comment_action(
    context: dict, risk: str, policy: dict, review: dict, auto_merge_state: str
) -> dict | None:
    """Return the upsert action for the sticky comment, or None when it is current."""
    body = _render_comment(context, risk, policy, review, auto_merge_state)
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
