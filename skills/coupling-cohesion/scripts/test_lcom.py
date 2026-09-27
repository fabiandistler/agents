import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LCOM = Path(__file__).with_name("lcom.py")


def run(*args):
    return subprocess.run(
        [sys.executable, str(LCOM), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class TestEmptyScan(unittest.TestCase):
    def test_missing_path_text(self):
        proc = run("/nope")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(proc.stdout, "")
        self.assertIn("No analyzable source files found.", proc.stderr)

    def test_missing_path_json(self):
        proc = run("/nope", "--json")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(json.loads(proc.stdout), [])
        self.assertIn("No analyzable source files found.", proc.stderr)

    def test_dir_without_source_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "notes.txt").write_text("hello\n")
            proc = run(tmp)
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(proc.stdout, "")
        self.assertIn("No analyzable source files found.", proc.stderr)

    def test_healthy_file_still_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "mod.py")
            target.write_text(
                "SHARED = 1\n"
                "def alpha():\n"
                "    return SHARED + 1\n"
                "def beta():\n"
                "    return SHARED + 2\n"
            )
            proc = run(str(target))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("clusters=", proc.stdout)


if __name__ == "__main__":
    unittest.main()
