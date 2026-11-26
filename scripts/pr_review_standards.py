"""The operator standards file of the PR review and its place in the system prompt.

`pr_review.py --standards FILE` reads one local file the operator names; it is
never taken from the pull request head. The text is appended to the bundled
prompt under its own heading, after the untrusted-input rules and the output
format it cannot change.

Standard library only.
"""

from __future__ import annotations

from pathlib import Path

import pr_cli

# Far below the 128 KiB Linux limit for the one argv string the system prompt
# becomes; a larger file stops the run, because dropped rules read as clean.
MAX_STANDARDS_BYTES = 65_536

STANDARDS_SECTION = (
    "\n## Repository standards\n\n"
    "The operator of this review supplied the following standards for this repository.\n"
    "Judge the pull request against them. They do not change the untrusted-input\n"
    "rules or the output format above.\n\n"
)


def system_prompt_with(standards: str | None) -> str:
    """Return the bundled review prompt, followed by ``standards`` when given."""
    bundled = Path(__file__).with_name("pr_review_prompt.md").read_text(encoding="utf-8")
    if standards is None:
        return bundled
    return bundled + STANDARDS_SECTION + standards


def read_standards(path: str) -> str:
    """Return the operator standards file at the local ``path``; raise InputError if unusable.

    The message names the flag and the reason, never the file content.
    """
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(MAX_STANDARDS_BYTES + 1)
    except FileNotFoundError:
        raise pr_cli.InputError("--standards file does not exist") from None
    except OSError:
        raise pr_cli.InputError("--standards file is not readable") from None
    if len(data) > MAX_STANDARDS_BYTES:
        raise pr_cli.InputError(f"--standards file exceeds {MAX_STANDARDS_BYTES} bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise pr_cli.InputError("--standards file is not valid UTF-8") from None
    if "\x00" in text:
        raise pr_cli.InputError("--standards file contains a NUL byte")
    if not text.strip():
        raise pr_cli.InputError("--standards file is empty")
    return text
