"""Tests for the caps of scripts/pr_review.py: what is cut, what is named, what is partial."""

from __future__ import annotations

import pr_github
import pr_review
import pr_review_coverage
from pr_review_testkit import (
    FAKE_TOKEN,
    base_context,
    changed_file,
    overfull_context,
    recording_transport,
    user_payload,
)

# --- Caps --------------------------------------------------------------------


def test_diff_line_cap_truncates_and_marks_partial() -> None:
    calls: list[dict] = []
    context = base_context(diff="\n".join(f"+line {number}" for number in range(2500)))
    artifact = pr_review.review(context, transport=recording_transport(calls), token=FAKE_TOKEN)
    assert artifact["status"] == "ok"
    assert artifact["partial"] is True
    payload = user_payload(calls[0])
    assert "+line 0" in payload
    assert "+line 1999" in payload
    assert "+line 2000" not in payload
    assert "truncated" in payload.lower()


def test_diff_byte_cap_truncates_and_marks_partial() -> None:
    calls: list[dict] = []
    context = base_context(diff="\n".join("~" * 400 for _ in range(600)))
    artifact = pr_review.review(context, transport=recording_transport(calls), token=FAKE_TOKEN)
    assert artifact["partial"] is True
    assert len(user_payload(calls[0]).encode("utf-8")) <= pr_review.MAX_TOTAL_BYTES


def files_with_base(paths: list[str]) -> list[dict]:
    return [changed_file(path) for path in paths]


def test_base_content_caps_the_file_count_without_marking_the_review_partial() -> None:
    calls: list[dict] = []
    paths = [f"docs/file-{number:02d}.md" for number in range(25)]
    artifact = pr_review.review(
        base_context(
            files=files_with_base(paths),
            base_files={path: f"CONTENT-{path[-5:-3]}" for path in paths},
        ),
        transport=recording_transport(calls),
        token=FAKE_TOKEN,
    )
    assert artifact["partial"] is False
    assert artifact["omissions"]["base_content_missing"] == paths[20:]
    payload = user_payload(calls[0])
    assert "CONTENT-19" in payload
    assert "CONTENT-20" not in payload


def test_base_content_caps_the_total_bytes_without_marking_the_review_partial() -> None:
    calls: list[dict] = []
    artifact = pr_review.review(
        base_context(
            files=files_with_base(["docs/huge.md", "docs/small.md"]),
            base_files={"docs/huge.md": "~" * 120_000, "docs/small.md": "SMALL-CONTENT"},
        ),
        transport=recording_transport(calls),
        token=FAKE_TOKEN,
    )
    assert artifact["partial"] is False
    assert artifact["omissions"]["base_content_missing"] == ["docs/huge.md"]
    payload = user_payload(calls[0])
    assert "~" * 120_000 not in payload
    assert "SMALL-CONTENT" in payload


def test_the_request_shares_the_fetchers_cap_on_base_contents() -> None:
    assert pr_review_coverage.BASE_BYTES_LIMIT is pr_github.BASE_BYTES_LIMIT
    assert pr_review_coverage.BASE_FILE_LIMIT is pr_github.BASE_FILE_LIMIT
    assert not hasattr(pr_review, "MAX_BASE_BYTES")


def pr_953_context() -> dict:
    """Shaped like PR #953: a complete diff under the diff caps, base contents over theirs.

    20 modified files; the fetcher sent 15 and skipped the last 5, and the 15
    sent hold more than the cap on base contents.
    """
    paths = [f".github/workflows/w{n}.yml" for n in range(1)]
    paths += [f"docs/page-{n:02d}.md" for n in range(7)]
    paths += [f"scripts/tool_{n:02d}.py" for n in range(7)]
    paths += [f"scripts/test_tool_{n:02d}.py" for n in range(5)]
    diff = "".join(
        f"diff --git a/{path} b/{path}\n" + "".join(f"+{path} line {n}\n" for n in range(85))
        for path in paths
    )
    fetched = {path: f"BASE-{path}\n" + "x " * 6_625 + "\n" for path in paths[:15]}
    return base_context(files=files_with_base(paths), diff=diff, base_files=fetched)


def test_a_pr_953_shaped_context_is_complete_and_names_the_files_without_base_content() -> None:
    context = pr_953_context()
    paths = [item["path"] for item in context["files"]]
    assert len(context["diff"].splitlines()) < pr_review.MAX_DIFF_LINES
    assert (
        sum(len(text) for text in context["base_files"].values())
        > pr_review_coverage.BASE_BYTES_LIMIT
    )

    request, coverage = pr_review.build_request(context)

    assert coverage.partial is False
    sent = [path for path in paths if f"=== {path} (base) ===" in user_payload(request)]
    assert sent == paths[:7]
    # Dropped by the request builder and skipped by the fetcher alike.
    assert coverage.base_content_missing == tuple(paths[7:])
    payload = user_payload(request)
    assert pr_review_coverage.TRUNCATION_PREFIX not in payload
    note = payload.split(pr_review_coverage.BASE_MISSING_LINE, 1)[1].split("\n\n", 1)[0]
    for path in paths[7:]:
        assert path in note
    assert "The diff is complete." in note
    assert f"+{paths[-1]} line 84" in payload
    assert payload.index("DIFF:") < payload.index("BASE FILE CONTENTS")


