import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("coupling_metrics.py")
EXAMPLE = Path(__file__).with_name("coupling_metrics.example.json")


def run(*args):
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def write_tmp(content):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        tmp.write(content)
        return tmp.name


class TestExitCodes(unittest.TestCase):
    def test_missing_file_is_1(self):
        proc = run("/nope.json")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("no such file", proc.stderr)

    def test_invalid_json_is_3(self):
        name = write_tmp("{bad")
        try:
            proc = run(name)
        finally:
            Path(name).unlink()
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(proc.stdout, "")
        self.assertIn("invalid JSON", proc.stderr)

    def test_schema_error_is_3(self):
        name = write_tmp('{"components": [], "edges": []}')
        try:
            proc = run(name)
        finally:
            Path(name).unlink()
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(proc.stdout, "")
        self.assertIn("error:", proc.stderr)

    def test_example_is_0(self):
        proc = run(str(EXAMPLE))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Zone", proc.stdout)
        self.assertEqual(proc.stderr, "")

    def test_example_prints_one_bullet_per_component_not_a_table(self):
        proc = run(str(EXAMPLE))
        bullets = [line for line in proc.stdout.splitlines() if line.startswith("- ")]
        self.assertEqual(len(bullets), 5)
        self.assertIn("- **core** — Zone of Pain: Ca 3, Ce 1, I 0.25, A 0.00, D 0.75", bullets)
        self.assertNotIn("|", proc.stdout)

    def test_example_json_is_0_and_parses(self):
        proc = run(str(EXAMPLE), "--json")
        self.assertEqual(proc.returncode, 0)
        rows = json.loads(proc.stdout)
        self.assertTrue(all({"name", "Ca", "Ce", "I", "A", "D", "zone"} <= set(r) for r in rows))
        self.assertEqual(proc.stderr, "")


class TestHelp(unittest.TestCase):
    def test_help_is_short_and_narrow(self):
        proc = run("--help")
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.splitlines()
        self.assertLessEqual(len(lines), 25)
        self.assertLessEqual(max(len(line) for line in lines), 100)


if __name__ == "__main__":
    unittest.main()
