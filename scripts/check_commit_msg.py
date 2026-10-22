#!/usr/bin/env python3
"""Reject commit subjects that do not follow Conventional Commits.

The commit-msg hook in .pre-commit-config.yaml runs this with the path of the
proposed message. It runs under the system interpreter, so it stays stdlib-only
and Python 3.9-compatible.

The subject is the first line that is neither blank nor a git comment (the
hook sees the message before git strips `#` lines). Merge commits and git's
autosquash prefixes (fixup!, squash!, amend!) pass unchecked: git writes them,
and autosquash folds them into a conventional commit before it lands.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TYPES = (
    "feat",
    "fix",
    "refactor",
    "perf",
    "style",
    "test",
    "docs",
    "build",
    "ops",
    "chore",
    "ci",
    "revert",
)

CONVENTIONAL_SUBJECT = re.compile(r"^(?:" + "|".join(TYPES) + r")(?:\([^()\s]+\))?!?: \S")
GIT_GENERATED_SUBJECT = re.compile(r"^(?:Merge |(?:fixup|squash|amend)! )")

USAGE = f"""usage: check_commit_msg.py MESSAGE_FILE

Check that the commit subject (first non-blank, non-# line of MESSAGE_FILE)
reads '<type>[(scope)][!]: <description>'.
Types: {" ".join(TYPES)}.
Subjects starting with 'Merge ', 'fixup! ', 'squash! ' or 'amend! ' pass.

  -h, --help  show this message

examples:
  python3 scripts/check_commit_msg.py .git/COMMIT_EDITMSG
  prek run --hook-stage commit-msg --commit-msg-filename msg.txt

exit: 0 subject ok | 1 subject not conventional | 2 usage error or unreadable file
"""


def main(argv: list[str]) -> int:
    if argv in (["-h"], ["--help"]):
        print(USAGE, end="")
        return 0
    if len(argv) != 1 or argv[0].startswith("-"):
        print(USAGE, end="", file=sys.stderr)
        return 2
    try:
        message = Path(argv[0]).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"check_commit_msg.py: cannot read MESSAGE_FILE: {error}", file=sys.stderr)
        return 2

    subject = commit_subject(message)
    if is_valid_subject(subject):
        return 0
    print(
        "commit subject does not follow Conventional Commits: expected "
        "'<type>[(scope)][!]: <description>' with <type> one of: " + " ".join(TYPES),
        file=sys.stderr,
    )
    return 1


def commit_subject(message: str) -> str:
    """Return the first line git would keep as the subject."""
    for line in message.splitlines():
        if line.strip() and not line.startswith("#"):
            return line
    return ""


def is_valid_subject(subject: str) -> bool:
    return bool(GIT_GENERATED_SUBJECT.match(subject) or CONVENTIONAL_SUBJECT.match(subject))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
