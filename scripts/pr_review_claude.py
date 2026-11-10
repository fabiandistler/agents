"""Run one model call through the unmodified Claude Code CLI (`claude -p`).

The PR review and the issue triage both call the model here. The CLI
authenticates with the maintainer's subscription token. Anthropic permits a
subscription only inside its own binary, so the request never goes to the API
directly.

By default the CLI runs with every tool disabled, the system prompt replaced
and an empty working directory: injected text in the payload can sway the
answer but cannot run a command or read the token. With a ``workspace`` the
CLI gets only the read-only file tools (Read, Grep, Glob) in restricted mode,
which confines them to that directory and refuses process files such as
``/proc/self/environ``. An answer that echoes the token is refused either way.

Standard library only.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"  # noqa: S105 -- a variable name, not a secret
CLAUDE_COMMAND = "claude"
TIMEOUT_SECONDS = 300
MAX_REASON_CHARS = 300
# The read-only tools a workspace call gets; nothing that runs code or writes.
WORKSPACE_TOOLS = "Read,Grep,Glob"
WORKSPACE_MAX_TURNS = 40
WORKSPACE_TIMEOUT_SECONDS = 600


class ProviderError(Exception):
    """The `claude` call failed; `pr_review.review` turns it into unavailable."""


def claude_command(request: dict, read_only_tools: bool = False) -> list[str]:
    """Return the argv for one `claude -p` call.

    Without ``read_only_tools`` the call is tool-less and single-turn. With
    it, the call may read the working directory over several turns, confined
    by ``--restricted``. The user payload goes to stdin, never into argv.
    """
    system = request["messages"][0]["content"]
    # The payload is untrusted and the job holds a secret: no tool that runs
    # code, writes or reaches the network, ever.
    tools = WORKSPACE_TOOLS if read_only_tools else ""
    max_turns = WORKSPACE_MAX_TURNS if read_only_tools else 1
    command = [
        CLAUDE_COMMAND,
        "--print",
        "--output-format",
        "json",
        "--tools",
        tools,
    ]
    if read_only_tools:
        command.append("--restricted")
    return command + [
        "--system-prompt",
        system,
        "--model",
        request["model"],
        "--max-turns",
        str(max_turns),
        "--no-session-persistence",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--setting-sources",
        "",
    ]


def cli_reason(stdout: str, stderr: str) -> str:
    """Return the CLI's own error description as one bounded line.

    An error result carries the CLI's message (an expired token, a usage limit,
    an unknown model), not the review, so it is safe to log.
    """
    try:
        parsed = json.loads(stdout)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and parsed.get("is_error") is True:
        parts = [
            f"{field}={parsed[field]}"
            for field in ("subtype", "api_error_status")
            if parsed.get(field) is not None
        ]
        if isinstance(parsed.get("result"), str):
            parts.append(parsed["result"])
        text = " ".join(parts)
    else:
        lines = [line for line in stderr.splitlines() if line.strip()]
        text = lines[-1] if lines else ""
    return " ".join(text.split())[:MAX_REASON_CHARS] or "(no reason given)"


def _run_cli(
    command: list[str], payload: str, workdir: str, environment: dict, timeout: int
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603 -- fixed argv, no shell
            command,
            input=payload,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            cwd=workdir,
            env=environment,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as err:
        raise ProviderError("the claude CLI is not installed") from err
    except subprocess.TimeoutExpired as err:
        raise ProviderError("the claude CLI timed out") from err


def run_claude(request: dict, oauth_token: str, workspace: Path | None = None) -> str:
    """Return the model's answer to ``request``.

    ``workspace`` is a directory the model may read with the read-only tools;
    without one the call runs tool-less in an empty directory. Settings files,
    CLAUDE.md, hooks and MCP servers are never loaded.
    """
    environment = {**os.environ, TOKEN_ENV: oauth_token}
    payload = request["messages"][1]["content"]
    if workspace is not None:
        command = claude_command(request, read_only_tools=True)
        completed = _run_cli(
            command, payload, str(workspace), environment, WORKSPACE_TIMEOUT_SECONDS
        )
    else:
        # An empty working directory: no CLAUDE.md, settings or hooks from a checkout.
        with tempfile.TemporaryDirectory(prefix="claude-call-") as workdir:
            completed = _run_cli(
                claude_command(request), payload, workdir, environment, TIMEOUT_SECONDS
            )
    if completed.returncode != 0:
        raise ProviderError(
            f"the claude CLI exited with status {completed.returncode}: "
            f"{cli_reason(completed.stdout, completed.stderr)}"
        )
    try:
        parsed = json.loads(completed.stdout)
    except ValueError as err:
        raise ProviderError("the claude CLI output is not JSON") from err
    if not isinstance(parsed, dict) or parsed.get("is_error") is not False:
        raise ProviderError(
            f"the claude CLI reported an error: {cli_reason(completed.stdout, completed.stderr)}"
        )
    content = parsed.get("result")
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("the claude CLI returned an empty answer")
    # The answer is published; one that carries the token must never leave the job.
    if oauth_token in content:
        raise ProviderError("the claude CLI answer contains the token")
    return content
