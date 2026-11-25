"""Render the review bot's sticky pull request comment.

One comment per pull request carries the risk, the verdict, the summary, the
risk reasons and the findings. It is found again through the handoff protocol
reader (``factory_handoff``), which counts its marker only in a comment by the
workflow bot, and updated in place; an unchanged body plans no action.
"""

from __future__ import annotations

import re

from factory_handoff import REVIEW_STICKY, format_marker, read_markers
from pr_review_response import SEVERITIES, name_paths

COMMENT_MARKER = format_marker(REVIEW_STICKY)


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


def _code_path(path: str) -> str:
    plain = _single_line(path).replace("`", "'")
    return f"`{plain}`"


def _partial_notice(omissions: dict) -> str:
    reasons = []
    if omissions.get("diff_cut") is True:
        last = omissions.get("diff_last_full_file")
        reason = "the diff was cut to the review limits or is unavailable"
        if last:
            reason += f"; the last file shown in full is {_code_path(last)}"
        not_in_full = omissions.get("diff_files_not_in_full") or []
        if not_in_full:
            reason += f"; not shown in full: {name_paths(not_in_full, _code_path)}"
        reasons.append(reason)
    if omissions.get("diff_markup_removed") is True:
        reasons.append("hidden markup was removed from the diff")
    cause = (
        "; and ".join(reasons)
        if reasons
        else "the input was truncated or hidden markup was removed from the diff"
    )
    return (
        f"> **Partial review.** Parts of the diff were not reviewed: {cause}. Auto-merge stays off."
    )


def _base_missing_notice(missing: list[str], partial: bool) -> str:
    named = name_paths(missing, _code_path)
    complete = "" if partial else " The diff was reviewed in full."
    return (
        f"> **Sent without base content:** {named}. It did not fit the review limits or "
        f"could not be fetched.{complete} Findings that depend on the unchanged lines of "
        "these files may be missing."
    )


def fenced_block(text: str) -> list[str]:
    """A ```text block around `text`, fenced longer than any backtick run in it."""
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
            *fenced_block(raw),
        ]
    omissions = review.get("omissions") or {}
    partial = review.get("partial") is True
    if partial:
        lines += ["", _partial_notice(omissions)]
    missing = omissions.get("base_content_missing") or []
    if missing:
        lines += ["", _base_missing_notice(missing, partial)]

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


def is_sticky_comment(comment: dict) -> bool:
    """Whether ``comment`` is this bot's own review comment, not a human one quoting its marker."""
    return bool(read_markers(REVIEW_STICKY, [comment]))


def _sticky_comment(context: dict) -> dict | None:
    comments = context.get("comments")
    reads = read_markers(REVIEW_STICKY, comments if isinstance(comments, list) else [])
    return dict(reads[0].entry) if reads else None


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
