"""Tests for the pr_review.py command line: dry run, sanitizing, canned responses, exits."""

from __future__ import annotations

import json
from pathlib import Path

from pr_review_testkit import (
    VALID_RESPONSE,
    base_context,
    dry_run_request,
    run_cli,
    user_payload,
    write_context,
)

# --- Dry run -----------------------------------------------------------------


def test_dry_run_assembles_the_request(tmp_path: Path) -> None:
    context = base_context()
    request = dry_run_request(tmp_path, context)
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
    payload = user_payload(dry_run_request(tmp_path, context))
    assert "Visible intro." in payload
    assert "Visible outro." in payload
    assert "Visible line" in payload
    assert hidden not in payload
    assert "\u200b" not in payload
    assert "Fix title" in payload
    assert blob not in payload


def test_dry_run_honours_model_and_base_url_env(tmp_path: Path) -> None:
    request = dry_run_request(
        tmp_path,
        base_context(),
        PR_REVIEW_MODEL="some/other-model",
        OPENCODE_BASE_URL="https://example.test/v1/",
    )
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


def test_dry_run_prints_a_bounded_summary_without_output(tmp_path: Path) -> None:
    context = base_context(diff="\n".join("+" + "x" * 90 for _ in range(1500)))
    run = run_cli("--context", str(write_context(tmp_path, context)), "--dry-run")
    assert run.returncode == 0, run.stderr
    summary = json.loads(run.stdout)
    assert len(run.stdout) < 1000
    assert "messages" not in summary
    assert summary["model"] == "deepseek-v4.1-flash-free"
    assert summary["partial"] is False
    assert summary["output"] is None
    assert summary["user_bytes"] > 135_000


def test_output_needs_dry_run_and_a_writable_file(tmp_path: Path) -> None:
    context_path = str(write_context(tmp_path, base_context()))
    assert run_cli("--context", context_path, "--output", str(tmp_path / "r.json")).returncode == 2
    run = run_cli("--context", context_path, "--dry-run", "--output", str(tmp_path))
    assert run.returncode == 4
    assert run.stdout == ""


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
