"""Tests for scripts/pr_review.py: request assembly, caps, parser and provider failures."""

from __future__ import annotations

import pr_review
import pytest
from pr_review_testkit import (
    FAKE_TOKEN,
    PROMPT,
    base_context,
    recording_transport,
    user_payload,
)

# --- System prompt -----------------------------------------------------------


def test_system_prompt_states_the_review_contract() -> None:
    prompt = PROMPT.read_text(encoding="utf-8")
    lowered = prompt.lower()
    assert "untrusted" in lowered
    assert "never" in lowered and "instructions" in lowered
    assert "cannot merge" in lowered or "cannot approve" in lowered
    for header in ("RISK:", "VERDICT:", "SUMMARY:", "FINDINGS:", "END"):
        assert header in prompt
    assert "fix:" in prompt


# --- Base tree paths and diff status -----------------------------------------


def test_base_tree_paths_list_changed_directories_first() -> None:
    request, partial = pr_review.build_request(
        base_context(base_paths=["README.md", "a/x.md", "docs/other.md", "docs/review.md"])
    )
    payload = user_payload(request)
    section = payload.split("BASE TREE PATHS", 1)[1].split("BASE FILE CONTENTS", 1)[0]
    listed = [line[2:] for line in section.splitlines() if line.startswith("- ")]
    assert listed == ["docs/other.md", "docs/review.md", "README.md", "a/x.md"]
    assert partial is False


def test_base_tree_paths_are_bounded_and_say_what_is_missing() -> None:
    paths = [f"lib/module-{number:05d}.py" for number in range(5000)]
    request, partial = pr_review.build_request(
        base_context(base_paths=paths, base_paths_truncated=True)
    )
    payload = user_payload(request)
    assert "lib/module-00000.py" in payload
    assert "lib/module-04999.py" not in payload
    assert "more paths not shown" in payload
    assert "incomplete" in payload
    assert len(payload.encode("utf-8")) < 30_000
    assert partial is False


def test_base_tree_paths_are_sanitized() -> None:
    request, _ = pr_review.build_request(
        base_context(base_paths=["docs/a\u200bb.md", "docs/<!-- HIDDEN -->c.md"])
    )
    payload = user_payload(request)
    assert "docs/ab.md" in payload
    assert "HIDDEN" not in payload


def test_an_unavailable_diff_marks_the_review_partial() -> None:
    request, partial = pr_review.build_request(base_context(diff="", diff_status="unavailable"))
    assert partial is True
    assert "diff is unavailable" in user_payload(request).lower()


def test_a_diff_truncated_upstream_marks_the_review_partial() -> None:
    _, partial = pr_review.build_request(base_context(diff_status="truncated"))
    assert partial is True


@pytest.mark.parametrize(
    "hidden",
    ["<!-- note -->", "zero\u200bwidth", "<div hidden>x</div>", "A" * 240],
)
def test_markup_removed_from_the_diff_marks_the_review_partial(hidden: str) -> None:
    # The removed part was never reviewed, so auto-merge must stay off.
    diff = f"diff --git a/docs/review.md b/docs/review.md\n+Visible {hidden}\n"
    request, partial = pr_review.build_request(base_context(diff=diff))
    assert partial is True
    assert "hidden markup was removed from the diff" in user_payload(request).lower()


def test_markup_removed_from_the_body_alone_keeps_the_review_complete() -> None:
    # Pull request templates carry HTML comments; the body is not reviewed code.
    request, partial = pr_review.build_request(base_context(body="Intro <!-- template -->"))
    assert partial is False
    assert "hidden markup was removed" not in user_payload(request).lower()


@pytest.mark.parametrize(
    "overrides",
    [
        {"diff_status": "maybe"},
        {"base_paths": "README.md"},
        {"base_paths": [1]},
        {"base_paths_truncated": None},
        {"files": [{"path": "docs/review.md", "status": "modified", "additions": None}]},
        {"files": [{"path": "docs/review.md", "additions": 1, "deletions": 0}]},
    ],
)
def test_a_malformed_context_is_rejected(overrides: dict) -> None:
    with pytest.raises(pr_review.ContextError):
        pr_review.build_request(base_context(**overrides))


# --- Caps --------------------------------------------------------------------


def test_diff_line_cap_truncates_and_marks_partial() -> None:
    calls: list[dict] = []
    context = base_context(diff="\n".join(f"+line {number}" for number in range(2500)))
    artifact = pr_review.review(context, transport=recording_transport(calls), token=FAKE_TOKEN)
    assert artifact["status"] == "ok"
    assert artifact["partial"] is True
    payload = user_payload(calls[0])
    assert "+line 0" in payload
    assert "+line 1999" in payload
    assert "+line 2000" not in payload
    assert "truncated" in payload.lower()