def test_the_total_cap_drops_base_content_before_the_diff() -> None:
    paths = [f"docs/file-{number:02d}.md" for number in range(20)]
    diff = "".join(f"diff --git a/{p} b/{p}\n" + ("+" + "~ " * 50 + "\n") * 90 for p in paths)
    context = base_context(
        files=files_with_base(paths),
        diff=diff,
        base_files={path: "y " * 2_450 for path in paths},
        body="B " * 25_000,
    )
    request, coverage = pr_review.build_request(context)

    payload = user_payload(request)
    assert coverage.partial is False
    assert diff in payload
    assert 0 < len(coverage.base_content_missing) < len(paths)
    assert coverage.base_content_missing == tuple(paths[-len(coverage.base_content_missing) :])
    budget = pr_review.MAX_TOTAL_BYTES - len(request["messages"][0]["content"].encode("utf-8"))
    assert len(payload.encode("utf-8")) <= budget


def test_a_diff_cut_names_the_last_file_shown_in_full_and_the_files_not_shown() -> None:
    paths = [f"scripts/file_{number}.py" for number in range(4)]
    sections = [
        f"diff --git a/{path} b/{path}\n" + "".join(f"+{n}\n" for n in range(lines))
        for path, lines in zip(paths, (900, 900, 900, 900), strict=True)
    ]
    context = base_context(files=files_with_base(paths), diff="".join(sections))
    artifact = pr_review.review(context, transport=recording_transport([]), token=FAKE_TOKEN)

    assert artifact["partial"] is True
    omissions = artifact["omissions"]
    assert omissions["diff_cut"] is True
    assert omissions["diff_last_full_file"] == paths[1]
    assert omissions["diff_files_not_in_full"] == paths[2:]
    request, _ = pr_review.build_request(context)
    payload = user_payload(request)
    assert f"Last file shown in full: {paths[1]}." in payload
    assert f"Not shown in full: {paths[2]}, {paths[3]}." in payload


def test_an_unavailable_diff_names_every_file_as_not_shown() -> None:
    request, coverage = pr_review.build_request(base_context(diff="", diff_status="unavailable"))
    assert coverage.partial is True
    assert coverage.diff_last_full_file is None
    assert coverage.diff_files_not_in_full == ("docs/review.md",)
    assert "Not shown in full: docs/review.md." in user_payload(request)


def test_a_payload_whose_diff_overflows_the_total_cap_drops_all_base_content_first() -> None:
    context = overfull_context()
    request, coverage = pr_review.build_request(context)

    payload = user_payload(request)
    assert coverage.partial is True
    assert "(no base content provided)" in payload
    assert coverage.base_content_missing == tuple(item["path"] for item in context["files"])
    assert coverage.diff_files_not_in_full
    budget = pr_review.MAX_TOTAL_BYTES - len(request["messages"][0]["content"].encode("utf-8"))
    assert len(payload.encode("utf-8")) <= budget


def test_a_cut_title_or_body_is_noted_without_marking_the_review_partial() -> None:
    request, coverage = pr_review.build_request(base_context(body="B " * 30_000))
    assert coverage.partial is False
    assert pr_review_coverage.TEXT_CUT_NOTE in user_payload(request)


def test_total_payload_is_capped() -> None:
    calls: list[dict] = []
    context = base_context(
        diff="\n".join("~" * 100 for _ in range(2000)),
        base_files={f"docs/file-{number}.md": "y " * 2500 for number in range(20)},
        body="B " * 1000,
    )
    artifact = pr_review.review(context, transport=recording_transport(calls), token=FAKE_TOKEN)
    assert artifact["partial"] is True
    assert len(user_payload(calls[0]).encode("utf-8")) <= pr_review.MAX_TOTAL_BYTES


def test_diff_coverage_counts_the_last_section_as_not_shown_even_at_a_file_header() -> None:
    files = [changed_file("a.py"), changed_file("b.py")]
    shown = "diff --git a/a.py b/a.py\n+x\ndiff --git a/b.py b/b.py\n"

    last_full, not_in_full = pr_review_coverage.diff_coverage(files, shown)

    assert last_full == "a.py"
    assert not_in_full == ("b.py",)


def test_diff_coverage_counts_a_file_with_a_quoted_header_as_not_shown() -> None:
    files = [changed_file("a.py"), changed_file("ü b.py"), changed_file("c.py")]
    shown = (
        "diff --git a/a.py b/a.py\n+x\n"
        'diff --git "a/\\303\\274 b.py" "b/\\303\\274 b.py"\n+y\n'
        "diff --git a/c.py b/c.py\n+z\n"
    )

    last_full, not_in_full = pr_review_coverage.diff_coverage(files, shown)

    assert last_full == "a.py"
    assert not_in_full == ("ü b.py", "c.py")
