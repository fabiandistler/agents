"""The exit-code table every pr_* command line of the review pipeline shares.

One code per failure class, the same number in every script, so a caller can
branch on the code without knowing which script failed. Each script's
``--help`` ends with ``exit_help`` for the codes it can return.
"""

from __future__ import annotations

import textwrap

EXIT_OK = 0
EXIT_ACTION_FAILED = 1
EXIT_USAGE = 2
EXIT_BAD_INPUT = 3
EXIT_FETCH_FAILED = 4
EXIT_MISSING_TOKEN = 5
EXIT_OUTPUT_FAILED = 6
EXIT_OUTSIDE_ACTIONS = 7

EXIT_CODES = {
    EXIT_OK: "success",
    EXIT_ACTION_FAILED: "a write action failed",
    EXIT_USAGE: "usage",
    EXIT_BAD_INPUT: "bad input file",
    EXIT_FETCH_FAILED: "GitHub fetch failed",
    EXIT_MISSING_TOKEN: "missing GITHUB_TOKEN",
    EXIT_OUTPUT_FAILED: "output file not writable",
    EXIT_OUTSIDE_ACTIONS: "--write outside GitHub Actions",
}


def exit_help(*codes: int) -> str:
    """The `exit:` block of a --help text for ``codes``, wrapped to 78 columns."""
    entries = " | ".join(f"{code} {EXIT_CODES[code]}" for code in sorted(codes))
    return textwrap.fill(
        f"exit: {entries}",
        width=78,
        subsequent_indent="      ",
        break_on_hyphens=False,
        break_long_words=False,
    )
