"""Tests for scripts/pr_review_response.py: the fail-safe model response parser."""

from __future__ import annotations

import pr_review_response
import pytest

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
        "- docs/review.md [info] No line number | fix: Pick one\n"
        "END\n"
    )
    artifact = pr_review_response.parse_response(response, CONTEXT)
    assert artifact["findings"][0]["line"] is None
    assert artifact["findings"][0]["path"] == "docs/review.md"


@pytest.mark.parametrize(
    ("finding", "path", "line"),
    [
        ("- .chezmoiignore:24 [warning] msg", ".chezmoiignore", 24),
        ("- **.github/workflows/x.yml:3** [info] msg", ".github/workflows/x.yml", 3),
        ("- `.pre-commit-config.yaml:7` [info] msg", ".pre-commit-config.yaml", 7),
        ("- ./src/a.py:1 [info] msg", "src/a.py", 1),
        ("- `src/a.py`: [info] msg", "src/a.py", None),
        ("- /etc/hosts:2 [info] msg", "/etc/hosts", 2),
    ],
)
def test_finding_path_keeps_its_leading_dot_and_line(finding: str, path: str, line) -> None:
    response = f"RISK: low\nVERDICT: concerns\nSUMMARY: s.\nFINDINGS:\n{finding}\nEND\n"
    artifact = pr_review_response.parse_response(response, CONTEXT)
    assert (artifact["findings"][0]["path"], artifact["findings"][0]["line"]) == (path, line)


LOW_QUALITY_RESPONSES = [
    "VERDICT: pass\nSUMMARY: Fine.\nFINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n",
    "RISK: low\nSUMMARY: Fine.\nFINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n",
    "RISK: low\nVERDICT: pass\nFINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n",
    (
        "RISK: severe\nVERDICT: pass\nSUMMARY: Fine.\n"
        "FINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n"
    ),
    (
        "RISK: low\nVERDICT: maybe\nSUMMARY: Fine.\n"
        "FINDINGS:\n- docs/x.md:1 [info] ok | fix: none\nEND\n"
    ),
    "RISK: low\nVERDICT: pass\nSUMMARY: Fine.\nEND\n",
    "RISK: low\nVERDICT: pass\nSUMMARY: Fine.\nFINDINGS:\n\nEND\n",
    "Not a review at all.",
    (
        "RISK: low\nVERDICT: pass\nSUMMARY: Fine.\n"
        "FINDINGS:\n- docs/x.md:1 [minor] ok | fix: none\nEND\n"
    ),
]


def test_low_quality_response_is_concerns_high_with_raw() -> None:
    for response in LOW_QUALITY_RESPONSES:
        artifact = pr_review_response.parse_response(response, CONTEXT)
        assert artifact["status"] == "ok", response
        assert artifact["risk"] == "high", response
        assert artifact["verdict"] == "concerns", response
        assert artifact["raw"] == response, response
        assert artifact["findings"] == [], response
