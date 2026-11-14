#!/usr/bin/env python3
"""Report one claude-code-action run on the job page and fail a failed run.

The agent-run workflows (implementer.yml, skill-audit.yml) ask the model to
write a short summary file. This script appends it to the step summary and
exits 1 when the summary is missing or starts with ``RUN FAILED``, so GitHub
notifies about the failed run. A failed run also prints one ``::error::``
workflow command with the summary's first line: GitHub turns it into a check
annotation, which the REST API serves and the step summary is not
(scripts/factory_failure.py reads it, ADR-0016).

A run that wrote no summary, or a failed one, also gets a diagnosis from the
action's execution file: the model's last message and a count of the tools it
called. Tool inputs and results are never printed: they can hold secrets, and
the run page of a public repository is public.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

FAILED_PREFIX = "RUN FAILED"
SUBAGENT_TOOLS = ("Agent", "Task")
# The last message is model text from a public run page; a cap keeps one
# runaway answer from filling the summary.
MAX_LAST_MESSAGE = 3000
# The annotation is one line on a public run page and a dedupe key; a cap keeps
# a long summary line from swamping either.
MAX_ANNOTATION = 300
NO_SUMMARY_LINE = f"{FAILED_PREFIX}: the model step wrote no summary"

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_USAGE = 2

HELP_EPILOG = """\
exit codes: 0 the run wrote a summary that does not start with RUN FAILED;
            1 the summary is missing or starts with RUN FAILED; 2 usage error.
stdout: on exit 1, one ::error:: line with the summary's first line (capped).

examples:
  agent_run_report.py --summary "$RUNNER_TEMP/run-summary.md" \\
      --execution-file "$EXECUTION_FILE" --output "$GITHUB_STEP_SUMMARY"
  agent_run_report.py --summary run-summary.md --output -
"""


def load_messages(execution_file: Path | None) -> list[dict] | None:
    """Return the action's message list, or None when there is none to read."""
    if execution_file is None or not execution_file.is_file():
        return None
    try:
        messages = json.loads(execution_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(messages, list):
        return None
    return [message for message in messages if isinstance(message, dict)]


def last_message(messages: list[dict]) -> str | None:
    """The text of the final result message, capped."""
    for message in reversed(messages):
        if message.get("type") == "result" and isinstance(message.get("result"), str):
            text = message["result"].strip()
            if len(text) > MAX_LAST_MESSAGE:
                text = text[:MAX_LAST_MESSAGE] + " [truncated]"
            return text
    return None


def tool_counts(messages: list[dict]) -> tuple[Counter, int]:
    """Count the model's tool calls by name, and its background subagents."""
    counts: Counter = Counter()
    background = 0
    for message in messages:
        if message.get("type") != "assistant":
            continue
        content = (message.get("message") or {}).get("content") or []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = str(block.get("name", "?"))
            counts[name] += 1
            tool_input = block.get("input") or {}
            if name in SUBAGENT_TOOLS and tool_input.get("run_in_background") is True:
                background += 1
    return counts, background


def diagnosis(messages: list[dict] | None) -> str:
    if messages is None:
        return "No execution file: the model step did not start or did not finish.\n"
    lines = []
    counts, background = tool_counts(messages)
    if counts:
        listed = ", ".join(f"{name} x{count}" for name, count in sorted(counts.items()))
        lines.append(f"Tool calls: {listed}.")
    else:
        lines.append("Tool calls: none.")
    if background:
        lines.append(
            f"{background} subagent(s) ran in the background: a headless run ends "
            "with the model's turn, which stops them."
        )
    text = last_message(messages)
    lines.append("")
    lines.append("Model's last message:")
    lines.append("")
    lines.append(text if text else "(none)")
    return "\n".join(lines) + "\n"


def build_report(summary_text: str | None, messages: list[dict] | None) -> tuple[str, int]:
    """Return the step-summary text and the exit code for one run."""
    if summary_text is None or not summary_text.strip():
        report = f"{NO_SUMMARY_LINE}\n\n" + diagnosis(messages)
        return report, EXIT_RUN_FAILED
    report = summary_text if summary_text.endswith("\n") else summary_text + "\n"
    if summary_text.lstrip().startswith(FAILED_PREFIX):
        return report + "\n" + diagnosis(messages), EXIT_RUN_FAILED
    return report, EXIT_OK


def error_annotation(summary_text: str | None) -> str | None:
    """The one ``::error::`` command for a failed run, or None for a good one."""
    if summary_text is None or not summary_text.strip():
        line = NO_SUMMARY_LINE
    elif summary_text.lstrip().startswith(FAILED_PREFIX):
        line = " ".join(summary_text.strip().splitlines()[0].split())
    else:
        return None
    if len(line) > MAX_ANNOTATION:
        line = line[:MAX_ANNOTATION] + " [truncated]"
    # Workflow-command data escaping; the line holds no CR or LF by now.
    return "::error::" + line.replace("%", "%25")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report a claude-code-action run; exit 1 if it failed.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--summary", required=True, type=Path, help="the model's summary file")
    parser.add_argument(
        "--execution-file",
        default="",
        help="the action's execution_file output; empty when the step wrote none",
    )
    parser.add_argument(
        "--output", required=True, help="file to append the report to, or - for stdout"
    )
    args = parser.parse_args(argv)

    summary_text = args.summary.read_text(encoding="utf-8") if args.summary.is_file() else None
    execution_file = Path(args.execution_file) if args.execution_file else None
    report, code = build_report(summary_text, load_messages(execution_file))
    annotation = error_annotation(summary_text)
    if annotation is not None:
        print(annotation)

    if args.output == "-":
        sys.stdout.write(report)
    else:
        with open(args.output, "a", encoding="utf-8") as handle:
            handle.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
