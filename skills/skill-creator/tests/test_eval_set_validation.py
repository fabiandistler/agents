"""Tests for eval-set shape validation in the trigger-eval entry points."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_eval import run_eval  # noqa: E402
from scripts.run_loop import run_loop  # noqa: E402
from scripts.utils import (  # noqa: E402
    EvalSetFormatError,
    load_eval_set,
    validate_eval_set,
)

GOOD_EVAL_SET = [
    {"query": "help me write a skill", "should_trigger": True},
    {"query": "what is the capital of France", "should_trigger": False},
]

# The shape of a skill's evals/evals.json — the mistake that used to surface
# as "TypeError: string indices must be integers".
TWO_LEVEL_EVAL_SET = {
    "skill_name": "example",
    "evals": [
        {"prompt": "help me write a skill", "expected": "triggers"},
    ],
}


class ValidateEvalSetTest(unittest.TestCase):
    def test_good_shape_passes_through_unchanged(self):
        self.assertIs(validate_eval_set(GOOD_EVAL_SET), GOOD_EVAL_SET)

    def test_two_level_object_shape_is_rejected(self):
        with self.assertRaises(EvalSetFormatError) as ctx:
            validate_eval_set(TWO_LEVEL_EVAL_SET)
        message = str(ctx.exception)
        self.assertIn("two-level object shape", message)
        self.assertIn("should_trigger", message)

    def test_plain_object_is_rejected(self):
        with self.assertRaises(EvalSetFormatError) as ctx:
            validate_eval_set({"query": "hi", "should_trigger": True})
        self.assertIn("expected an array", str(ctx.exception))

    def test_non_list_shapes_are_rejected(self):
        for value in ("a string", 42, None, True):
            with self.subTest(value=value):
                with self.assertRaises(EvalSetFormatError) as ctx:
                    validate_eval_set(value)
                self.assertIn("expected an array", str(ctx.exception))

    def test_empty_list_is_rejected(self):
        with self.assertRaises(EvalSetFormatError) as ctx:
            validate_eval_set([])
        self.assertIn("empty", str(ctx.exception))

    def test_item_must_be_an_object(self):
        with self.assertRaises(EvalSetFormatError) as ctx:
            validate_eval_set(["help me write a skill"])
        self.assertIn("item 0", str(ctx.exception))

    def test_missing_and_malformed_fields_are_rejected(self):
        cases = [
            ([{"should_trigger": True}], '"query"'),
            ([{"query": "", "should_trigger": True}], '"query"'),
            ([{"query": 3, "should_trigger": True}], '"query"'),
            ([{"query": "hi"}], '"should_trigger"'),
            ([{"query": "hi", "should_trigger": "yes"}], '"should_trigger"'),
        ]
        for eval_set, expected in cases:
            with self.subTest(eval_set=eval_set):
                with self.assertRaises(EvalSetFormatError) as ctx:
                    validate_eval_set(eval_set)
                self.assertIn(expected, str(ctx.exception))

    def test_source_is_named_in_the_message(self):
        with self.assertRaises(EvalSetFormatError) as ctx:
            validate_eval_set(TWO_LEVEL_EVAL_SET, source="evals/evals.json")
        self.assertIn("evals/evals.json", str(ctx.exception))


class LoadEvalSetTest(unittest.TestCase):
    def setUp(self):
        # One directory per test, removed on teardown. Everything this class
        # touches has to live inside it: the system temp dir is shared with
        # every other process on the machine, so neither "this file is mine"
        # nor "this name is free" holds there.
        tmp = tempfile.TemporaryDirectory(prefix="eval-set-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self._written = 0

    def _write(self, payload: object, *, raw: str | None = None) -> Path:
        self._written += 1
        path = self.tmp / f"eval_set_{self._written}.json"
        path.write_text(raw if raw is not None else json.dumps(payload))
        return path

    def test_loads_a_good_eval_set(self):
        self.assertEqual(load_eval_set(self._write(GOOD_EVAL_SET)), GOOD_EVAL_SET)

    def test_rejects_the_two_level_object_shape(self):
        path = self._write(TWO_LEVEL_EVAL_SET)
        with self.assertRaises(EvalSetFormatError) as ctx:
            load_eval_set(path)
        self.assertIn(str(path), str(ctx.exception))
        self.assertIn("two-level object shape", str(ctx.exception))

    def test_rejects_a_non_list_shape(self):
        with self.assertRaises(EvalSetFormatError) as ctx:
            load_eval_set(self._write("just a string"))
        self.assertIn("expected an array", str(ctx.exception))

    def test_rejects_malformed_json(self):
        with self.assertRaises(EvalSetFormatError) as ctx:
            load_eval_set(self._write(None, raw="{not json"))
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_rejects_a_missing_file(self):
        # Inside this test's own directory, so "missing" is a fact we control
        # rather than a bet that nothing else on the machine wrote this name.
        with self.assertRaises(EvalSetFormatError) as ctx:
            load_eval_set(self.tmp / "definitely-missing-eval-set.json")
        self.assertIn("cannot read eval set", str(ctx.exception))


class EntryPointValidationTest(unittest.TestCase):
    """Both entry points reject bad shapes before any subprocess work."""

    def test_run_eval_rejects_bad_shapes(self):
        for bad in (TWO_LEVEL_EVAL_SET, "a string", [{"prompt": "hi"}]):
            with self.subTest(bad=bad):
                with self.assertRaises(EvalSetFormatError):
                    run_eval(
                        eval_set=bad,
                        skill_name="example",
                        description="an example skill",
                        num_workers=1,
                        timeout=1,
                        project_root=Path.cwd(),
                    )

    def test_run_loop_rejects_bad_shapes(self):
        for bad in (TWO_LEVEL_EVAL_SET, "a string", [{"prompt": "hi"}]):
            with self.subTest(bad=bad):
                with self.assertRaises(EvalSetFormatError):
                    run_loop(
                        eval_set=bad,
                        # Validation runs first, so this path is never read.
                        skill_path=Path("/nonexistent-skill"),
                        description_override=None,
                        num_workers=1,
                        timeout=1,
                        max_iterations=1,
                        runs_per_query=1,
                        trigger_threshold=0.5,
                        holdout=0.0,
                        model="test-model",
                        verbose=False,
                    )


if __name__ == "__main__":
    unittest.main()
