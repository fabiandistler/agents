"""Tests for the context mapping of the GitHub REST fetcher (scripts/pr_github.py).

Every test injects ``pr_github_fake.FakeClient``; none performs a network call.
"""

from __future__ import annotations

from typing import cast

import pr_github
import pytest
from pr_github_fake import (
    CHECK_RUNS_PATH,
    COMMENTS_PATH,
    DIFF_ACCEPT,
    FILES_PATH,
    NUMBER,
    PR_PATH,
    REPO,
    REVIEWS_PATH,
    FakeClient,
    api_file,
    binary_api_file,
    contents_response,
    fetch,
    pull_request,
)


def test_fetch_context_maps_every_contract_field():
    client = FakeClient(
        pull_request(
            state="closed",
            draft=True,
            mergeable=False,
            labels=[{"name": "risk:low"}, {"name": "x"}],
        ),
        file_pages=(
            [
                api_file("scripts/modified.py", patch="@@ -1 +1 @@\n"),
                binary_api_file("assets/logo.png", additions=5),
                api_file("docs/old.md", status="removed", additions=0, deletions=4),
                api_file("scripts/new_name.py", status="renamed", previous="scripts/old_name.py"),
                api_file("docs/new.md", status="added", additions=2, patch="@@ -0,0 +1 @@\n"),
            ],
        ),
        comment_pages=(
            [
                {"id": 1, "body": "first", "user": {"login": "someone"}},
                {"id": 2, "body": None},
            ],
        ),
        review_pages=(
            [
                {
                    "user": {"login": "a"},
                    "state": "APPROVED",
                    "submitted_at": "2026-01-01T00:00:00Z",
                },
                {
                    "user": {"login": "b"},
                    "state": "CHANGES_REQUESTED",
                    "submitted_at": "2026-01-01T00:00:00Z",
                },
            ],
        ),
        check_run_pages=(
            [
                {"name": "checks", "conclusion": "success", "status": "completed"},
                {"name": "mermaid", "conclusion": None, "status": "in_progress"},
            ],
        ),
        diff="diff --git a/x b/x\n",
        contents={
            "scripts/modified.py": contents_response("print('x')\n"),
            "scripts/old_name.py": contents_response("old\n"),
        },
    )

    context = fetch(client)

    assert context["schema_version"] == 1
    assert context["repo"] == REPO
    assert context["number"] == NUMBER
    assert context["state"] == "closed"
    assert context["title"] == "Fix docs"
    assert context["body"] == "Body"
    assert context["author"] == "fabiandistler"
    assert context["head_sha"] == "abc123"
    assert context["head_ref"] == "fix/x"
    assert context["base_ref"] == "main"
    assert context["default_branch"] == "main"
    assert context["draft"] is True
    assert context["fork"] is False
    assert context["mergeable"] is False
    assert context["auto_merge_active"] is False
    assert context["labels"] == ["risk:low", "x"]
    assert context["files"] == [
        {
            "path": "scripts/modified.py",
            "status": "modified",
            "additions": 1,
            "deletions": 0,
            "binary": False,
            "renamed_from": None,
        },
        {
            "path": "assets/logo.png",
            "status": "modified",
            "additions": 5,
            "deletions": 0,
            "binary": True,
            "renamed_from": None,
        },
        {
            "path": "docs/old.md",
            "status": "removed",
            "additions": 0,
            "deletions": 4,
            "binary": False,
            "renamed_from": None,
        },
        {
            "path": "scripts/new_name.py",
            "status": "renamed",
            "additions": 1,
            "deletions": 0,
            "binary": False,
            "renamed_from": "scripts/old_name.py",
        },
        {
            "path": "docs/new.md",
            "status": "added",
            "additions": 2,
            "deletions": 0,
            "binary": False,
            "renamed_from": None,
        },
    ]
    assert context["diff"] == "diff --git a/x b/x\n"
    assert context["diff_status"] == "complete"
    assert context["base_paths"] == []
    assert context["base_paths_truncated"] is False
    assert context["base_files"] == {
        "scripts/modified.py": "print('x')\n",
        "scripts/new_name.py": "old\n",
    }
    assert context["comments"] == [{"id": 1, "body": "first"}, {"id": 2, "body": ""}]
    assert context["checks"] == {"checks": "success", "mermaid": "in_progress"}
    assert context["reviews"] == {"changes_requested": True}


def test_non_object_item_in_a_paginated_list_fails_safe():
    malformed_page = cast(list[dict], [api_file("docs/guide.md"), "junk"])
    client = FakeClient(file_pages=(malformed_page,))

    with pytest.raises(pr_github.FetchError):
        fetch(client)


def test_files_comments_reviews_and_check_runs_are_paginated():
    first_files = [
        api_file(f"docs/page-{index}.md", status="added", patch="@@ -0,0 +1 @@\n")
        for index in range(100)
    ]
    client = FakeClient(
        file_pages=(
            first_files,
            [api_file("docs/last.md", status="added", patch="@@ -0,0 +1 @@\n")],
        ),
        comment_pages=(
            [{"id": index, "body": "x"} for index in range(100)],
            [{"id": 100, "body": "y"}],
        ),
        review_pages=(
            [{"user": {"login": f"u{index}"}, "state": "COMMENTED"} for index in range(100)],
            [{"user": {"login": "late"}, "state": "CHANGES_REQUESTED"}],
        ),
        check_run_pages=(
            [{"name": f"check-{index}", "conclusion": "success"} for index in range(100)],
            [{"name": "last", "conclusion": "success"}],
        ),
    )

    context = fetch(client)

    assert len(context["files"]) == 101
    assert len(context["comments"]) == 101
    assert context["reviews"] == {"changes_requested": True}
    assert len(context["checks"]) == 101
    assert context["checks"]["last"] == "success"

    for prefix in (FILES_PATH, COMMENTS_PATH, REVIEWS_PATH, CHECK_RUNS_PATH):
        pages = [call.params["page"] for call in client.calls if call.path == prefix]
        assert pages == [1, 2], prefix
        assert all(call.params["per_page"] == 100 for call in client.calls if call.path == prefix)


