"""Parse a model review response into the review artifact, failing safe.

The parser accepts only the documented header block (see
``pr_review_prompt.md``). A response without the header, with an unknown
risk, verdict or severity, or without findings becomes `verdict: concerns`
and `risk: high` with the raw text retained. The artifact shape is shared
with ``pr_review.py``, which builds the skipped and unavailable artifacts.
``InputCoverage`` is the part of that shape that says what the model was not
shown; the request builder fills it and the sticky comment names it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from pr_risk import RISK_ORDER

SCHEMA_VERSION = 1

# The artifact statuses and the verdicts and severities a model may answer with.
REVIEW_STATUSES = ("ok", "unavailable", "skipped")
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


# The payload note and the sticky comment name at most this many files per list.
NAMED_PATHS_LIMIT = 20


def name_paths(paths: list[str] | tuple[str, ...], render: Callable[[str], str]) -> str:
    """``paths`` as a comma list of at most NAMED_PATHS_LIMIT, then how many more."""
    named = ", ".join(render(path) for path in paths[:NAMED_PATHS_LIMIT])
    rest = len(paths) - NAMED_PATHS_LIMIT
    return f"{named} and {rest} more" if rest > 0 else named


@dataclass(frozen=True)
class InputCoverage:
    """What of a pull request the review model was not shown.

    The review is partial only when a diff line was not seen: the diff was cut
    or unavailable, or hidden markup was removed from it. Base content is
    context, so files sent without it are named but leave the review complete.
    """

    diff_cut: bool = False
    diff_markup_removed: bool = False
    diff_last_full_file: str | None = None
    diff_files_not_in_full: tuple[str, ...] = ()
    base_content_missing: tuple[str, ...] = ()

    @property
    def partial(self) -> bool:
        return self.diff_cut or self.diff_markup_removed

    def omissions(self) -> dict:
        return {
            "diff_cut": self.diff_cut,
            "diff_markup_removed": self.diff_markup_removed,
            "diff_last_full_file": self.diff_last_full_file,
            "diff_files_not_in_full": list(self.diff_files_not_in_full),
            "base_content_missing": list(self.base_content_missing),
        }


COMPLETE_INPUT = InputCoverage()


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
    coverage: InputCoverage = COMPLETE_INPUT,
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
        "partial": coverage.partial,
        "omissions": coverage.omissions(),
        "raw": raw,
    }


def parse_response(text: str, context: dict, coverage: InputCoverage = COMPLETE_INPUT) -> dict:
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

    # An unknown severity is not guessed: the whole response counts as unparseable.
    severities_known = all(finding["severity"] in SEVERITIES for finding in findings)
    if (
        risk not in RISK_ORDER
        or verdict not in VERDICTS
        or not summary
        or not findings
        or not severities_known
    ):
        return build_artifact(
            context,
            "ok",
            risk="high",
            verdict="concerns",
            summary="",
            findings=[],
            coverage=coverage,
            raw=text,
        )
    return build_artifact(
        context,
        "ok",
        risk=risk,
        verdict=verdict,
        summary=summary,
        findings=findings,
        coverage=coverage,
    )
