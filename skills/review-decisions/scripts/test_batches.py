"""Tests for batches.py through its command line.

Run from the repo root with: uv run --with pytest pytest skills/review-decisions/scripts/
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("batches.py")
# The batch size limit batches.py documents; a diff line below is LINE_BYTES long.
LIMIT = 200_000
LINE_BYTES = 100


def run(*args):
    return subprocess.run(  # noqa: S603 -- test invokes batches.py with argv, no shell.
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def file_diff(path: str, lines: int) -> str:
    body = ("+" + "x" * (LINE_BYTES - 2) + "\n") * lines
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 0000000..1111111 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{lines} @@\n"
        f"{body}"
    )


def write_diff(tmp_path: Path, *files: tuple[str, int]) -> Path:
    diff = tmp_path / "diff.patch"
    diff.write_text("".join(file_diff(p, n) for p, n in files), encoding="utf-8")
    return diff


def split(tmp_path: Path, diff: Path) -> dict:
    out = tmp_path / "batches"
    proc = run("split", str(diff), "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_split_puts_every_file_in_exactly_one_batch_under_the_limit(tmp_path):
    diff = write_diff(tmp_path, ("a.py", 900), ("b.py", 900), ("c.py", 900), ("d.py", 900))

    manifest = split(tmp_path, diff)

    assert [b["paths"] for b in manifest["batches"]] == [["a.py", "b.py"], ["c.py", "d.py"]]
    out = tmp_path / "batches"
    texts = [(out / b["file"]).read_text(encoding="utf-8") for b in manifest["batches"]]
    assert "".join(texts) == diff.read_text(encoding="utf-8")
    assert all(len(text.encode()) <= LIMIT for text in texts)
    assert manifest["max_bytes"] == LIMIT


def test_split_keeps_a_small_diff_in_one_batch(tmp_path):
    diff = write_diff(tmp_path, ("a.py", 3), ("b.py", 3))

    manifest = split(tmp_path, diff)

    assert [b["paths"] for b in manifest["batches"]] == [["a.py", "b.py"]]


def test_split_gives_a_file_over_the_limit_its_own_batch_and_flags_it(tmp_path):
    diff = write_diff(tmp_path, ("small.py", 2), ("huge.py", 2100), ("tail.py", 2))

    manifest = split(tmp_path, diff)

    assert [b["paths"] for b in manifest["batches"]] == [["small.py"], ["huge.py"], ["tail.py"]]
    assert [b["oversize"] for b in manifest["batches"]] == [False, True, False]


def test_split_is_deterministic(tmp_path):
    diff = write_diff(tmp_path, ("a.py", 1500), ("b.py", 100), ("c.py", 1500))

    first = split(tmp_path, diff)
    second = split(tmp_path, diff)

    assert first == second


def test_split_names_renamed_and_deleted_files_by_their_path(tmp_path):
    diff = tmp_path / "diff.patch"
    diff.write_text(
        "diff --git a/old name.py b/new name.py\n"
        "similarity index 100%\n"
        "rename from old name.py\n"
        "rename to new name.py\n"
        "diff --git a/gone.py b/gone.py\n"
        "deleted file mode 100644\n"
        "--- a/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-x\n",
        encoding="utf-8",
    )

    manifest = split(tmp_path, diff)

    assert manifest["batches"][0]["paths"] == ["new name.py", "gone.py"]


def test_split_takes_no_size_option(tmp_path):
    diff = write_diff(tmp_path, ("a.py", 3))

    proc = run("split", str(diff), "--out", str(tmp_path / "batches"), "--max-bytes", "10")

    assert proc.returncode == 1


def test_split_rejects_text_that_is_not_a_git_diff(tmp_path):
    diff = tmp_path / "diff.patch"
    diff.write_text("hello\n", encoding="utf-8")

    proc = run("split", str(diff), "--out", str(tmp_path / "batches"))

    assert proc.returncode == 3
    assert not (tmp_path / "batches").exists()


def block(
    category: str, location: str, criterion: str = "open choice", depends_on: str = ""
) -> str:
    text = (
        f"Category: {category}\n"
        f"Location: {location}\n"
        f"Criterion: {criterion}\n"
        "Chosen: one option\n"
        "Cost to undo: callers would break.\n"
        "Lean: ask the author\n"
    )
    return text + (f"Depends on: {depends_on}\n" if depends_on else "")


def two_batches(tmp_path: Path) -> Path:
    diff = write_diff(tmp_path, ("api.py", 900), ("cli.py", 900), ("test_api.py", 900))
    split(tmp_path, diff)
    return tmp_path / "batches"


def answer(out: Path, batch: int, *blocks: str) -> None:
    (out / f"batch-{batch}.answer.md").write_text("\n".join(blocks), encoding="utf-8")


def merge(out: Path) -> dict:
    proc = run("merge", str(out))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_merge_orders_cards_from_all_batches_by_category(tmp_path):
    out = two_batches(tmp_path)
    answer(
        out,
        1,
        block("Behaviour", "cli.py:3"),
        block("Tests", "api.py:9", criterion="test choice"),
        block("Public surface", "api.py:1"),
    )
    answer(
        out,
        2,
        block("Tests", "test_api.py:4", criterion="deleted or weakened test: assert removed"),
        block("Deviation", "test_api.py:1"),
    )

    merged = merge(out)

    assert [(c["category"], c["location"], c["batch"]) for c in merged["cards"]] == [
        ("Deviation", "test_api.py:1", 2),
        ("Public surface", "api.py:1", 1),
        ("Behaviour", "cli.py:3", 1),
        ("Tests", "test_api.py:4", 2),
        ("Tests", "api.py:9", 1),
    ]
    assert merged["cards"][0]["chosen"] == "one option"
    assert merged["unclassified"] == []


def test_merge_lists_the_batch_boundaries(tmp_path):
    out = two_batches(tmp_path)
    answer(out, 1, "No review decisions found.")
    answer(out, 2, "No review decisions found.")

    merged = merge(out)

    assert merged["cards"] == []
    assert merged["boundaries"] == [
        "Batch 1 of 2: api.py, cli.py",
        "Batch 2 of 2: test_api.py",
    ]


def test_merge_marks_decisions_that_may_span_batches(tmp_path):
    out = two_batches(tmp_path)
    answer(
        out,
        1,
        block("Public surface", "api.py:1"),
        block("Behaviour", "cli.py:3", depends_on="api.py:1"),
        block("Behaviour", "cli.py:8"),
    )
    answer(
        out,
        2,
        block("Deviation", "test_api.py:1"),
        block("Tests", "test_api.py:4", depends_on="api.py:1"),
    )

    merged = merge(out)

    spans = {c["location"]: c["unchecked_across_batches"] for c in merged["cards"]}
    assert spans == {
        "api.py:1": True,
        "cli.py:3": False,
        "cli.py:8": False,
        "test_api.py:1": True,
        "test_api.py:4": True,
    }


def test_merge_marks_nothing_across_batches_for_a_single_batch(tmp_path):
    diff = write_diff(tmp_path, ("api.py", 3))
    split(tmp_path, diff)
    out = tmp_path / "batches"
    answer(out, 1, block("Public surface", "api.py:1"))

    merged = merge(out)

    assert merged["cards"][0]["unchecked_across_batches"] is False


def test_merge_names_every_file_of_a_batch_it_could_not_read(tmp_path):
    out = two_batches(tmp_path)
    answer(out, 1, "Category: Opinion\nLocation: api.py:1\n")

    merged = merge(out)

    assert merged["unclassified"] == [
        {"path": "api.py", "batch": 1, "reason": "classifier answer malformed: unknown category"},
        {"path": "cli.py", "batch": 1, "reason": "classifier answer malformed: unknown category"},
        {"path": "test_api.py", "batch": 2, "reason": "no classifier answer"},
    ]


def test_merge_reports_the_deviation_group_unchecked_without_an_issue(tmp_path):
    out = two_batches(tmp_path)
    answer(out, 1, "Deviation: unchecked (no issue).", block("Behaviour", "cli.py:3"))
    answer(out, 2, "Deviation: unchecked (no issue).\n\nNo review decisions found.")

    merged = merge(out)

    assert merged["deviation"] == "unchecked"
    assert [c["location"] for c in merged["cards"]] == ["cli.py:3"]


def test_merge_rejects_a_directory_without_a_split(tmp_path):
    proc = run("merge", str(tmp_path))

    assert proc.returncode == 2


def test_merge_reads_an_answer_wrapped_in_a_code_fence(tmp_path):
    out = two_batches(tmp_path)
    answer(out, 1, "```text\n" + block("Behaviour", "cli.py:3") + "```\n")
    answer(out, 2, "```\nNo review decisions found.\n```")

    merged = merge(out)

    assert [c["location"] for c in merged["cards"]] == ["cli.py:3"]
    assert merged["cards"][0]["lean"] == "ask the author"
    assert merged["unclassified"] == []


def test_merge_names_the_size_of_an_oversize_batch_without_an_answer(tmp_path):
    diff = write_diff(tmp_path, ("small.py", 3), ("big.py", 2100))
    split(tmp_path, diff)
    out = tmp_path / "batches"
    answer(out, 1, "No review decisions found.")
    size = json.loads((out / "batches.json").read_text())["batches"][1]["bytes"]

    merged = merge(out)

    assert merged["unclassified"] == [
        {
            "path": "big.py",
            "batch": 2,
            "reason": (
                f"no classifier answer; one file of {size} bytes, over the {LIMIT}-byte limit"
            ),
        }
    ]


def test_merge_records_why_a_classifier_run_failed(tmp_path):
    out = two_batches(tmp_path)
    answer(out, 1, "No review decisions found.")
    (out / "batch-2.failed").write_text("context window exceeded\n", encoding="utf-8")

    merged = merge(out)

    assert merged["unclassified"] == [
        {
            "path": "test_api.py",
            "batch": 2,
            "reason": "classifier run failed: context window exceeded",
        }
    ]


def test_merge_verifies_only_the_new_side_and_suggests_the_nearest_addition(tmp_path):
    diff = tmp_path / "diff.patch"
    diff.write_text(
        "diff --git a/old.py b/new name.py\n"
        "similarity index 50%\n"
        "rename from old.py\n"
        "rename to new name.py\n"
        "--- a/old.py\n"
        "+++ b/new name.py\t\n"
        "@@ -1,2 +1,2 @@\n"
        " context\n"
        "-old\n"
        "+new\n"
        "@@ -8 +8 @@\n"
        "-old\n"
        "+new\n"
        "\\ No newline at end of file\n"
        "diff --git a/gone.py b/gone.py\n"
        "deleted file mode 100644\n"
        "--- a/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-deleted\n",
        encoding="utf-8",
    )
    manifest = split(tmp_path, diff)
    out = tmp_path / "batches"
    expected = {
        "new name.py:1": (True, False, None, None, "new name.py", 1),
        "new name.py:2": (True, True, None, None, "new name.py", 2),
        "new name.py:8": (True, True, None, None, "new name.py", 8),
        "new name.py:5": (False, False, "line outside every hunk", 2, "new name.py", 5),
        "new name.py:9": (False, False, "line outside every hunk", 8, "new name.py", 9),
        "old.py:2": (False, False, "file not in diff", None, "old.py", 2),
        "gone.py:1": (False, False, "line outside every hunk", None, "gone.py", 1),
        "gone.py": (False, False, "location has no line", None, "gone.py", None),
        "-": (False, False, "omission has no location", None, None, None),
    }
    answer(out, 1, *(block("Behaviour", location) for location in expected))

    merged = merge(out)

    assert merged["files"] == manifest["batches"][0]["paths"] == ["new name.py", "gone.py"]
    assert {
        card["location"]: (
            card["location_verified"],
            card["location_changed"],
            card["location_reason"],
            card["nearest_line"],
            card["location_path"],
            card["location_line"],
        )
        for card in merged["cards"]
    } == expected


def test_merge_verifies_a_quoted_git_path(tmp_path):
    diff = tmp_path / "diff.patch"
    diff.write_text(
        r'diff --git "a/\303\244.py" "b/\303\244.py"'
        + "\n"
        + r'--- "a/\303\244.py"'
        + "\n"
        + r'+++ "b/\303\244.py"'
        + "\n"
        + "@@ -1 +1 @@\n-old\n+new\n",
        encoding="utf-8",
    )
    split(tmp_path, diff)
    out = tmp_path / "batches"
    answer(out, 1, block("Behaviour", "ä.py:1"))

    merged = merge(out)

    assert merged["files"] == ["ä.py"]
    assert merged["cards"][0]["location_changed"] is True


def test_merge_ignores_legacy_alternatives_without_changing_chosen(tmp_path):
    diff = write_diff(tmp_path, ("api.py", 1))
    split(tmp_path, diff)
    out = tmp_path / "batches"
    legacy = block("Behaviour", "api.py:1").replace(
        "Cost to undo:", "Alternatives: one guess\n- another guess\nCost to undo:"
    )
    answer(out, 1, legacy)

    card = merge(out)["cards"][0]

    assert "alternatives" not in card
    assert card["chosen"] == "one option"
    assert card["cost_to_undo"] == "callers would break."
