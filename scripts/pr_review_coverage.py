"""What a pull request review request leaves out, and the notes that say so.

``pr_review.py`` caps the diff and the payload; this module caps the base
contents at the limit shared with the fetcher, and turns what the caps removed
into an ``InputCoverage`` and into the notes at the top of the payload. A note
names files: the last one shown in full and those not shown in full after a
diff cut, and every changed file sent without its base content, including
files the fetcher (``pr_github.py``) skipped.
"""

from __future__ import annotations

from pr_github import BASE_BYTES_LIMIT, BASE_FILE_LIMIT, wants_base_content
from pr_review_response import InputCoverage, name_paths
from pr_review_sanitize import sanitize_text, single_line

TRUNCATION_PREFIX = "TRUNCATION:"
DIFF_CUT_LINE = (
    f"{TRUNCATION_PREFIX} The diff was truncated to fit the review limits. The parts not shown\n"
    "cannot be reviewed; do not assume the shown code is complete."
)
DIFF_UNAVAILABLE_LINE = (
    f"{TRUNCATION_PREFIX} The diff is unavailable; only the file list is known.\n"
    "Do not assume any change is complete."
)
TEXT_CUT_NOTE = (
    f"{TRUNCATION_PREFIX} The pull request title or body was cut to fit the review limits.\n"
    "The diff is not affected."
)
BASE_MISSING_LINE = (
    "BASE CONTENT: These changed files are sent without their base content, because it\n"
    "did not fit the review limits or could not be fetched; their unchanged lines are\n"
    "not shown:"
)
SANITIZED_NOTE = (
    "SANITIZED: Hidden markup was removed from the diff (HTML comments, hidden elements,\n"
    "zero-width characters or base64 blobs). The removed parts cannot be reviewed."
)


def cap_base_files(base_files: dict) -> list[tuple[str, str]]:
    """The base contents in context order, within the cap shared with ``pr_github.py``."""
    entries: list[tuple[str, str]] = []
    used = 0
    for raw_path, raw_content in base_files.items():
        path = single_line(str(raw_path), 300)
        content = sanitize_text(raw_content if isinstance(raw_content, str) else "")
        size = len(content.encode("utf-8"))
        if len(entries) >= BASE_FILE_LIMIT or used + size > BASE_BYTES_LIMIT:
            continue
        entries.append((path, content))
        used += size
    return entries


def _diff_header(item: dict) -> str:
    renamed_from = item.get("renamed_from")
    source = renamed_from if isinstance(renamed_from, str) and renamed_from else item["path"]
    return f"diff --git a/{source} b/{item['path']}"


def diff_coverage(files: list[dict], shown_diff: str) -> tuple[str | None, tuple[str, ...]]:
    """The last file shown in full in a cut ``shown_diff``, and the files not shown in full.

    The last file section in a cut diff counts as not shown in full; a file
    whose header is not found (a path git quotes) counts as not shown.
    """
    headers = [line for line in shown_diff.splitlines() if line.startswith("diff --git ")]
    path_by_header = {_diff_header(item): item["path"] for item in files}
    in_full = [path_by_header[header] for header in headers[:-1] if header in path_by_header]
    shown = set(in_full)
    not_in_full = tuple(item["path"] for item in files if item["path"] not in shown)
    return (in_full[-1] if in_full else None), not_in_full


def _payload_path(path: str) -> str:
    return single_line(path, 300)


def coverage_notes(coverage: InputCoverage, diff_unavailable: bool) -> list[str]:
    notes = []
    if coverage.diff_cut:
        lines = [DIFF_UNAVAILABLE_LINE if diff_unavailable else DIFF_CUT_LINE]
        if not diff_unavailable:
            last = coverage.diff_last_full_file
            lines.append(f"Last file shown in full: {_payload_path(last) if last else '(none)'}.")
        if coverage.diff_files_not_in_full:
            named = name_paths(coverage.diff_files_not_in_full, _payload_path)
            lines.append(f"Not shown in full: {named}.")
        notes.append("\n".join(lines))
    if coverage.diff_markup_removed:
        notes.append(SANITIZED_NOTE)
    if coverage.base_content_missing:
        lines = [BASE_MISSING_LINE, name_paths(coverage.base_content_missing, _payload_path) + "."]
        if not coverage.partial:
            lines.append("The diff is complete.")
        notes.append("\n".join(lines))
    return notes


def missing_base_content(context: dict, base_entries: list[tuple[str, str]]) -> tuple[str, ...]:
    """Changed files the fetcher would send base content for that the payload lacks."""
    sent = {path for path, _ in base_entries}
    return tuple(
        item["path"]
        for item in context["files"]
        if wants_base_content(item) and single_line(item["path"], 300) not in sent
    )
