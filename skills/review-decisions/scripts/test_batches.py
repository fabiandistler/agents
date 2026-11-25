"""Tests for batches.py through its command line.

Run from the repo root with: uv run --with pytest pytest skills/review-decisions/scripts/
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("batches.py")


def run(*args):
    return subprocess.run(  # noqa: S603 -- test invokes batches.py with argv, no shell.
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def file_diff(path: str, lines: int) -> str:
    body = "".join(f"+line {i}\n" for i in range(lines))
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


def split(tmp_path: Path, diff: Path, max_bytes: int) -> dict:
    out = tmp_path / "batches"
    proc = run("split", str(diff), "--out", str(out), "--max-bytes", str(max_bytes))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_split_puts_every_file_in_exactly_one_batch_under_the_limit(tmp_path):
    diff = write_diff(tmp_path, ("a.py", 40), ("b.py", 40), ("c.py", 40), ("d.py", 40))
    limit = 2 * len(file_diff("a.py", 40).encode()) + 10

    manifest = split(tmp_path, diff, max_bytes=limit)

    assert [b["paths"] for b in manifest["batches"]] == [["a.py", "b.py"], ["c.py", "d.py"]]
    out = tmp_path / "batches"
    texts = [(out / b["file"]).read_text(encoding="utf-8") for b in manifest["batches"]]
    assert "".join(texts) == diff.read_text(encoding="utf-8")
    assert all(len(text.encode()) <= limit for text in texts)


def test_split_keeps_a_small_diff_in_one_batch(tmp_path):
    diff = write_diff(tmp_path, ("a.py", 3), ("b.py", 3))

    manifest = split(tmp_path, diff, max_bytes=100_000)

    assert [b["paths"] for b in manifest["batches"]] == [["a.py", "b.py"]]


def test_split_gives_a_file_over_the_limit_its_own_batch_and_flags_it(tmp_path):
    diff = write_diff(tmp_path, ("small.py", 2), ("huge.py", 500), ("tail.py", 2))

    manifest = split(tmp_path, diff, max_bytes=2_000)

    assert [b["paths"] for b in manifest["batches"]] == [["small.py"], ["huge.py"], ["tail.py"]]
    assert [b["oversize"] for b in manifest["batches"]] == [False, True, False]


def test_split_is_deterministic(tmp_path):
    diff = write_diff(tmp_path, ("a.py", 30), ("b.py", 5), ("c.py", 30))

    first = split(tmp_path, diff, max_bytes=1_500)
    second = split(tmp_path, diff, max_bytes=1_500)

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

    manifest = split(tmp_path, diff, max_bytes=100_000)

    assert manifest["batches"][0]["paths"] == ["new name.py", "gone.py"]


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
        "Alternatives: another option; a third option\n"
        "Cost to undo: callers would break.\n"
        "Lean: ask the author\n"
    )
    return text + (f"Depends on: {depends_on}\n" if depends_on else "")


def two_batches(tmp_path: Path) -> Path:
    diff = write_diff(tmp_path, ("api.py", 40), ("cli.py", 40), ("test_api.py", 40))
    split(tmp_path, diff, max_bytes=len(file_diff("api.py", 40).encode()) * 2 + 10)
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
    split(tmp_path, diff, max_bytes=100_000)
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
