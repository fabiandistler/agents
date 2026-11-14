"""The rules of the Fix task, free of I/O: one issue per factory failure signature.

A failed factory run (implementer, skill-audit, issue-triage, pr-review) is
reduced to a signature: the workflow path, the job and step of the first
failure, and a normalized reason. The reason is the first annotation starting
with ``RUN FAILED`` (``agent_run_report.py`` prints it), otherwise the job's
first error annotation. Numbers, SHAs, URLs and ``#<n>`` become placeholders,
so two runs failing the same way share a signature and one issue.

``plan`` decides the one write for a run: a comment on the open issue with the
signature's marker, or a new issue. ``scripts/factory_failure.py`` fetches the
facts and applies the plan; see ADR-0016 and docs/agents/triage-labels.md.
"""

from __future__ import annotations

import hashlib
import re

from agent_run_report import FAILED_PREFIX
from issue_triage_policy import COMMENT_AUTHOR, NEEDS_TRIAGE
from pr_comment import fenced_block

LABEL = "factory-failure"
LABEL_COLOR = "b60205"
LABEL_DESCRIPTION = "A factory workflow run failed; filed by the Fix task"
ISSUE_LABELS = (LABEL, "bug", NEEDS_TRIAGE)
# Issues and comments the workflow's GITHUB_TOKEN writes carry this author; a
# marker quoted by anyone else never counts.
AUTHOR = COMMENT_AUTHOR

WATCHED_WORKFLOWS = (
    ".github/workflows/implementer.yml",
    ".github/workflows/skill-audit.yml",
    ".github/workflows/issue-triage.yml",
    ".github/workflows/pr-review.yml",
)
IMPLEMENTER = ".github/workflows/implementer.yml"
FAILED_CONCLUSIONS = ("failure", "timed_out")
# The implementer's run-name; only this exact shape names the issue it works.
IMPLEMENTER_RUN_NAME = re.compile(r"implementer: issue #([1-9][0-9]*)")

MAX_REASON = 200
NO_REASON = "(no error annotation)"
UNKNOWN = "(unknown)"
_URL = re.compile(r"https?://\S+")
_ISSUE_REF = re.compile(r"#[0-9]+")
# Hex of SHA length with at least one digit, so plain words like "defaced" stay.
_SHA = re.compile(r"\b(?=[0-9a-f]*[0-9])[0-9a-f]{7,64}\b", re.IGNORECASE)
_DIGITS = re.compile(r"[0-9]+")


def normalize_reason(text: str) -> str:
    """One capped line with run-specific values replaced by placeholders."""
    line = _URL.sub("<url>", text)
    line = _ISSUE_REF.sub("#<n>", line)
    line = _SHA.sub("<sha>", line)
    line = _DIGITS.sub("<n>", line)
    line = " ".join(line.split())
    return line[:MAX_REASON] if line else NO_REASON


def first_failure(jobs: list[dict]) -> dict:
    """The first failed job and its first failed step, by name, and the job id."""
    failed = [job for job in jobs if job.get("conclusion") in ("failure", "timed_out")]
    if not failed:
        failed = [job for job in jobs if job.get("conclusion") not in ("success", "skipped")]
    if not failed:
        return {"job": UNKNOWN, "step": UNKNOWN, "job_id": None}
    job = failed[0]
    steps = job.get("steps") or []
    step = next((s for s in steps if s.get("conclusion") == "failure"), None)
    if step is None:
        step = next((s for s in steps if s.get("conclusion") in ("cancelled", "timed_out")), None)
    return {
        "job": str(job.get("name") or UNKNOWN),
        "step": str((step or {}).get("name") or UNKNOWN),
        "job_id": job.get("id"),
    }


def failure_reason(annotations: list[dict]) -> str:
    """The first line of the RUN FAILED annotation, else of the first error one."""
    messages = [str(a.get("message") or "").strip() for a in annotations]
    chosen = next((m for m in messages if m.startswith(FAILED_PREFIX)), None)
    if chosen is None:
        chosen = next(
            (
                str(a.get("message") or "").strip()
                for a in annotations
                if a.get("annotation_level") == "failure" and str(a.get("message") or "").strip()
            ),
            "",
        )
    return chosen.splitlines()[0] if chosen else ""


def signature(path: str, job: str, step: str, reason: str) -> dict:
    """The signature fields and the marker their hash makes."""
    fields = {"workflow": path, "job": job, "step": step, "reason": normalize_reason(reason)}
    digest = hashlib.sha256("\n".join(fields.values()).encode("utf-8")).hexdigest()[:16]
    return {**fields, "hash": digest, "marker": f"<!-- factory-failure:{digest} -->"}


