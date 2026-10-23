"""Tests for scripts/pr_review.py: request assembly, sanitizing, caps, parser, CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pr_review

SCRIPT = Path(__file__).resolve().parent / "pr_review.py"
PROMPT = Path(__file__).resolve().parent / "pr_review_prompt.md"

VALID_RESPONSE = """\
RISK: medium
VERDICT: concerns
SUMMARY: The documentation change is useful but one heading no
longer matches the file it describes.

FINDINGS:
- docs/review.md:12 [warning] The heading is stale | fix: Rename the heading
* scripts/example.py [info] Minor wording | fix: Reflow the sentence
- docs/review.md:20 [blocker] The link target is missing
END
"""


def base_context(**overrides: object) -> dict:
    context = {
        "schema_version": 1,
        "repo": "fabiandistler/agents",
        "number": 42,
        "title": "Document the review bot",
        "body": "A short body.",
        "author": "fabiandistler",
        "head_sha": "abc123",
        "head_ref": "feat/x",
        "base_ref": "main",
        "default_branch": "main",
        "draft": False,
        "fork": False,
        "mergeable": True,
        "labels": [],
        "files": [
            {
                "path": "docs/review.md",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
                "binary": False,
                "renamed_from": None,
            }
        ],
        "diff": "diff --git a/docs/review.md b/docs/review.md\n+New line\n",
        "base_files": {"docs/review.md": "Old line\n"},
        "comments": [],
        "checks": {},
        "reviews": {"changes_requested": False},
    }
    context.update(overrides)
    return context


def recording_transport(calls: list[dict], response: str = VALID_RESPONSE):
    def transport(request: dict) -> str:
        calls.append(request)
        return response

    return transport


def user_payload(request: dict) -> str:
    return request["messages"][1]["content"]


def run_cli(*args: str, **env: str) -> subprocess.CompletedProcess:
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"OPENCODE_API_KEY", "PR_REVIEW_MODEL", "OPENCODE_BASE_URL"}
    }
    clean_env.update(env)
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )


def write_context(tmp_path: Path, context: dict) -> Path:
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context), encoding="utf-8")
    return path


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


# --- Request assembly --------------------------------------------------------


def test_dry_run_assembles_the_request(tmp_path: Path) -> None:
    context = base_context()
    run = run_cli("--context", str(write_context(tmp_path, context)), "--dry-run")
    assert run.returncode == 0, run.stderr
    assert run.stderr == ""
    request = json.loads(run.stdout)
    assert set(request) == {"url", "model", "messages"}
    assert request["url"] == "https://opencode.ai/zen/v1/chat/completions"
    assert request["model"] == "deepseek-v4.1-flash-free"
    assert [message["role"] for message in request["messages"]] == ["system", "user"]
    payload = user_payload(request)
    assert context["title"] in payload
    assert context["body"] in payload
    assert context["diff"].strip() in payload
    assert "docs/review.md" in payload and "modified" in payload
    assert "Old line" in payload


def test_dry_run_strips_untrusted_markup(tmp_path: Path) -> None:
    hidden = "HIDDEN-INSTRUCTION"
    blob = "A" * 240
    context = base_context(
        title="Fix\u200b title",
        body=(
            "Visible intro.\n"
            f"<!-- {hidden}-comment -->\n"
            f'<div style="display: none">{hidden}-display</div>\n'
            f'<span style="visibility:hidden">{hidden}-visibility</span>\n'
            f"<div hidden>{hidden}-attribute</div>\n"
            f"Payload: {blob}\n"
            "Visible outro.\n"
            f'<div style="display:none">{hidden}-unclosed'
        ),
        diff=(
            f"diff --git a/docs/review.md b/docs/review.md\n+Visible line\n<!-- {hidden}-diff -->\n"
        ),
        base_files={"docs/review.md": f"Old line\n<!-- {hidden}-base -->\n"},
    )
    run = run_cli("--context", str(write_context(tmp_path, context)), "--dry-run")
    assert run.returncode == 0, run.stderr
    payload = user_payload(json.loads(run.stdout))
    assert "Visible intro." in payload
    assert "Visible outro." in payload
    assert "Visible line" in payload
    assert hidden not in payload
    assert "\u200b" not in payload
    assert "Fix title" in payload
    assert blob not in payload


def test_dry_run_honours_model_and_base_url_env(tmp_path: Path) -> None:
    context_path = write_context(tmp_path, base_context())
    run = run_cli(
        "--context",
        str(context_path),
        "--dry-run",
        PR_REVIEW_MODEL="some/other-model",
        OPENCODE_BASE_URL="https://example.test/v1/",
    )
    assert run.returncode == 0, run.stderr
    request = json.loads(run.stdout)
    assert request["model"] == "some/other-model"
    assert request["url"] == "https://example.test/v1/chat/completions"


def test_dry_run_never_echoes_the_api_key(tmp_path: Path) -> None:
    context_path = write_context(tmp_path, base_context())
    run = run_cli(
        "--context",
        str(context_path),
        "--dry-run",
        OPENCODE_API_KEY="sk-test-secret-value",
    )
    assert run.returncode == 0, run.stderr
    assert "sk-test-secret-value" not in run.stdout
    assert "sk-test-secret-value" not in run.stderr


# --- Caps --------------------------------------------------------------------


def test_diff_line_cap_truncates_and_marks_partial() -> None:
    calls: list[dict] = []
    context = base_context(diff="\n".join(f"+line {number}" for number in range(2500)))
    artifact = pr_review.review(context, transport=recording_transport(calls), key="test-key")
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
    artifact = pr_review.review(context, transport=recording_transport(calls), key="k")
    assert artifact["partial"] is True
    assert len(user_payload(calls[0]).encode("utf-8")) <= pr_review.MAX_TOTAL_BYTES


def test_base_content_caps_the_file_count() -> None:
    calls: list[dict] = []
    base_files = {f"docs/file-{number:02d}.md": f"CONTENT-{number:02d}" for number in range(25)}
    artifact = pr_review.review(
        base_context(base_files=base_files),
        transport=recording_transport(calls),
        key="k",
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
        key="k",
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
    artifact = pr_review.review(context, transport=recording_transport(calls), key="k")
    assert artifact["partial"] is True
    assert len(user_payload(calls[0]).encode("utf-8")) <= pr_review.MAX_TOTAL_BYTES


# --- Parser ------------------------------------------------------------------


def test_valid_response_parses_into_the_artifact() -> None:
    calls: list[dict] = []
    artifact = pr_review.review(base_context(), transport=recording_transport(calls), key="k")
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
    artifact = pr_review.parse_response(response, base_context())
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
    artifact = pr_review.parse_response(response, base_context())
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
        artifact = pr_review.parse_response(response, base_context())
        assert artifact["status"] == "ok", response
        assert artifact["risk"] == "high", response
        assert artifact["verdict"] == "concerns", response
        assert artifact["raw"] == response, response
        assert artifact["findings"] == [], response


def test_unavailable_status_has_no_verdict() -> None:
    artifact = pr_review.review(base_context(), transport=lambda request: "", key="k")
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
            base_context(**{flag: True}), transport=recording_transport(calls), key="k"
        )
        assert artifact["status"] == "skipped", flag
        assert artifact["risk"] is None, flag
        assert artifact["verdict"] is None, flag
        assert calls == [], flag


def test_missing_key_is_unavailable_without_calling_transport(monkeypatch) -> None:
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
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

    artifact = pr_review.review(base_context(), transport=failing, key="k")
    assert (artifact["status"], artifact["risk"], artifact["verdict"]) == (
        "unavailable",
        "high",
        None,
    )
    assert artifact["raw"] is None


def test_timeout_is_unavailable() -> None:
    def timing_out(request: dict) -> str:
        raise TimeoutError("slow provider")

    artifact = pr_review.review(base_context(), transport=timing_out, key="k")
    assert (artifact["status"], artifact["risk"], artifact["verdict"]) == (
        "unavailable",
        "high",
        None,
    )


# --- CLI contract -------------------------------------------------------------


def test_cli_parses_a_canned_response(tmp_path: Path) -> None:
    context_path = write_context(tmp_path, base_context())
    response_path = tmp_path / "response.txt"
    response_path.write_text(VALID_RESPONSE, encoding="utf-8")
    run = run_cli("--context", str(context_path), "--response", str(response_path))
    assert run.returncode == 0, run.stderr
    artifact = json.loads(run.stdout)
    assert artifact["status"] == "ok"
    assert artifact["verdict"] == "concerns"


def test_cli_missing_key_prints_unavailable_and_exits_0(tmp_path: Path) -> None:
    context_path = write_context(tmp_path, base_context())
    run = run_cli("--context", str(context_path))
    assert run.returncode == 0, run.stderr
    artifact = json.loads(run.stdout)
    assert artifact["status"] == "unavailable"
    assert artifact["risk"] == "high"
    assert artifact["verdict"] is None


def test_cli_draft_without_key_is_skipped_and_exits_0(tmp_path: Path) -> None:
    context_path = write_context(tmp_path, base_context(draft=True))
    run = run_cli("--context", str(context_path))
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["status"] == "skipped"


def test_cli_bad_context_exits_3(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    path.write_text('{"schema_version": 1, "number": 42}', encoding="utf-8")
    run = run_cli("--context", str(path), "--dry-run")
    assert run.returncode == 3
    assert run.stdout == ""
    assert "head_sha" in run.stderr


def test_cli_unreadable_response_exits_3(tmp_path: Path) -> None:
    context_path = write_context(tmp_path, base_context())
    run = run_cli("--context", str(context_path), "--response", str(tmp_path / "missing"))
    assert run.returncode == 3
    assert run.stdout == ""


def test_cli_rejects_dry_run_with_response(tmp_path: Path) -> None:
    context_path = write_context(tmp_path, base_context())
    run = run_cli(
        "--context",
        str(context_path),
        "--dry-run",
        "--response",
        str(tmp_path / "response.txt"),
    )
    assert run.returncode == 2


def test_cli_help_is_short_and_names_exit_codes() -> None:
    run = run_cli("--help")
    assert run.returncode == 0
    assert "Exit:" in run.stdout
    assert "Examples:" in run.stdout
    assert len(run.stdout.splitlines()) <= 25