def test_diff_byte_cap_truncates_and_marks_partial() -> None:
    calls: list[dict] = []
    context = base_context(diff="\n".join("~" * 400 for _ in range(600)))
    artifact = pr_review.review(context, transport=recording_transport(calls), token=FAKE_TOKEN)
    assert artifact["partial"] is True
    assert len(user_payload(calls[0]).encode("utf-8")) <= pr_review.MAX_TOTAL_BYTES


def test_base_content_caps_the_file_count() -> None:
    calls: list[dict] = []
    base_files = {f"docs/file-{number:02d}.md": f"CONTENT-{number:02d}" for number in range(25)}
    artifact = pr_review.review(
        base_context(base_files=base_files),
        transport=recording_transport(calls),
        token=FAKE_TOKEN,
    )
    assert artifact["partial"] is True
    payload = user_payload(calls[0])
    assert "CONTENT-19" in payload
    assert "CONTENT-20" not in payload


def test_base_content_caps_the_total_bytes() -> None:
    calls: list[dict] = []
    base_files = {
        "docs/huge.md": "~" * 120_000,
        "docs/small.md": "SMALL-CONTENT",
    }
    artifact = pr_review.review(
        base_context(base_files=base_files),
        transport=recording_transport(calls),
        token=FAKE_TOKEN,
    )
    assert artifact["partial"] is True
    payload = user_payload(calls[0])
    assert "~" * 120_000 not in payload
    assert "SMALL-CONTENT" in payload


def test_total_payload_is_capped() -> None:
    calls: list[dict] = []
    context = base_context(
        diff="\n".join("~" * 100 for _ in range(2000)),
        base_files={f"docs/file-{number}.md": "y " * 2500 for number in range(20)},
        body="B " * 1000,
    )
    artifact = pr_review.review(context, transport=recording_transport(calls), token=FAKE_TOKEN)
    assert artifact["partial"] is True
    assert len(user_payload(calls[0]).encode("utf-8")) <= pr_review.MAX_TOTAL_BYTES


# --- Parser ------------------------------------------------------------------


def test_valid_response_parses_into_the_artifact() -> None:
    calls: list[dict] = []
    artifact = pr_review.review(
        base_context(), transport=recording_transport(calls), token=FAKE_TOKEN
    )
    assert artifact == {
        "schema_version": 1,
        "number": 42,
        "head_sha": "abc123",
        "status": "ok",
        "risk": "medium",
        "verdict": "concerns",
        "summary": (
            "The documentation change is useful but one heading no longer matches "
            "the file it describes."
        ),
        "findings": [
            {
                "path": "docs/review.md",
                "line": 12,
                "severity": "warning",
                "message": "The heading is stale",
                "suggestion": "Rename the heading",
            },
            {
                "path": "scripts/example.py",
                "line": None,
                "severity": "info",
                "message": "Minor wording",
                "suggestion": "Reflow the sentence",
            },
            {
                "path": "docs/review.md",
                "line": 20,
                "severity": "blocker",
                "message": "The link target is missing",
                "suggestion": "",
            },
        ],
        "partial": False,
        "raw": None,
    }


def test_unavailable_status_has_no_verdict() -> None:
    artifact = pr_review.review(base_context(), transport=lambda request: "", token=FAKE_TOKEN)
    assert (artifact["status"], artifact["risk"], artifact["verdict"]) == (
        "unavailable",
        "high",
        None,
    )


# --- Skip and provider failure ------------------------------------------------


def test_draft_and_fork_skip_without_calling_transport() -> None:
    for flag in ("draft", "fork"):
        calls: list[dict] = []
        artifact = pr_review.review(
            base_context(**{flag: True}), transport=recording_transport(calls), token=FAKE_TOKEN
        )
        assert artifact["status"] == "skipped", flag
        assert artifact["risk"] is None, flag
        assert artifact["verdict"] is None, flag
        assert calls == [], flag


def test_missing_token_is_unavailable_without_calling_transport(monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    calls: list[dict] = []
    artifact = pr_review.review(base_context(), transport=recording_transport(calls))
    assert (artifact["status"], artifact["risk"], artifact["verdict"]) == (
        "unavailable",
        "high",
        None,
    )
    assert calls == []


def test_provider_error_is_unavailable() -> None:
    def failing(request: dict) -> str:
        raise pr_review.ProviderError("HTTP 500")

    artifact = pr_review.review(base_context(), transport=failing, token=FAKE_TOKEN)
    assert (artifact["status"], artifact["risk"], artifact["verdict"]) == (
        "unavailable",
        "high",
        None,
    )
    assert artifact["raw"] is None


def test_timeout_is_unavailable() -> None:
    def timing_out(request: dict) -> str:
        raise TimeoutError("slow provider")

    artifact = pr_review.review(base_context(), transport=timing_out, token=FAKE_TOKEN)
    assert (artifact["status"], artifact["risk"], artifact["verdict"]) == (
        "unavailable",
        "high",
        None,
    )