def run_record(run: dict) -> str:
    """The marker that records one run attempt on an issue."""
    return f"<!-- factory-failure-run:{run['id']}/{run['attempt']} -->"


def fix_issue_number(run: dict) -> int | None:
    """The issue an implementer run works on, read from its run-name."""
    if run.get("path") != IMPLEMENTER:
        return None
    found = IMPLEMENTER_RUN_NAME.fullmatch(str(run.get("display_title") or ""))
    return int(found.group(1)) if found else None


def _bot_wrote(entry: dict, marker: str) -> bool:
    return entry.get("author") == AUTHOR and marker in (entry.get("body") or "")


def find_issues(issues: list[dict], marker: str) -> tuple[dict | None, dict | None]:
    """The open issue the bot filed with ``marker``, and the newest closed one."""
    matching = sorted(
        (issue for issue in issues if _bot_wrote(issue, marker)),
        key=lambda issue: issue["number"],
        reverse=True,
    )
    open_issue = next((issue for issue in matching if issue.get("state") == "open"), None)
    closed = next((issue for issue in matching if issue.get("state") != "open"), None)
    return open_issue, closed


def skip_reason(run: dict) -> str | None:
    """Why a run files nothing, or None when it should."""
    if run.get("path") not in WATCHED_WORKFLOWS:
        return "the workflow is not watched"
    if run.get("conclusion") not in FAILED_CONCLUSIONS:
        return f"the run concluded {run.get('conclusion')}, not failure or timed_out"
    return None


def _neutral(text: str) -> str:
    """Text with every @ broken by a zero-width space, so it mentions nobody."""
    return text.replace("@", "@\u200b")


def _comment(run: dict, failure: dict, record: str, date: str) -> str:
    return "\n".join(
        [
            record,
            (
                f"Failed again: [run {run['id']}, attempt {run['attempt']}]({run['url']})"
                f" on {date}, job `{_neutral(failure['job'])}`,"
                f" step `{_neutral(failure['step'])}`."
            ),
        ]
    )


def _issue(run: dict, failure: dict, sig: dict, record: str, closed: dict | None) -> dict:
    lines = [
        sig["marker"],
        record,
        (
            f"A factory run failed: [{run['name']} run {run['id']}, attempt {run['attempt']}]"
            f"({run['url']})."
        ),
        "",
        f"- Workflow: `{sig['workflow']}`",
        f"- Job: `{_neutral(failure['job'])}`",
        f"- Step: `{_neutral(failure['step'])}`",
        "",
        "Normalized reason:",
        "",
        *fenced_block(_neutral(sig["reason"])),
    ]
    if closed is not None:
        lines += ["", f"The same failure was filed before in #{closed['number']}, now closed."]
    lines += [
        "",
        "Later runs failing the same way are added as comments. A fix attempt is a person",
        "posting an agent brief here and adding `ready-for-agent` (ADR-0016).",
    ]
    title = f"{run['name']}: {failure['job']}/{failure['step']} failed"
    return {
        "kind": "create_issue",
        "title": _neutral(title),
        "body": "\n".join(lines),
        "labels": list(ISSUE_LABELS),
    }


def plan(
    run: dict,
    failure: dict,
    open_issue: dict | None,
    closed_issue: dict | None,
    fix_issue: dict | None,
    date: str,
) -> dict:
    """The one write for a failed run, or why there is none.

    ``failure`` holds ``job``, ``step`` and the raw ``reason``. ``open_issue``,
    ``closed_issue`` come from ``find_issues``; ``open_issue`` and
    ``fix_issue`` (the issue a fix-related implementer run works on) carry
    ``comments`` as ``{author, body}``. ``date`` is the day shown in a comment.
    """
    sig = signature(run.get("path") or "", failure["job"], failure["step"], failure["reason"])
    planned = {
        "run_id": run.get("id"),
        "attempt": run.get("attempt"),
        "signature": sig,
        "skip_reason": skip_reason(run),
        "action": None,
    }
    if planned["skip_reason"] is not None:
        return planned
    record = run_record(run)
    target = None
    if fix_issue is not None and LABEL in fix_issue.get("labels", []):
        target = fix_issue
    elif open_issue is not None:
        target = open_issue
    if target is not None:
        if _bot_wrote(target, record) or any(
            _bot_wrote(comment, record) for comment in target.get("comments", [])
        ):
            planned["skip_reason"] = f"run {run['id']} attempt {run['attempt']} is recorded"
            return planned
        planned["action"] = {
            "kind": "comment",
            "number": target["number"],
            "body": _comment(run, failure, record, date),
        }
        return planned
    planned["action"] = _issue(run, failure, sig, record, closed_issue)
    return planned
