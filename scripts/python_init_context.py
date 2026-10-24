#!/usr/bin/env python3
"""Inject the Python project baseline before Claude runs `uv init`."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import NoReturn

EXIT_OK = 0
EXIT_BAD_INPUT = 3
EXIT_MISSING_BASELINE = 4
EXIT_USAGE = 5
HOOK_COMMAND_ID = "python_init_context.py"
HOOK_IF = "Bash(uv init*)"
PAYLOAD_MARKER = "<!-- managed-by: fabiandistler/agents install.sh -->"
BASELINE_MARKER = re.compile(r"^<!-- python-project-baseline:(?:start|end) -->\r?\n?", re.MULTILINE)

USAGE = """usage: python_init_context.py [--baseline PATH] [--help]

Inject the installed Python project baseline for a matching Claude PreToolUse event.
Reads the event JSON from stdin. The configured hook filters to Bash(uv init*).

  --baseline PATH  installed or project Python baseline file
  --help           show this message

exit: 0 context emitted or event ignored | 3 invalid event JSON/schema
      4 installed baseline missing/unreadable | 5 usage error
examples:
  printf '%s' '{"tool_name":"Bash","tool_input":{"command":"uv init --package demo"}}' | python3 scripts/python_init_context.py --baseline instructions/30-python.md
  printf '%s' '{"tool_name":"Bash","tool_input":{"command":"uv run pytest"}}' | python3 scripts/python_init_context.py
"""


class UsageError(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"python_init_context.py: {message}\n")
        raise SystemExit(EXIT_USAGE)


def is_hook_handler(value: object) -> bool:
    if not isinstance(value, dict) or value.get("type") != "command":
        return False
    command = value.get("command")
    return isinstance(command, str) and HOOK_COMMAND_ID in command


def without_claude_hook(settings: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(settings)
    hooks = result.get("hooks")
    if not isinstance(hooks, dict) or not isinstance(hooks.get("PreToolUse"), list):
        return result

    remaining_groups = []
    for group in hooks["PreToolUse"]:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            remaining_groups.append(group)
            continue
        remaining_handlers = [handler for handler in group["hooks"] if not is_hook_handler(handler)]
        if remaining_handlers:
            updated_group = copy.deepcopy(group)
            updated_group["hooks"] = remaining_handlers
            remaining_groups.append(updated_group)

    if remaining_groups:
        hooks["PreToolUse"] = remaining_groups
    else:
        del hooks["PreToolUse"]
        if not hooks:
            del result["hooks"]
    return result


def claude_hook_entry(command: str) -> dict[str, object]:
    return {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "if": HOOK_IF,
                "command": command,
            }
        ],
    }


def with_claude_hook(settings: dict[str, object], command: str) -> dict[str, object]:
    result = without_claude_hook(settings)
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise TypeError("settings field 'hooks' must be an object")
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre_tool_use, list):
        raise TypeError("settings field 'hooks.PreToolUse' must be a list")
    pre_tool_use.append(claude_hook_entry(command))
    return result


def context_for(event: object, baseline_path: Path) -> str | None:
    if not isinstance(event, dict):
        raise TypeError("event must be an object")
    if event.get("tool_name") != "Bash":
        return None
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        raise TypeError("event field 'tool_input' must be an object")
    command = tool_input.get("command")
    if not isinstance(command, str):
        raise TypeError("event field 'tool_input.command' must be a string")
    if not command.lstrip().startswith("uv init"):
        return None

    content = baseline_path.read_text(encoding="utf-8")
    if content.startswith(PAYLOAD_MARKER):
        content = content[len(PAYLOAD_MARKER) :].lstrip()
    if content.startswith("---\n"):
        frontmatter_end = content.find("\n---\n", 4)
        if frontmatter_end < 0:
            raise OSError("installed Python baseline has invalid frontmatter")
        content = content[frontmatter_end + len("\n---\n") :]
    content = BASELINE_MARKER.sub("", content).strip()
    if not content:
        raise OSError("installed Python baseline is empty")
    return content


def main(argv: list[str] | None = None) -> int:
    parser = UsageError(add_help=False, prog="python_init_context.py")
    parser.add_argument("--help", action="store_true", help="show this message")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path.home() / ".agents/instructions/30-python.md",
        help="installed or project Python baseline file",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.help:
        sys.stdout.write(USAGE)
        return EXIT_OK

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        sys.stderr.write("event stdin must be valid JSON\n")
        return EXIT_BAD_INPUT
    try:
        baseline = context_for(event, args.baseline)
    except (TypeError, ValueError) as exc:
        sys.stderr.write(f"invalid event: {exc}\n")
        return EXIT_BAD_INPUT
    except OSError:
        sys.stderr.write("installed Python baseline is missing or unreadable\n")
        return EXIT_MISSING_BASELINE

    if baseline is not None:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": baseline,
                }
            },
            sys.stdout,
        )
        sys.stdout.write("\n")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