def test_raw_diff_is_fetched_with_its_own_accept_header_and_capped():
    client = FakeClient(diff="a" * 500_000)

    context = fetch(client)

    assert len(context["diff"]) == 400 * 1024
    diff_calls = [call for call in client.calls if call.accept == DIFF_ACCEPT]
    assert len(diff_calls) == 1
    assert diff_calls[0].path == PR_PATH


def test_a_diff_the_api_refuses_is_reported_unavailable_not_raised():
    # GitHub answers 406 (code too_large) when a diff exceeds its line or file
    # limit; any error on the diff request is handled the same way.
    for status in (406, 500):
        client = FakeClient(
            file_pages=([api_file("docs/guide.md")],),
            errors={PR_PATH + "#diff": pr_github.FetchError(str(status), status=status)},
        )

        context = fetch(client)

        assert context["diff"] == ""
        assert context["diff_status"] == "unavailable"
        assert [file["path"] for file in context["files"]] == ["docs/guide.md"]


def test_a_diff_within_the_limit_is_complete_and_a_cut_one_truncated():
    assert fetch(FakeClient(diff="diff --git a/x b/x\n"))["diff_status"] == "complete"
    assert fetch(FakeClient(diff="a" * 500_000))["diff_status"] == "truncated"


@pytest.mark.parametrize(
    ("entry", "binary"),
    [
        (api_file("a.py", patch="@@ -1 +1 @@\n", additions=1), False),
        (binary_api_file("b.png", additions=3), True),
        (binary_api_file("c.png", additions=0, deletions=0), True),
        (api_file("d.py", patch="", additions=1), False),
        (binary_api_file("e.bin", additions=0, deletions=2), True),
    ],
)
def test_binary_detection_fails_safe_when_the_patch_is_missing(entry, binary):
    client = FakeClient(file_pages=([entry],), contents={entry["filename"]: contents_response("")})

    (file,) = fetch(client)["files"]

    assert file["binary"] is binary


def test_missing_patch_with_zero_changes_counts_as_binary():
    # GitHub reports a binary file as 0/0 without a patch; a mode-only change
    # looks the same, so both fail safe as binary.
    entry = {
        "filename": "docs/diagram.png",
        "status": "modified",
        "additions": 0,
        "deletions": 0,
    }
    client = FakeClient(file_pages=([entry],))

    (file,) = fetch(client)["files"]

    assert file["binary"] is True


def test_pure_rename_without_a_patch_is_not_binary():
    entry = {
        "filename": "docs/new-name.md",
        "status": "renamed",
        "previous_filename": "docs/old-name.md",
        "additions": 0,
        "deletions": 0,
    }
    client = FakeClient(file_pages=([entry],))

    (file,) = fetch(client)["files"]

    assert file["binary"] is False


def test_enabled_auto_merge_is_reported_as_active():
    client = FakeClient(pull_request(auto_merge={"merge_method": "merge"}))

    assert fetch(client)["auto_merge_active"] is True


def test_check_run_without_a_conclusion_maps_to_its_status():
    client = FakeClient(
        check_run_pages=(
            [
                {"name": "queued", "conclusion": None, "status": "queued"},
                {"name": "done", "conclusion": "success", "status": "completed"},
                {"conclusion": "success", "status": "completed"},
            ],
        ),
    )

    context = fetch(client)

    assert context["checks"] == {"queued": "queued", "done": "success"}


@pytest.mark.parametrize(
    ("reviews", "changes_requested"),
    [
        ([], False),
        ([{"user": {"login": "a"}, "state": "APPROVED"}], False),
        ([{"user": {"login": "a"}, "state": "CHANGES_REQUESTED"}], True),
        (
            [
                {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "a"}, "state": "APPROVED"},
            ],
            False,
        ),
        (
            [
                {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "b"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "c"}, "state": "COMMENTED"},
            ],
            True,
        ),
        (
            [
                {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "a"}, "state": "PENDING"},
            ],
            True,
        ),
        (
            [
                {"user": {"login": "a"}, "state": "CHANGES_REQUESTED"},
                {"user": {"login": "a"}, "state": "DISMISSED"},
            ],
            False,
        ),
    ],
)
def test_reviews_use_the_latest_submitted_state_per_user(reviews, changes_requested):
    client = FakeClient(review_pages=(reviews,))

    assert fetch(client)["reviews"] == {"changes_requested": changes_requested}


@pytest.mark.parametrize(
    ("head_repo", "fork"),
    [
        ({"full_name": REPO}, False),
        ({"full_name": "someone/agents"}, True),
        (None, True),
    ],
)
def test_fork_is_detected_from_the_head_repository(head_repo, fork):
    client = FakeClient(pull_request(head={"sha": "abc123", "ref": "fix/x", "repo": head_repo}))

    assert fetch(client)["fork"] is fork
