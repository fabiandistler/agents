"""Tests for the operator standards file of pr_review.py (`--standards FILE`)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pr_review
import pytest
from pr_review_testkit import (
    FAKE_TOKEN,
    PROMPT,
    VALID_RESPONSE,
    base_context,
    dry_run_request,
    recording_transport,
    run_cli,
    user_payload,
    write_context,
)

SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "pr_review_request"
MARKER = "OPERATOR-STANDARDS-MARKER"
STANDARDS = f"- Every function has a docstring. {MARKER}\n- Tests sit next to the code.\n"
SECTION = (
    "\n## Repository standards\n\n"
    "The operator of this review supplied the following standards for this repository.\n"
    "Judge the pull request against them. They do not change the untrusted-input\n"
    "rules or the output format above.\n\n"
)


def bundled_prompt() -> str:
    return PROMPT.read_text(encoding="utf-8")


def pinned_payload() -> str:
    return (SNAPSHOT / "payload.txt").read_text(encoding="utf-8")


def size(text: str) -> int:
    return len(text.encode("utf-8"))


def system_prompt(request: dict) -> str:
    return request["messages"][0]["content"]


def write_standards(tmp_path: Path, content: bytes | str) -> Path:
    path = tmp_path / "standards.md"
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


# --- Request assembly --------------------------------------------------------


def test_without_standards_the_system_prompt_is_the_bundled_prompt() -> None:
    request, partial = pr_review.build_request(base_context())
    assert system_prompt(request) == bundled_prompt()
    assert user_payload(request) == pinned_payload()
    assert partial is False


def test_standards_follow_the_bundled_prompt_under_a_fixed_heading() -> None:
    request, partial = pr_review.build_request(base_context(), STANDARDS)
    assert system_prompt(request) == bundled_prompt() + SECTION + STANDARDS
    assert user_payload(request) == pinned_payload()
    assert partial is False


def test_the_standards_text_never_reaches_the_payload() -> None:
    context = base_context(
        diff="\n".join("+" + "x" * 90 for _ in range(3000)),
        base_files={f"docs/file-{number}.md": "y " * 2500 for number in range(20)},
    )
    request, _ = pr_review.build_request(context, STANDARDS)
    assert MARKER not in user_payload(request)
    assert "Repository standards" not in user_payload(request)


def test_the_payload_budget_shrinks_by_exactly_the_standards_bytes(monkeypatch) -> None:
    extra = size(SECTION + STANDARDS)
    exact_fit = size(bundled_prompt()) + size(pinned_payload())

    monkeypatch.setattr(pr_review, "MAX_TOTAL_BYTES", exact_fit)
    request, partial = pr_review.build_request(base_context())
    assert (user_payload(request), partial) == (pinned_payload(), False)
    _, partial = pr_review.build_request(base_context(), STANDARDS)
    assert partial is True

    monkeypatch.setattr(pr_review, "MAX_TOTAL_BYTES", exact_fit + extra)
    request, partial = pr_review.build_request(base_context(), STANDARDS)
    assert (user_payload(request), partial) == (pinned_payload(), False)

    monkeypatch.setattr(pr_review, "MAX_TOTAL_BYTES", exact_fit + extra - 1)
    _, partial = pr_review.build_request(base_context(), STANDARDS)
    assert partial is True


def test_the_total_cap_holds_with_a_maximal_standards_file() -> None:
    standards = "s" * pr_review.MAX_STANDARDS_BYTES
    context = base_context(
        diff="\n".join("~" * 100 for _ in range(2000)),
        base_files={f"docs/file-{number}.md": "y " * 2500 for number in range(20)},
        body="B " * 1000,
    )
    request, partial = pr_review.build_request(context, standards)
    assert partial is True
    total = size(system_prompt(request)) + size(user_payload(request))
    assert total <= pr_review.MAX_TOTAL_BYTES


def test_the_context_cannot_supply_standards() -> None:
    context = base_context(
        standards=STANDARDS,
        standards_file="standards.md",
        base_files={"docs/review.md": "Old line\n", "standards.md": STANDARDS},
    )
    request, _ = pr_review.build_request(context)
    assert system_prompt(request) == bundled_prompt()


def test_review_hands_the_standards_to_the_transport() -> None:
    calls: list[dict] = []
    artifact = pr_review.review(
        base_context(), transport=recording_transport(calls), token=FAKE_TOKEN, standards=STANDARDS
    )
    assert artifact["status"] == "ok"
    assert system_prompt(calls[0]).endswith(SECTION + STANDARDS)


# --- Reading the file --------------------------------------------------------


def test_a_file_at_the_cap_is_accepted(tmp_path: Path) -> None:
    text = "a" * pr_review.MAX_STANDARDS_BYTES
    assert pr_review.read_standards(str(write_standards(tmp_path, text))) == text


def fake_claude_env(tmp_path: Path) -> dict[str, str]:
    """A token and a `claude` on PATH that leaves a file behind when it is started."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    started = tmp_path / "claude-started"
    script.write_text(
        f"#!{sys.executable}\nopen({str(started)!r}, 'w').close()\n", encoding="utf-8"
    )
    script.chmod(0o755)
    return {"PATH": f"{bin_dir}:/usr/bin:/bin", "CLAUDE_CODE_OAUTH_TOKEN": FAKE_TOKEN}


