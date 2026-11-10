"""Tests for agent_run_report.py: the report of one claude-code-action run."""

import json
from pathlib import Path

import agent_run_report as report
import pytest


def _assistant(*tools: dict) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", **tool} for tool in tools]},
    }


def _write_execution(tmp_path: Path, messages) -> Path:
    path = tmp_path / "claude-execution-output.json"
    path.write_text(json.dumps(messages), encoding="utf-8")
    return path


def test_a_good_summary_passes_through_without_diagnosis():
    text, code = report.build_report("Issue #1\nPR opened", [{"type": "result", "result": "x"}])
    assert code == report.EXIT_OK
    assert text == "Issue #1\nPR opened\n"


def test_a_failed_summary_fails_and_is_diagnosed():
    messages = [
        _assistant({"name": "Bash", "input": {}}),
        {"type": "result", "result": "Claim 500"},
    ]
    text, code = report.build_report("RUN FAILED: claim (HTTP 500)\n", messages)
    assert code == report.EXIT_RUN_FAILED
    assert text.startswith("RUN FAILED: claim (HTTP 500)\n")
    assert "Claim 500" in text and "Bash x1" in text


def test_a_blank_summary_counts_as_missing():
    text, code = report.build_report("  \n", None)
    assert code == report.EXIT_RUN_FAILED
    assert "wrote no summary" in text
    assert "No execution file" in text


def test_background_subagents_are_counted_and_named():
    messages = [
        _assistant(
            {"name": "Agent", "input": {"run_in_background": True}},
            {"name": "Agent", "input": {"run_in_background": False}},
            {"name": "Task", "input": {"run_in_background": True}},
        ),
        {"type": "result", "result": "Waiting for the reviewers."},
    ]
    text, code = report.build_report(None, messages)
    assert code == report.EXIT_RUN_FAILED
    assert "Agent x2, Task x1" in text
    assert "2 subagent(s) ran in the background" in text
    assert "Waiting for the reviewers." in text


def test_tool_inputs_never_reach_the_report():
    secret_input = {"command": "echo ghs_secretvalue", "run_in_background": False}
    messages = [_assistant({"name": "Bash", "input": secret_input}), {"type": "result"}]
    text, _ = report.build_report(None, messages)
    assert "ghs_secretvalue" not in text
    assert "(none)" in text, "a result without text reads as no last message"


def test_the_last_message_is_capped():
    long_text = "x" * (report.MAX_LAST_MESSAGE + 50)
    text, _ = report.build_report(None, [{"type": "result", "result": long_text}])
    assert "[truncated]" in text
    assert "x" * (report.MAX_LAST_MESSAGE + 1) not in text


def test_an_unreadable_execution_file_reads_as_none(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert report.load_messages(broken) is None
    assert report.load_messages(_write_execution(tmp_path, {"a": 1})) is None
    assert report.load_messages(tmp_path / "missing.json") is None
    assert report.load_messages(None) is None


def test_main_appends_to_the_output_and_returns_the_exit_code(tmp_path):
    summary = tmp_path / "run-summary.md"
    summary.write_text("Audit done: 0 error\n", encoding="utf-8")
    output = tmp_path / "step-summary.md"
    output.write_text("earlier step\n", encoding="utf-8")
    code = report.main(["--summary", str(summary), "--execution-file", "", "--output", str(output)])
    assert code == report.EXIT_OK
    assert output.read_text(encoding="utf-8") == "earlier step\nAudit done: 0 error\n"


def test_main_fails_without_a_summary_file(tmp_path):
    execution = _write_execution(tmp_path, [{"type": "result", "result": "Ended early."}])
    output = tmp_path / "step-summary.md"
    code = report.main(
        [
            "--summary",
            str(tmp_path / "absent.md"),
            "--execution-file",
            str(execution),
            "--output",
            str(output),
        ]
    )
    assert code == report.EXIT_RUN_FAILED
    assert "Ended early." in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("missing_flag", ["--summary", "--output"])
def test_main_rejects_a_missing_required_flag_and_writes_nothing(tmp_path, capsys, missing_flag):
    summary = tmp_path / "run-summary.md"
    summary.write_text("Audit done: 0 error\n", encoding="utf-8")
    output = tmp_path / "step-summary.md"
    output.write_text("earlier step\n", encoding="utf-8")
    flags = {"--summary": str(summary), "--output": str(output)}
    del flags[missing_flag]
    argv = [part for flag, value in flags.items() for part in (flag, value)]

    with pytest.raises(SystemExit) as exit_info:
        report.main(argv)

    assert exit_info.value.code == report.EXIT_USAGE
    assert output.read_text(encoding="utf-8") == "earlier step\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["run-summary.md", "step-summary.md"]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert missing_flag in captured.err
