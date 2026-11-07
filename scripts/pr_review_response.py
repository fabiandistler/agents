"""Parse a model review response into the review artifact, failing safe.

The parser accepts only the documented header block (see
``pr_review_prompt.md``). A response without the header, with an unknown
risk or verdict, or without findings becomes `verdict: concerns`
and `risk: high` with the raw text retained. The artifact shape is shared
with ``pr_review.py``, which builds the skipped and unavailable artifacts.
"""

from __future__ import annotations

import re

SCHEMA_VERSION = 1

RISKS = ("low", "medium", "high")
VERDICTS = ("pass", "concerns", "block")
SEVERITIES = ("info", "warning", "blocker")

_TRIM_CHARS = "*_`\"'.,;:"

_LEAD = r"[ \t*_#>\-]*"
_VALUE_START = r"[ \t*_`\"']*"
_RISK_RE = re.compile(rf"(?im)^{_LEAD}RISK[ \t]*:{_VALUE_START}([A-Za-z]+)")
_VERDICT_RE = re.compile(rf"(?im)^{_LEAD}VERDICT[ \t]*:{_VALUE_START}([A-Za-z]+)")
_SUMMARY_RE = re.compile(rf"(?im)^{_LEAD}SUMMARY[ \t]*:[ \t]*(.*)$")
_FINDINGS_RE = re.compile(rf"(?im)^{_LEAD}FINDINGS[ \t]*:[ \t]*$")
_END_RE = re.compile(r"(?im)^[ \t]*END[ \t]*$")
_BULLET_RE = re.compile(r"^[ \t]*[-*][ \t]+(?P<body>.+)$")
_FINDING_RE = re.compile(
    r"^(?P<path>.*?)[ \t]*(?::(?P<line>\d+))?[ \t]*"
    r"\[(?P<severity>[A-Za-z]+)\][ \t]*(?P<message>.*)$"
)
_FIX_RE = re.compile(r"\s*\|\s*fix\s*:\s*", re.IGNORECASE)


class ContextError(ValueError):
    """The context JSON is missing required fields or has the wrong shape."""


def validate_identity(context: object) -> None:
    if not isinstance(context, dict):
        raise ContextError("context is not a JSON object")
    if context.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ContextError("unsupported context schema_version")
    for field in ("number", "head_sha"):
        if field not in context:
            raise ContextError(f"context is missing the field {field!r}")


def _header_value(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip().strip(_TRIM_CHARS).lower()


def _parse_finding(body: str) -> dict | None:
    match = _FINDING_RE.match(body.strip())
    if match is None:
        return None
    path = match.group("path").strip().strip(_TRIM_CHARS)
    line = int(match.group("line")) if match.group("line") else None
    severity = match.group("severity").lower()
    if severity not in SEVERITIES:
        severity = "info"
    message = match.group("message").strip()
    parts = _FIX_RE.split(message, maxsplit=1)
    return {
        "path": path,
        "line": line,
        "severity": severity,
        "message": parts[0].strip(),
        "suggestion": parts[1].strip() if len(parts) == 2 else "",
    }


def _parse_findings(block: str) -> list[dict]:
    findings: list[dict] = []
    for line in block.splitlines():
        if not line.strip():
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            finding = _parse_finding(bullet.group("body"))
            if finding is not None:
                findings.append(finding)
                continue
        if findings:
            findings[-1]["message"] = f"{findings[-1]['message']} {line.strip()}".strip()
    return findings


def build_artifact(
    context: dict,
    status: str,
    *,
    risk: str | None = None,
    verdict: str | None = None,
    summary: str = "",
    findings: list[dict] | None = None,
    partial: bool = False,
    raw: str | None = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "number": context.get("number"),
        "head_sha": context.get("head_sha"),
        "status": status,
        "risk": risk,
        "verdict": verdict,
        "summary": summary,
        "findings": findings if findings is not None else [],
        "partial": partial,
        "raw": raw,
    }


def parse_response(text: str, context: dict, partial: bool = False) -> dict:
    """Turn a model response into the review artifact, failing safe."""
    validate_identity(context)
    if not isinstance(text, str):
        raise TypeError("response text is not a string")
    # Parse normalized line endings; the raw artifact keeps what the provider sent.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    risk = _header_value(_RISK_RE, normalized)
    verdict = _header_value(_VERDICT_RE, normalized)
    summary_match = _SUMMARY_RE.search(normalized)
    findings_match = _FINDINGS_RE.search(normalized)

    summary = ""
    if summary_match is not None:
        stop = len(normalized)
        if findings_match is not None and findings_match.start() >= summary_match.end():
            stop = findings_match.start()
        summary = " ".join(
            (summary_match.group(1) + " " + normalized[summary_match.end() : stop]).split()
        )

    findings: list[dict] = []
    if findings_match is not None:
        end = _END_RE.search(normalized, findings_match.end())
        stop = end.start() if end is not None else len(normalized)
        findings = _parse_findings(normalized[findings_match.end() : stop])

    if risk not in RISKS or verdict not in VERDICTS or not summary or not findings:
        return build_artifact(
            context,
            "ok",
            risk="high",
            verdict="concerns",
            summary="",
            findings=[],
            partial=partial,
            raw=text,
        )
    return build_artifact(
        context,
        "ok",
        risk=risk,
        verdict=verdict,
        summary=summary,
        findings=findings,
        partial=partial,
    )
