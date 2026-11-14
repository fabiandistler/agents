#!/usr/bin/env python3
"""Render the agent-run guard settings for one run of a factory workflow.

`agent_run_settings.json` loads the PR merge guard and the default-branch push
guard. Its commands name `{{factory_dir}}`, the factory checkout outside the
target's workspace, and `{{default_branch}}`. This script fills both in,
shell-quoted, and writes the settings file that claude-code-action's `settings`
input reads. The action merges that file into the user-level
`~/.claude/settings.json`, and Claude Code still loads the target repository's
own project settings, so the guards add to the target's hooks.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

FRAGMENT = Path(__file__).resolve().parent / "agent_run_settings.json"
FACTORY_DIR_PLACEHOLDER = "{{factory_dir}}"
DEFAULT_BRANCH_PLACEHOLDER = "{{default_branch}}"

EXIT_OK = 0
EXIT_USAGE = 2

HELP_EPILOG = """\
stdout: nothing; writes the rendered settings JSON to --output.
exit codes: 0 written; 2 usage error (relative --factory-dir, empty --default-branch).

examples:
  agent_run_settings.py --factory-dir "$RUNNER_TEMP/factory" --default-branch main \\
      --output "$RUNNER_TEMP/agent-run-settings.json"
  agent_run_settings.py --help
"""


def render(factory_dir: str, default_branch: str) -> dict:
    """The fragment with every command's placeholders replaced by shell-quoted values."""
    settings = json.loads(FRAGMENT.read_text(encoding="utf-8"))
    for entry in settings["hooks"]["PreToolUse"]:
        for hook in entry["hooks"]:
            hook["command"] = (
                hook["command"]
                .replace(FACTORY_DIR_PLACEHOLDER, shlex.quote(factory_dir))
                .replace(DEFAULT_BRANCH_PLACEHOLDER, shlex.quote(default_branch))
            )
    return settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fill in the agent-run guard settings fragment.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--factory-dir", required=True, help="absolute path of the factory checkout"
    )
    parser.add_argument("--default-branch", required=True, help="the target's default branch")
    parser.add_argument("--output", required=True, type=Path, help="settings file to write")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not Path(args.factory_dir).is_absolute():
        parser.error("--factory-dir must be an absolute path")
    if not args.default_branch:
        parser.error("--default-branch must not be empty")
    settings = render(args.factory_dir, args.default_branch)
    args.output.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
