import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("balance_check.py")
EXAMPLE = Path(__file__).with_name("balance_check.example.json")


def run(*args):
    return subprocess.run(
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
        name = write_tmp('{"edges": []}')
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
        self.assertIn("knowledge leak", proc.stdout)
        self.assertEqual(proc.stderr, "")

    def test_example_json_is_0_and_parses(self):
        proc = run(str(EXAMPLE), "--json")
        self.assertEqual(proc.returncode, 0)
        rows = json.loads(proc.stdout)
        self.assertTrue(all({"from", "to", "verdict", "balance"} <= set(r) for r in rows))
        self.assertEqual(proc.stderr, "")


if __name__ == "__main__":
    unittest.main()
