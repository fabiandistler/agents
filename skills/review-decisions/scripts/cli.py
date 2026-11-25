"""The command-line contract the review-decisions scripts share.

A script's module docstring is its help: a summary line, a blank line, a
`usage:` line, then the rest. A usage error prints the usage and exits 1. A
failure the script names raises ScriptError: one `<script>: <message>` line on
stderr and the error's own exit code, so the caller can branch on the code.
Git is only read: argv, no shell, and None when the command fails.

Imported by its siblings as `import cli`; Python puts a script's own directory
first on the path, so this works from any working directory.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

EXIT_USAGE = 1


class ScriptError(Exception):
    """A failure with its own exit code; the message names inputs, never their content."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: {message}\n")


def parser(doc: str, prog: str) -> Parser:
    """A parser whose usage and help come from the script's docstring."""
    _summary, _blank, usage, rest = doc.split("\n", 3)
    return Parser(
        prog=prog,
        usage=usage.removeprefix("usage: "),
        description=rest,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def run(prog: str, command: Callable[[], None]) -> int:
    """Run the command; turn a ScriptError into its stderr line and exit code."""
    try:
        command()
    except ScriptError as err:
        print(f"{prog}: {err}", file=sys.stderr)
        return err.code
    return 0


def git(repo: Path, *args: str) -> str | None:
    """Git's stdout for a read-only command in repo, or None when it fails."""
    proc = subprocess.run(  # noqa: S603 -- fixed Git argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None
