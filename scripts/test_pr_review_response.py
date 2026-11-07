"""Tests for scripts/pr_review_response.py: the fail-safe model response parser."""

from __future__ import annotations

import pr_review_response

CONTEXT = {"schema_version": 1, "number": 42, "head_sha": "abc123"}


def test_response_tolerates_missing_end_and_star_bullets() -> None:
    response = (
        "RISK: low\n"
        "VERDICT: pass\n"
        "SUMMARY: Fine.\n"
        "\n"
        "FINDINGS:\n"
        "\n"
        "* docs/review.md:3 [info] No issues | fix: none\n"
        "\n"
    )
    artifact = pr_review_response.parse_response(response, CONTEXT)
    assert artifact["status"] == "ok"
    assert artifact["risk"] == "low"
    assert artifact["verdict"] == "pass"
    assert artifact["summary"] == "Fine."
    assert artifact["findings"] == [
        {
            "path": "docs/review.md",
            "line": 3,
            "severity": "info",
            "message": "No issues",
            "suggestion": "none",
        }
    ]


def test_finding_without_a_parseable_line_gets_null() -> None:
    response = (
        "RISK: low\n"
        "VERDICT: concerns\n"
        "SUMMARY: Something to say.\n"
        "FINDINGS:\n"
        "- docs/review.md [idea] Not a known severity | fix: Pick one\n"
        "END\n"
    )
    artifact = pr_review_response.parse_response(response, CONTEXT)
    assert artifact["findings"][0]["line"] is None
    assert artifact["findings"][0]["path"] == "docs/review.md"


LOW_QUALITY_RESPONSES = [
    "VERDICT: pass\nSUMMARY: Fine.\nFINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n",
    "RISK: low\nSUMMARY: Fine.\nFINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n",
    "RISK: low\nVERDICT: pass\nFINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n",
    "RISK: severe\nVERDICT: pass\nSUMMARY: Fine.\nFINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n",
    "RISK: low\nVERDICT: maybe\nSUMMARY: Fine.\nFINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n",
    "RISK: low\nVERDICT: pass\nSUMMARY: Fine.\nEND\n",
    "RISK: low\nVERDICT: pass\nSUMMARY: Fine.\nFINDINGS:\n\nEND\n",
    "Not a review at all.",
]


def test_low_quality_response_is_concerns_high_with_raw() -> None:
    for response in LOW_QUALITY_RESPONSES:
        artifact = pr_review_response.parse_response(response, CONTEXT)
        assert artifact["status"] == "ok", response
        assert artifact["risk"] == "high", response
        assert artifact["verdict"] == "concerns", response
        assert artifact["raw"] == response, response
        assert artifact["findings"] == [], response
