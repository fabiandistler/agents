"""Shared utilities for skill-creator scripts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

# The only shape the trigger-eval tools accept. Kept in one place so every
# error message names the same format.
EVAL_SET_SHAPE = '[{"query": "...", "should_trigger": true}, ...]'


class EvalSetFormatError(ValueError):
    """Raised when an eval set does not match the trigger-eval shape."""


def _describe(value: object) -> str:
    """Short, human-readable name for a JSON value's type."""
    return {
        dict: "object",
        list: "array",
        str: "string",
        bool: "boolean",
        int: "number",
        float: "number",
        type(None): "null",
    }.get(type(value), type(value).__name__)


def validate_eval_set(eval_set: object, source: str | None = None) -> list[dict]:
    """Check that ``eval_set`` is a trigger-eval array and return it.

    The trigger-eval tools expect a flat array of ``{"query", "should_trigger"}``
    objects. A common mistake is passing a skill's ``evals/evals.json``, which
    wraps its cases in a ``{"skill_name": ..., "evals": [...]}`` object; that
    used to blow up deep inside the runner with ``TypeError: string indices
    must be integers``. Raise :class:`EvalSetFormatError` naming the expected
    shape instead.
    """
    where = f" in {source}" if source else ""

    if isinstance(eval_set, dict):
        if isinstance(eval_set.get("evals"), list):
            raise EvalSetFormatError(
                f"eval set{where} is the two-level object shape"
                ' ({"skill_name": ..., "evals": [...]}), which this tool does not'
                f" accept. Pass the trigger-eval array directly: {EVAL_SET_SHAPE}"
            )
        raise EvalSetFormatError(
            f"eval set{where} is a JSON object; expected an array: {EVAL_SET_SHAPE}"
        )

    if not isinstance(eval_set, list):
        raise EvalSetFormatError(
            f"eval set{where} is a JSON {_describe(eval_set)}; expected an array: {EVAL_SET_SHAPE}"
        )

    if not eval_set:
        raise EvalSetFormatError(
            f"eval set{where} is empty; expected at least one {EVAL_SET_SHAPE}"
        )

    for idx, item in enumerate(eval_set):
        prefix = f"eval set{where} item {idx}"
        if not isinstance(item, dict):
            raise EvalSetFormatError(
                f"{prefix} is a {_describe(item)}; expected an object: {EVAL_SET_SHAPE}"
            )
        if "query" not in item:
            raise EvalSetFormatError(f'{prefix} is missing "query": {EVAL_SET_SHAPE}')
        if not isinstance(item["query"], str) or not item["query"].strip():
            raise EvalSetFormatError(f'{prefix} needs a non-empty string "query": {EVAL_SET_SHAPE}')
        if "should_trigger" not in item:
            raise EvalSetFormatError(f'{prefix} is missing "should_trigger": {EVAL_SET_SHAPE}')
        if not isinstance(item["should_trigger"], bool):
            raise EvalSetFormatError(
                f'{prefix} has a non-boolean "should_trigger": {EVAL_SET_SHAPE}'
            )

    return eval_set


def load_eval_set(path: Path) -> list[dict]:
    """Read and validate an eval-set JSON file.

    Raises :class:`EvalSetFormatError` for unreadable, malformed, or
    wrongly-shaped files so callers can report one kind of failure.
    """
    try:
        raw = path.read_text()
    except OSError as exc:
        raise EvalSetFormatError(f"cannot read eval set {path}: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvalSetFormatError(f"eval set {path} is not valid JSON: {exc}") from exc

    return validate_eval_set(parsed, source=str(path))


# Mapping from $CODER_CLI value to the argv prefix needed to run a one-shot
# "read prompt from stdin, print response to stdout" invocation. Each backend
# is expected to:
#   - read its prompt from stdin,
#   - write the model's text response to stdout,
#   - exit 0 on success.
# `codex exec` prints only the final agent message to stdout (progress goes to
# stderr) and needs --skip-git-repo-check because callers may run outside a
# git repository. Add new backends here; downstream callers don't need to
# change.
_CODER_CLI_BACKENDS: dict[str, list[str]] = {
    "claude": ["claude", "-p", "--output-format", "text"],
    "codex": ["codex", "exec", "--skip-git-repo-check", "-"],
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

    ``model`` is passed through as ``--model`` (all backends accept it), but
    the ID format differs per backend: ``claude-*`` IDs for claude, Codex
    model names (e.g. ``gpt-*``) for codex, and ``provider/model`` for
    opencode.

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
