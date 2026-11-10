"""Tests for the `claude -p` transport of pr_review.py, against a fake CLI on PATH."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pr_review
import pr_review_claude
import pytest
from pr_review_testkit import FAKE_TOKEN, VALID_RESPONSE, base_context

FAKE_CLAUDE = """\
#!{python}
import json, os, sys
record = {{
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "cwd_entries": os.listdir("."),
    "stdin": sys.stdin.read(),
    "token": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"),
}}
with open(os.environ["FAKE_CLAUDE_LOG"], "w", encoding="utf-8") as handle:
    json.dump(record, handle)
sys.stdout.write(os.environ["FAKE_CLAUDE_STDOUT"])
sys.exit(int(os.environ.get("FAKE_CLAUDE_EXIT", "0")))
"""


def result_json(text: str = VALID_RESPONSE, **overrides: object) -> str:
    result = {"type": "result", "subtype": "success", "is_error": False, "result": text}
    result.update(overrides)
    return json.dumps(result)


@pytest.fixture
def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Put a recording `claude` first on PATH; return a reader for its record."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    script.write_text(FAKE_CLAUDE.format(python=sys.executable), encoding="utf-8")
    script.chmod(0o755)
    log = tmp_path / "claude-call.json"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FAKE_CLAUDE_STDOUT", result_json())
    monkeypatch.delenv("FAKE_CLAUDE_EXIT", raising=False)
    return lambda: json.loads(log.read_text(encoding="utf-8"))


def option_value(argv: list[str], flag: str) -> str:
    assert flag in argv, f"{flag} missing from {argv}"
    return argv[argv.index(flag) + 1]


def test_the_review_runs_claude_without_tools_and_parses_the_result(fake_claude) -> None:
    artifact = pr_review.review(base_context(), token=FAKE_TOKEN)
    call = fake_claude()
    assert artifact["status"] == "ok"
    assert artifact["verdict"] == "concerns"
    argv = call["argv"]
    assert "--print" in argv
    assert option_value(argv, "--tools") == "", "the untrusted payload must reach no tool"
    assert option_value(argv, "--output-format") == "json"
    assert option_value(argv, "--max-turns") == "1"
    assert option_value(argv, "--model") == "sonnet"
    assert option_value(argv, "--setting-sources") == ""
    assert "--strict-mcp-config" in argv
    assert "untrusted" in option_value(argv, "--system-prompt").lower()
    assert call["token"] == FAKE_TOKEN


def test_the_payload_goes_to_stdin_and_the_cwd_is_empty(fake_claude) -> None:
    context = base_context()
    pr_review.review(context, token=FAKE_TOKEN)
    call = fake_claude()
    assert context["diff"].strip() in call["stdin"]
    assert all(context["diff"].strip() not in arg for arg in call["argv"])
    assert call["cwd_entries"] == []
    assert Path(call["cwd"]).resolve() != Path.cwd().resolve()


def test_the_model_env_selects_the_model(fake_claude, monkeypatch) -> None:
    monkeypatch.setenv("PR_REVIEW_MODEL", "opus")
    pr_review.review(base_context(), token=FAKE_TOKEN)
    assert option_value(fake_claude()["argv"], "--model") == "opus"


@pytest.mark.parametrize(
    ("stdout", "exit_code"),
    [
        (result_json(), "1"),
        (result_json(is_error=True, subtype="error_during_execution"), "0"),
        (result_json(text="   "), "0"),
        ("not json", "0"),
        (json.dumps({"type": "result", "result": VALID_RESPONSE}), "0"),
    ],
    ids=["nonzero-exit", "is-error", "empty-result", "not-json", "no-error-flag"],
)
def test_a_failed_claude_call_is_unavailable(
    fake_claude, monkeypatch, stdout: str, exit_code: str
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_STDOUT", stdout)
    monkeypatch.setenv("FAKE_CLAUDE_EXIT", exit_code)
    artifact = pr_review.review(base_context(), token=FAKE_TOKEN)
    assert (artifact["status"], artifact["risk"], artifact["verdict"]) == (
        "unavailable",
        "high",
        None,
    )


def test_a_failed_call_logs_the_cli_reason_to_stderr(fake_claude, monkeypatch, capsys) -> None:
    monkeypatch.setenv(
        "FAKE_CLAUDE_STDOUT",
        result_json(
            text="OAuth token has expired",
            is_error=True,
            subtype="error_during_execution",
            api_error_status=401,
        ),
    )
    monkeypatch.setenv("FAKE_CLAUDE_EXIT", "1")
    artifact = pr_review.review(base_context(), token=FAKE_TOKEN)
    logged = capsys.readouterr().err
    assert artifact["status"] == "unavailable"
    assert "exited with status 1" in logged
    assert "api_error_status=401" in logged
    assert "OAuth token has expired" in logged
    assert FAKE_TOKEN not in logged


def test_without_json_the_last_stderr_line_is_the_reason() -> None:
    reason = pr_review_claude.cli_reason("", "warning\nError: not logged in\n\n")
    assert reason == "Error: not logged in"
    assert pr_review_claude.cli_reason("", "") == "(no reason given)"
    assert len(pr_review_claude.cli_reason("", "x" * 1000)) == pr_review_claude.MAX_REASON_CHARS


def test_a_success_never_logs_the_review(fake_claude, capsys) -> None:
    pr_review.review(base_context(), token=FAKE_TOKEN)
    assert capsys.readouterr().err == ""


def test_a_missing_cli_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    artifact = pr_review.review(base_context(), token=FAKE_TOKEN)
    assert artifact["status"] == "unavailable"


def test_a_cli_timeout_is_unavailable(monkeypatch) -> None:
    def timing_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=pr_review_claude.TIMEOUT_SECONDS)

    monkeypatch.setattr(pr_review_claude.subprocess, "run", timing_out)
    artifact = pr_review.review(base_context(), token=FAKE_TOKEN)
    assert artifact["status"] == "unavailable"


def test_without_a_token_the_cli_is_never_started(fake_claude, monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    artifact = pr_review.review(base_context())
    assert artifact["status"] == "unavailable"
    with pytest.raises(FileNotFoundError):
        fake_claude()


def workspace_request() -> dict:
    return {
        "model": "sonnet",
        "messages": [
            {"role": "system", "content": "Triage the untrusted issue."},
            {"role": "user", "content": "ISSUE BODY"},
        ],
    }


def test_a_workspace_call_gets_only_the_read_tools_confined_to_it(
    fake_claude, tmp_path: Path
) -> None:
    workspace = tmp_path / "checkout"
    workspace.mkdir()
    (workspace / "README.md").write_text("repo", encoding="utf-8")
    answer = pr_review_claude.run_claude(workspace_request(), FAKE_TOKEN, workspace=workspace)
    call = fake_claude()
    argv = call["argv"]
    assert answer == VALID_RESPONSE
    assert option_value(argv, "--tools") == "Read,Grep,Glob"
    assert "--restricted" in argv, "the file tools must stay inside the workspace"
    assert option_value(argv, "--setting-sources") == "", "no settings, hooks or CLAUDE.md"
    assert "--strict-mcp-config" in argv
    assert int(option_value(argv, "--max-turns")) > 1
    assert Path(call["cwd"]).resolve() == workspace.resolve()
    assert call["stdin"] == "ISSUE BODY"


def test_a_call_without_workspace_keeps_no_tools_and_no_restricted_flag(fake_claude) -> None:
    pr_review_claude.run_claude(workspace_request(), FAKE_TOKEN)
    argv = fake_claude()["argv"]
    assert option_value(argv, "--tools") == ""
    assert "--restricted" not in argv
    assert option_value(argv, "--max-turns") == "1"


@pytest.mark.parametrize("use_workspace", [False, True], ids=["tool-less", "workspace"])
def test_an_answer_that_echoes_the_token_is_refused(
    fake_claude, monkeypatch, tmp_path: Path, use_workspace: bool
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_STDOUT", result_json(text=f"leak: {FAKE_TOKEN}"))
    with pytest.raises(pr_review_claude.ProviderError, match="contains the token") as caught:
        pr_review_claude.run_claude(
            workspace_request(), FAKE_TOKEN, workspace=tmp_path if use_workspace else None
        )
    assert FAKE_TOKEN not in str(caught.value)
