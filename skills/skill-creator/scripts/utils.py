"""Shared utilities for skill-creator scripts."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


# Mapping from $CODER_CLI value to the argv prefix needed to run a one-shot
# "read prompt from stdin, print response to stdout" invocation. Each backend
# is expected to:
#   - read its prompt from stdin,
#   - write the model's text response to stdout,
#   - exit 0 on success.
# Add new backends here; downstream callers don't need to change.
_CODER_CLI_BACKENDS: dict[str, list[str]] = {
    "claude": ["claude", "-p", "--output-format", "text"],
    "codex": ["codex", "exec", "--quiet", "-"],
    "opencode": ["opencode", "run", "-"],
}


def coder_cli_invoke(
    prompt: str,
    model: str | None = None,
    timeout: int = 300,
) -> str:
    """Run the configured coder CLI and return its stdout.

    Backend is selected by $CODER_CLI (default: ``claude``). The prompt is
    fed on stdin so it can embed arbitrarily large content (e.g. a whole
    SKILL.md body) without hitting argv limits.

    Raises FileNotFoundError if the configured CLI is not on $PATH, with a
    message naming both the backend and the binary it tried to launch.
    """
    backend = os.environ.get("CODER_CLI", "claude")
    if backend not in _CODER_CLI_BACKENDS:
        raise ValueError(
            f"unknown $CODER_CLI={backend!r}; supported: {', '.join(sorted(_CODER_CLI_BACKENDS))}"
        )
    cmd = list(_CODER_CLI_BACKENDS[backend])
    if model:
        cmd.extend(["--model", model])

    if shutil.which(cmd[0]) is None:
        raise FileNotFoundError(f"$CODER_CLI={backend!r} requires {cmd[0]!r} on PATH")

    # Strip CLAUDECODE so this works when nested inside a Claude Code session.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{backend} ({' '.join(cmd)}) exited {result.returncode}\nstderr: {result.stderr}"
        )
    return result.stdout


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text()
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:") :].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:") :].strip()
            # Handle YAML multiline indicators (>, |, >-, |-)
            if value in (">", "|", ">-", "|-"):
                continuation_lines: list[str] = []
                i += 1
                while i < len(frontmatter_lines) and (
                    frontmatter_lines[i].startswith("  ") or frontmatter_lines[i].startswith("\t")
                ):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content
