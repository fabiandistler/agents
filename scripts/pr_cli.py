"""The command-line conventions every pr_* script of the review pipeline shares.

The exit-code table: one code per failure class, the same number in every
script, so a caller can branch on the code without knowing which script
failed; each script's ``--help`` ends with ``exit_help`` for its codes. The
flag parser, the --pr/--repo check, and the JSON readers and writers keep the
scripts' argument and file handling identical.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from pr_github_client import REPO_PATTERN

EXIT_OK = 0
EXIT_ACTION_FAILED = 1
EXIT_USAGE = 2
EXIT_BAD_INPUT = 3
EXIT_FETCH_FAILED = 4
EXIT_MISSING_TOKEN = 5
EXIT_OUTPUT_FAILED = 6
EXIT_OUTSIDE_ACTIONS = 7
EXIT_REVIEW_UNAVAILABLE = 8

EXIT_CODES = {
    EXIT_OK: "success",
    EXIT_ACTION_FAILED: "a write action failed",
    EXIT_USAGE: "usage",
    EXIT_BAD_INPUT: "bad input file",
    EXIT_FETCH_FAILED: "GitHub fetch failed",
    EXIT_MISSING_TOKEN: "missing GITHUB_TOKEN",
    EXIT_OUTPUT_FAILED: "output file not writable",
    EXIT_OUTSIDE_ACTIONS: "--write outside GitHub Actions",
    EXIT_REVIEW_UNAVAILABLE: "review unavailable",
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


class UsageError(Exception):
    """The command line is not usable; the script prints its usage and exits 2."""


class InputError(ValueError):
    """An input file is unreadable or holds no JSON object; the script exits 3."""


def parse_flags(
    argv: list[str], values: tuple[str, ...], switches: tuple[str, ...] = ()
) -> dict[str, object] | None:
    """Parse ``--name VALUE``, ``--name=VALUE`` and the bare ``switches``.

    Returns the options keyed by flag name without dashes (``dry-run`` becomes
    ``dry_run``): None for an absent value flag, False for an absent switch.
    Returns None for -h/--help. Anything else raises ``UsageError``.
    """
    options: dict[str, object] = {_key(name): None for name in values}
    options.update({_key(name): False for name in switches})
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("-h", "--help"):
            return None
        name, separator, inline = argument.partition("=")
        if name in switches:
            if separator:
                raise UsageError(f"{name} takes no value")
            options[_key(name)] = True
            index += 1
            continue
        if name not in values:
            raise UsageError(f"unknown argument: {argument}")
        if separator:
            value = inline
            index += 1
        else:
            if index + 1 >= len(argv):
                raise UsageError(f"{name} needs a value")
            value = argv[index + 1]
            index += 2
        if not value:
            raise UsageError(f"{name} needs a value")
        options[_key(name)] = value
    return options


def _key(flag: str) -> str:
    return flag[2:].replace("-", "_")


def require_pull_request(options: dict[str, object]) -> None:
    """Check --pr and --repo in ``options``; --pr becomes an int."""
    if options["pr"] is None or options["repo"] is None:
        raise UsageError("--pr and --repo are both required")
    try:
        number = int(str(options["pr"]))
    except ValueError as error:
        raise UsageError("--pr must be a positive integer") from error
    if number <= 0:
        raise UsageError("--pr must be a positive integer")
    if not REPO_PATTERN.fullmatch(str(options["repo"])):
        raise UsageError("--repo must be OWNER/REPO")
    options["pr"] = number


def usage_failure(script: str, usage: str, error: UsageError) -> int:
    print(f"{script}: {error}", file=sys.stderr)
    print(usage, end="", file=sys.stderr)
    return EXIT_USAGE


def read_json_object(path: str, flag: str) -> dict:
    """Read the JSON object in ``path``; ``InputError`` names ``flag``."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise InputError(f"cannot read {flag}: {error}") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise InputError(f"{flag} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise InputError(f"{flag} must contain a JSON object")
    return payload


def print_json(payload: object) -> None:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def write_json_file(script: str, flag: str, path: str, payload: object) -> bool:
    """Write ``payload`` to ``path``; on failure name ``flag`` on stderr and return False."""
    try:
        Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"{script}: cannot write {flag}: {error}", file=sys.stderr)
        return False
    return True
