import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aggregate_benchmark import (  # noqa: E402
    generate_benchmark,
    generate_markdown,
    load_run_results,
    main,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FlatLayoutTests(unittest.TestCase):
    def setUp(self):
        self.results = load_run_results(FIXTURES / "flat")

    def test_discovers_both_configs_with_two_runs_each(self):
        self.assertEqual(set(self.results), {"with_skill", "without_skill"})
        self.assertEqual(len(self.results["with_skill"]), 2)
        self.assertEqual(len(self.results["without_skill"]), 2)

    def test_flat_runs_have_run_number_one(self):
        for config in self.results.values():
            for run in config:
                self.assertEqual(run["run_number"], 1)

    def test_eval_name_is_set_from_metadata(self):
        names = {run["eval_name"] for config in self.results.values() for run in config}
        self.assertEqual(names, {"flat-eval-one", "flat-eval-zero"})

    def test_reads_real_pass_rate_time_and_tokens(self):
        with_skill = {run["eval_id"]: run for run in self.results["with_skill"]}
        without_skill = {run["eval_id"]: run for run in self.results["without_skill"]}
        self.assertEqual(with_skill[0]["pass_rate"], 1.0)
        self.assertEqual(with_skill[0]["time_seconds"], 12.0)
        self.assertEqual(with_skill[0]["tokens"], 5000)
        self.assertEqual(without_skill[0]["pass_rate"], 0.3333)
        self.assertEqual(without_skill[0]["time_seconds"], 8.0)
        self.assertEqual(without_skill[0]["tokens"], 2000)
        self.assertEqual(without_skill[1]["pass_rate"], 0.0)
        self.assertEqual(without_skill[1]["time_seconds"], 15.0)
        self.assertEqual(without_skill[1]["tokens"], 3000)
        self.assertEqual(without_skill[1]["errors"], 1)

    def test_inputs_directory_is_skipped(self):
        self.assertNotIn("inputs", self.results)

    def test_generate_benchmark_payload(self):
        benchmark = generate_benchmark(FIXTURES / "flat")
        # Two evals run once each — not two runs of one configuration.
        self.assertEqual(benchmark["metadata"]["runs_per_configuration"], 1)
        # Ordered by eval_id, not lexicographically by name.
        self.assertEqual(
            benchmark["metadata"]["evals_run"], ["flat-eval-zero", "flat-eval-one"]
        )
        run = benchmark["runs"][0]
        self.assertIn("eval_name", run)
        self.assertGreater(benchmark["run_summary"]["with_skill"]["pass_rate"]["mean"], 0)
        self.assertGreater(benchmark["run_summary"]["with_skill"]["time_seconds"]["mean"], 0)
        self.assertGreater(benchmark["run_summary"]["with_skill"]["tokens"]["mean"], 0)

    def test_generate_markdown_columns(self):
        markdown = generate_markdown(generate_benchmark(FIXTURES / "flat"))
        self.assertIn("100% ± 0%", markdown)
        self.assertIn("17% ± 24%", markdown)
        self.assertIn("+0.83", markdown)

    def test_evals_run_falls_back_to_ids_without_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            eval_dir = Path(tmp) / "eval-0" / "with_skill"
            eval_dir.mkdir(parents=True)
            grading = json.loads(
                (FIXTURES / "flat" / "eval-0" / "with_skill" / "grading.json").read_text()
            )
            (eval_dir / "grading.json").write_text(json.dumps(grading))
            benchmark = generate_benchmark(Path(tmp))
            self.assertEqual(benchmark["metadata"]["evals_run"], [0])


class NestedLayoutTests(unittest.TestCase):
    def setUp(self):
        self.results = load_run_results(FIXTURES / "nested")

    def test_discovers_two_runs_per_config(self):
        self.assertEqual(set(self.results), {"with_skill", "without_skill"})
        self.assertEqual(len(self.results["with_skill"]), 2)
        self.assertEqual(len(self.results["without_skill"]), 2)

    def test_run_numbers_are_parsed_from_directory_names(self):
        run_numbers = sorted(run["run_number"] for run in self.results["with_skill"])
        self.assertEqual(run_numbers, [1, 2])

    def test_timing_embedded_in_grading_json(self):
        run_1 = next(run for run in self.results["with_skill"] if run["run_number"] == 1)
        self.assertEqual(run_1["pass_rate"], 0.9)
        self.assertEqual(run_1["time_seconds"], 0.8)

    def test_timing_falls_back_to_sibling_timing_json(self):
        run_2 = next(run for run in self.results["with_skill"] if run["run_number"] == 2)
        self.assertEqual(run_2["pass_rate"], 0.7)
        self.assertEqual(run_2["time_seconds"], 0.6)
        self.assertEqual(run_2["tokens"], 600)

    def test_runs_per_configuration_counts_runs_of_one_eval(self):
        benchmark = generate_benchmark(FIXTURES / "nested")
        self.assertEqual(benchmark["metadata"]["runs_per_configuration"], 2)

    def test_tokens_come_from_grading_timing_block(self):
        run_1 = next(run for run in self.results["with_skill"] if run["run_number"] == 1)
        self.assertEqual(run_1["tokens"], 800)

    def test_baseline_run_values(self):
        run_1 = next(run for run in self.results["without_skill"] if run["run_number"] == 1)
        run_2 = next(run for run in self.results["without_skill"] if run["run_number"] == 2)
        self.assertEqual(run_1["pass_rate"], 0.5)
        self.assertEqual(run_1["time_seconds"], 0.2)
        self.assertEqual(run_2["pass_rate"], 0.4)
        self.assertEqual(run_2["time_seconds"], 0.1)
        self.assertEqual(run_2["tokens"], 100)


class WrappedLayoutTests(unittest.TestCase):
    def test_runs_under_runs_directory_are_discovered(self):
        results = load_run_results(FIXTURES / "wrapped")
        self.assertEqual(set(results), {"with_skill", "without_skill"})
        self.assertEqual(len(results["with_skill"]), 1)
        self.assertEqual(results["with_skill"][0]["pass_rate"], 1.0)
        self.assertEqual(results["without_skill"][0]["pass_rate"], 0.5)


class EdgeCaseTests(unittest.TestCase):
    def test_mixed_layout_prefers_nested_runs(self):
        results = load_run_results(FIXTURES / "mixed")
        self.assertEqual(len(results["with_skill"]), 1)
        self.assertEqual(results["with_skill"][0]["pass_rate"], 0.9)
        self.assertEqual(results["without_skill"][0]["pass_rate"], 0.1)

    def test_outputs_without_grading_is_omitted_not_zeroed(self):
        results = load_run_results(FIXTURES / "partial")
        self.assertNotIn("with_skill", results)
        self.assertEqual(len(results["without_skill"]), 1)
        self.assertEqual(results["without_skill"][0]["pass_rate"], 0.75)

    def test_ungraded_config_does_not_appear_as_zero_percent(self):
        benchmark = generate_benchmark(FIXTURES / "partial")
        self.assertNotIn("with_skill", benchmark["run_summary"])
        self.assertEqual(benchmark["metadata"]["runs_per_configuration"], 1)


    def test_config_metadata_inherits_eval_name_from_eval_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "eval-0" / "with_skill"
            config_dir.mkdir(parents=True)
            (config_dir.parent / "eval_metadata.json").write_text(
                json.dumps({"eval_id": 7, "eval_name": "inherited-name"})
            )
            # Config-dir copy overrides eval_id but says nothing about the name.
            (config_dir / "eval_metadata.json").write_text(json.dumps({"eval_id": 9}))
            (config_dir / "grading.json").write_text(
                json.dumps({"summary": {"pass_rate": 1.0}})
            )
            run = load_run_results(Path(tmp))["with_skill"][0]
            self.assertEqual(run["eval_id"], 9)
            self.assertEqual(run["eval_name"], "inherited-name")

    def test_timing_json_supplies_tokens_when_grading_has_duration_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "eval-0" / "with_skill"
            config_dir.mkdir(parents=True)
            (config_dir / "grading.json").write_text(
                json.dumps(
                    {
                        "summary": {"pass_rate": 1.0},
                        "timing": {"total_duration_seconds": 4.0},
                        "execution_metrics": {"output_chars": 123},
                    }
                )
            )
            (config_dir / "timing.json").write_text(json.dumps({"total_tokens": 4200}))
            run = load_run_results(Path(tmp))["with_skill"][0]
            self.assertEqual(run["time_seconds"], 4.0)
            self.assertEqual(run["tokens"], 4200)


class EndToEndTests(unittest.TestCase):
    def test_main_writes_benchmark_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "benchmark.json"
            main([str(FIXTURES / "flat"), "--output", str(output)])
            benchmark = json.loads(output.read_text())
            self.assertTrue(benchmark["runs"])
            self.assertIn("run_summary", benchmark)
            self.assertIn("with_skill", benchmark["run_summary"])
            self.assertIn("without_skill", benchmark["run_summary"])
            markdown = output.with_suffix(".md")
            self.assertTrue(markdown.exists())
            self.assertIn("Pass Rate", markdown.read_text())


if __name__ == "__main__":
    unittest.main()
