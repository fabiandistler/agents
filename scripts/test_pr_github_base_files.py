"""Tests for the bounded base-file fetch of scripts/pr_github.py.

Every test injects ``pr_github_fake.FakeClient``; none performs a network call.
"""

from __future__ import annotations

import pr_github
import pr_github_client
import pytest
from pr_github_fake import (
    CONTENTS_PREFIX,
    TREE_PATH,
    FakeClient,
    api_file,
    binary_api_file,
    contents_response,
    fetch,
    json_response,
    pull_request,
    tree_entry,
)


def test_base_files_are_capped_at_twenty_files():
    files = [api_file(f"scripts/file-{index}.py") for index in range(25)]
    contents = {f"scripts/file-{index}.py": contents_response("x") for index in range(25)}
    client = FakeClient(file_pages=(files,), contents=contents)

    context = fetch(client)

    assert len(context["base_files"]) == 20
    assert list(context["base_files"]) == [f"scripts/file-{index}.py" for index in range(20)]
    assert len(client.contents_calls()) == 20


def test_base_files_stop_at_the_byte_budget():
    limit = 200 * 1024
    client = FakeClient(
        file_pages=(
            [
                api_file("scripts/big.py"),
                api_file("scripts/one-byte.py"),
            ],
        ),
        contents={
            "scripts/big.py": contents_response("a" * limit),
            "scripts/one-byte.py": contents_response("b"),
        },
    )

    context = fetch(client)

    assert context["base_files"] == {"scripts/big.py": "a" * limit}
    assert len(client.contents_calls()) == 2


def test_a_single_file_over_the_byte_budget_is_skipped():
    client = FakeClient(
        file_pages=([api_file("scripts/huge.py")],),
        contents={"scripts/huge.py": contents_response("a" * (200 * 1024 + 1))},
    )

    assert fetch(client)["base_files"] == {}


def test_removed_binary_and_added_files_are_not_fetched():
    client = FakeClient(
        file_pages=(
            [
                api_file("docs/removed.md", status="removed", deletions=3),
                binary_api_file("docs/logo.png", additions=2),
                api_file("docs/added.md", status="added", patch="@@ -0,0 +1 @@\n"),
                api_file("docs/kept.md"),
            ],
        ),
        contents={"docs/kept.md": contents_response("kept")},
    )

    context = fetch(client)

    assert context["base_files"] == {"docs/kept.md": "kept"}
    assert [call.path for call in client.contents_calls()] == [f"{CONTENTS_PREFIX}docs/kept.md"]


def test_renamed_files_read_the_previous_path_at_the_base_commit():
    client = FakeClient(
        file_pages=([api_file("scripts/new.py", status="renamed", previous="scripts/old.py")],),
        contents={"scripts/old.py": contents_response("old")},
    )

    context = fetch(client)

    assert context["base_files"] == {"scripts/new.py": "old"}
    (call,) = client.contents_calls()
    assert call.path == f"{CONTENTS_PREFIX}scripts/old.py"
    assert call.params == {"ref": "base-sha"}


@pytest.mark.parametrize(
    "payload",
    [
        contents_response("x", encoding="none"),
        contents_response(b"\xff\xfe", type_="file"),
        json_response({"type": "submodule", "encoding": "base64", "size": 1, "content": "eA=="}),
        json_response({"type": "file", "encoding": "base64", "size": 300_000, "content": "eA=="}),
        json_response({"type": "file", "encoding": "base64", "size": 1}),
    ],
)
def test_unusable_base_content_is_skipped(payload):
    client = FakeClient(
        file_pages=([api_file("scripts/odd.py")],),
        contents={"scripts/odd.py": payload},
    )

    assert fetch(client)["base_files"] == {}


def test_base_file_404_is_skipped_but_other_fetch_errors_propagate():
    missing = FakeClient(
        file_pages=([api_file("scripts/missing.py")],),
        errors={
            f"{CONTENTS_PREFIX}scripts/missing.py": pr_github_client.FetchError("404", status=404)
        },
    )
    assert fetch(missing)["base_files"] == {}

    broken = FakeClient(
        file_pages=([api_file("scripts/broken.py")],),
        errors={
            f"{CONTENTS_PREFIX}scripts/broken.py": pr_github_client.FetchError("500", status=500)
        },
    )
    with pytest.raises(pr_github_client.FetchError):
        fetch(broken)


def test_missing_base_commit_fails_safe():
    client = FakeClient(pull_request(base={"ref": "main", "repo": {"full_name": "o/r"}}))

    with pytest.raises(pr_github_client.FetchError):
        fetch(client)


def test_base_tree_paths_list_every_blob_at_the_base_commit():
    client = FakeClient(
        tree={
            "sha": "base-sha",
            "tree": [
                tree_entry("scripts", type_="tree"),
                tree_entry("scripts/pr_review.py"),
                tree_entry("docs/guide.md"),
                tree_entry("vendor/lib", type_="commit"),
                tree_entry("README.md"),
            ],
            "truncated": False,
        }
    )

    context = fetch(client)

    assert context["base_paths"] == ["README.md", "docs/guide.md", "scripts/pr_review.py"]
    assert context["base_paths_truncated"] is False
    assert [call.params for call in client.calls if call.path == TREE_PATH] == [{"recursive": "1"}]


def test_base_tree_paths_keep_the_truncated_flag_github_reports():
    client = FakeClient(tree={"sha": "base-sha", "tree": [tree_entry("a.md")], "truncated": True})

    context = fetch(client)

    assert context["base_paths"] == ["a.md"]
    assert context["base_paths_truncated"] is True


def test_base_tree_paths_are_capped_and_marked_truncated():
    limit = pr_github.BASE_PATH_LIMIT
    entries = [tree_entry(f"docs/page-{index:05d}.md") for index in range(limit + 5)]

    context = fetch(FakeClient(tree={"sha": "base-sha", "tree": entries, "truncated": False}))

    assert len(context["base_paths"]) == limit
    assert context["base_paths"][-1] == f"docs/page-{limit - 1:05d}.md"
    assert context["base_paths_truncated"] is True


@pytest.mark.parametrize(
    "tree",
    [
        [],
        {"sha": "base-sha", "truncated": False},
        {"sha": "base-sha", "tree": [{"type": "blob"}], "truncated": False},
        {"sha": "base-sha", "tree": [], "truncated": "no"},
    ],
)
def test_malformed_base_tree_fails_safe(tree):
    with pytest.raises(pr_github_client.FetchError):
        fetch(FakeClient(tree=tree))
