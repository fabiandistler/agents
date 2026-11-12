"""Read the "Blocked by" declarations of a ticket's text, free of I/O.

This module knows the formats the ticket skills write
(.claude/skills/to-tickets/SKILL.md, docs/agents/issue-tracker.md): a
``## Blocked by`` section with one entry per line, a ``Blocked by: #3, #4`` or
``**Blocked by:** #3`` line, and "None (can start immediately)".

A reference is ``#3``, ``owner/repo#3`` or a GitHub URL. A bare URL after
``Blocked by`` (``Blocked by https://github.com/owner/repo/issues/3``, also in
``<...>``) is a declaration like ``Blocked by #3``; an issue URL of this
repository resolves to its number, case-insensitively.

Parsing fails closed. An entry that names no issue of this repository (a title,
a reference to another repository, a pull request URL, an empty section, a
reference hidden in inline code) cannot be checked, so it counts as unresolved
and the ticket stays blocked; a person rewrites the entry as ``#<n>`` or removes
it. A pull request never counts as done, because the gate's only done state is
an issue closed as completed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from check_pr_issue_links import REFERENCE, markdown_prose, normalized_reference

_ANY_HEADING = re.compile(r"^ {0,3}#{1,6}\s")
_BLOCKED_BY_HEADING = re.compile(r"^ {0,3}#{1,6}\s*blocked[ -]by\s*:?\s*#*\s*$", re.IGNORECASE)
_BLOCKED_BY_LINE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?blocked[ -]by"
    r"(?P<marker>(?:\*\*|__|\s*:)*)\s*(?P<value>.*)$",
    re.IGNORECASE,
)
_ENTRY_DECORATION = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)])\s+)?(?:\[[ xX]\]\s+)?")
_NO_BLOCKERS = re.compile(r"none(?:\s*\(can start immediately\))?", re.IGNORECASE)
# REFERENCE knows issue URLs only; a pull request URL is still a reference here,
# so that "Blocked by <pull URL>" declares a blocker instead of reading as prose.
_PULL_REQUEST_URL = r"https://github\.com/[\w.-]+/[\w.-]+/pull/[1-9]\d*"
_BLOCKER_REFERENCE = rf"(?:{_PULL_REQUEST_URL}|{REFERENCE})"


@dataclass(frozen=True)
class DeclaredBlockers:
    """Same-repository issue numbers, and how many entries could not be resolved."""

    numbers: frozenset[int]
    unresolved: int


def declared_blockers(ticket_text: str, repo: str) -> DeclaredBlockers:
    """Every blocker one ticket text declares; code and HTML comments declare nothing."""
    same_repo_prefix = f"{repo.lower()}#"
    numbers: set[int] = set()
    unresolved = 0
    for entry in _blocker_entries(markdown_prose(ticket_text)):
        references = re.findall(_BLOCKER_REFERENCE, entry, flags=re.IGNORECASE)
        if not references and not _says_no_blockers(entry):
            unresolved += 1
        for reference in references:
            normalized = normalized_reference(reference, repo)
            if re.fullmatch(_PULL_REQUEST_URL, reference, flags=re.IGNORECASE):
                unresolved += 1
            elif normalized.startswith(same_repo_prefix):
                numbers.add(int(normalized[len(same_repo_prefix) :]))
            else:
                unresolved += 1
    return DeclaredBlockers(frozenset(numbers), unresolved)


def _blocker_entries(prose: str) -> list[str]:
    """The raw entries of every declaration; a declaration without one yields ``""``."""
    lines = prose.splitlines()
    entries: list[str] = []
    for index, line in enumerate(lines):
        following = lines[index + 1 :]
        if _BLOCKED_BY_HEADING.match(line):
            entries += _block_entries(following, ends_at_blank_line=False)
        elif (declaration := _BLOCKED_BY_LINE.match(line)) and _is_declaration(declaration):
            value = declaration["value"]
            entries += [value] if value.strip() else _block_entries(following, True)
    return entries


def _is_declaration(line: re.Match[str]) -> bool:
    """A colon or closing bold marks a label; bare prose must lead with a reference."""
    leading_reference = rf"<?{_BLOCKER_REFERENCE}"
    return (
        bool(line["marker"])
        or re.match(leading_reference, line["value"], re.IGNORECASE) is not None
    )


def _block_entries(following: list[str], ends_at_blank_line: bool) -> list[str]:
    block: list[str] = []
    for line in following:
        if _ANY_HEADING.match(line):
            break
        if line.strip():
            block.append(line)
        elif ends_at_blank_line and block:
            break
    return block or [""]


def _says_no_blockers(entry: str) -> bool:
    return _NO_BLOCKERS.fullmatch(_ENTRY_DECORATION.sub("", entry).strip(" \t*_\"'.")) is not None
