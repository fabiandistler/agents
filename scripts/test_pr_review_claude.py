"""Tests for the `claude -p` transport of pr_review.py, against a fake CLI on PATH."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pr_review
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


def test_a_missing_cli_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    artifact = pr_review.review(base_context(), token=FAKE_TOKEN)
    assert artifact["status"] == "unavailable"


def test_a_cli_timeout_is_unavailable(monkeypatch) -> None:
    def timing_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=pr_review.TIMEOUT_SECONDS)

    monkeypatch.setattr(pr_review.subprocess, "run", timing_out)
    artifact = pr_review.review(base_context(), token=FAKE_TOKEN)
    assert artifact["status"] == "unavailable"


def test_without_a_token_the_cli_is_never_started(fake_claude, monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    artifact = pr_review.review(base_context())
    assert artifact["status"] == "unavailable"
    with pytest.raises(FileNotFoundError):
        fake_claude()
