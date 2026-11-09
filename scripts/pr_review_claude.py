"""Run one PR review through the unmodified Claude Code CLI (`claude -p`).

The CLI authenticates with the maintainer's subscription token. Anthropic
permits a subscription only inside its own binary, so the request never goes
to the API directly. The CLI runs with every tool disabled, the system prompt
replaced and an empty working directory: injected text in the diff can sway
the verdict but cannot run a command or read the token.

Standard library only.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"  # noqa: S105 -- a variable name, not a secret
CLAUDE_COMMAND = "claude"
TIMEOUT_SECONDS = 300
MAX_REASON_CHARS = 300


class ProviderError(Exception):
    """The `claude` call failed; `pr_review.review` turns it into unavailable."""


def claude_command(request: dict) -> list[str]:
    """Return the argv for one tool-less, single-turn `claude -p` call.

    The user payload (up to MAX_TOTAL_BYTES) goes to stdin, never into argv.
    """
    system = request["messages"][0]["content"]
    return [
        CLAUDE_COMMAND,
        "--print",
        "--output-format",
        "json",
        # No tool at all: the payload is untrusted, and the job holds a secret.
        "--tools",
        "",
        "--system-prompt",
        system,
        "--model",
        request["model"],
        "--max-turns",
        "1",
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


def run_claude(request: dict, oauth_token: str) -> str:
    environment = {**os.environ, TOKEN_ENV: oauth_token}
    payload = request["messages"][1]["content"]
    # An empty working directory: no CLAUDE.md, settings or hooks from the checkout.
    with tempfile.TemporaryDirectory(prefix="pr-review-") as workdir:
        try:
            completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell
                claude_command(request),
                input=payload,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                cwd=workdir,
                env=environment,
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as err:
            raise ProviderError("the claude CLI is not installed") from err
        except subprocess.TimeoutExpired as err:
            raise ProviderError("the claude CLI timed out") from err
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
        raise ProviderError("the claude CLI returned an empty review")
    return content