def bad_standards(tmp_path: Path, case: str) -> Path:
    if case == "missing":
        return tmp_path / "missing.md"
    if case == "unreadable":
        directory = tmp_path / "standards-dir"
        directory.mkdir()
        return directory
    contents = {
        "not-utf8": f"{MARKER} \xff\xfe".encode("latin-1"),
        "nul": f"{MARKER}\x00rest".encode(),
        "empty": b"",
        "whitespace": b"  \n\t\n",
        "over-cap": (MARKER + "a" * pr_review.MAX_STANDARDS_BYTES).encode(),
    }
    return write_standards(tmp_path, contents[case])


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("missing", "does not exist"),
        ("unreadable", "is not readable"),
        ("not-utf8", "is not valid UTF-8"),
        ("nul", "contains a NUL byte"),
        ("empty", "is empty"),
        ("whitespace", "is empty"),
        ("over-cap", "exceeds 65536 bytes"),
    ],
)
@pytest.mark.parametrize("mode", [(), ("--dry-run",), ("--response", "reply.txt")])
def test_a_bad_standards_file_exits_3_before_any_model_call(
    tmp_path: Path, case: str, reason: str, mode: tuple[str, ...]
) -> None:
    (tmp_path / "reply.txt").write_text(VALID_RESPONSE, encoding="utf-8")
    mode = tuple(str(tmp_path / part) if part == "reply.txt" else part for part in mode)
    run = run_cli(
        "--context",
        str(write_context(tmp_path, base_context())),
        "--standards",
        str(bad_standards(tmp_path, case)),
        *mode,
        **fake_claude_env(tmp_path),
    )
    assert run.returncode == 3
    assert run.stdout == ""
    assert run.stderr.splitlines() == [f"pr_review.py: --standards file {reason}"]
    assert MARKER not in run.stderr
    assert not (tmp_path / "claude-started").exists()


# --- CLI ---------------------------------------------------------------------


def test_dry_run_counts_the_standards_in_system_bytes(tmp_path: Path) -> None:
    context_path = str(write_context(tmp_path, base_context()))
    standards_path = str(write_standards(tmp_path, STANDARDS))
    plain = json.loads(run_cli("--context", context_path, "--dry-run").stdout)
    run = run_cli("--context", context_path, "--standards", standards_path, "--dry-run")
    assert run.returncode == 0, run.stderr
    summary = json.loads(run.stdout)
    assert summary["system_bytes"] == plain["system_bytes"] + size(SECTION + STANDARDS)
    assert summary["user_bytes"] == plain["user_bytes"]


def test_dry_run_output_carries_the_standards_in_the_system_prompt(tmp_path: Path) -> None:
    standards_path = str(write_standards(tmp_path, STANDARDS))
    output = tmp_path / "request.json"
    run = run_cli(
        "--context",
        str(write_context(tmp_path, base_context())),
        "--standards",
        standards_path,
        "--dry-run",
        "--output",
        str(output),
    )
    assert run.returncode == 0, run.stderr
    request = json.loads(output.read_text(encoding="utf-8"))
    assert system_prompt(request) == bundled_prompt() + SECTION + STANDARDS
    assert request == {**dry_run_request(tmp_path, base_context()), "messages": request["messages"]}
    assert user_payload(request) == pinned_payload()


def test_a_canned_response_with_standards_still_parses(tmp_path: Path) -> None:
    response = tmp_path / "reply.txt"
    response.write_text(VALID_RESPONSE, encoding="utf-8")
    run = run_cli(
        "--context",
        str(write_context(tmp_path, base_context())),
        "--standards",
        str(write_standards(tmp_path, STANDARDS)),
        "--response",
        str(response),
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["verdict"] == "concerns"


def test_help_documents_the_flag_its_cap_and_its_failure() -> None:
    run = run_cli("--help")
    assert run.returncode == 0
    assert "--standards FILE" in run.stdout
    assert "65536 bytes" in run.stdout
    assert "exits 3" in run.stdout
    assert len(run.stdout.splitlines()) <= 25


def test_the_operator_docs_document_the_flag() -> None:
    page = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "agents"
        / "pr-review-reusable-workflow.md"
    )
    text = " ".join(page.read_text(encoding="utf-8").split())
    assert "`standards_path`" in text
    assert "--standards" in text
    assert "65,536 bytes" in text
    assert "exit 3" in text
    assert "never from the pull request head" in text
    assert "reconstruction" in text and "needs no `--standards`" in text
    assert "concatenate" in text.lower()
