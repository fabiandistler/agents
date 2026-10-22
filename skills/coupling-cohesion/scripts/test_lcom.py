import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LCOM = Path(__file__).with_name("lcom.py")


def run(*args):
    return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
        [sys.executable, str(LCOM), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def write_mod(tmp, name, funcs):
    target = Path(tmp, name)
    target.write_text("".join(f"def {f}():\n    return {i}\n" for i, f in enumerate(funcs)))
    return target


class TestEmptyScan(unittest.TestCase):
    def test_missing_path_text(self):
        proc = run("/nope")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("no such path", proc.stderr)

    def test_missing_path_json(self):
        proc = run("/nope", "--json")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("no such path", proc.stderr)

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
        self.assertIn("groups=1 [LCOM=", proc.stdout)
        self.assertNotIn("clusters=", proc.stdout)


class TestBoundedOutput(unittest.TestCase):
    def test_summary_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_mod(tmp, "mod.py", ["alpha", "beta"])
            proc = run(str(target))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("1 modules, 1 with 2+ groups", proc.stdout)

    def test_top_caps_text_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                write_mod(tmp, f"mod{i}.py", [f"alpha{i}", f"beta{i}"])
            proc = run(tmp, "--top", "1")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.count("# "), 1)
        self.assertIn("2 more (raise --top)", proc.stdout)
        self.assertIn("3 modules, 3 with 2+ groups", proc.stdout)

    def test_top_caps_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                write_mod(tmp, f"mod{i}.py", [f"alpha{i}", f"beta{i}"])
            proc = run(tmp, "--top", "2", "--json")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(json.loads(proc.stdout)), 2)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_mod(tmp, "mod.py", ["alpha", "beta"])
            out = Path(tmp, "report.txt")
            proc = run(str(target), "--output", str(out))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
            body = out.read_text()
        self.assertIn("1 modules, 1 with 2+ groups", body)


class TestGroupsFirstText(unittest.TestCase):
    def test_split_candidate_leads_with_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_mod(tmp, "mod.py", ["alpha", "beta"])
            proc = run(str(target))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("groups=2 [LCOM=", proc.stdout)
        self.assertIn("-> 2 disjoint groups --", proc.stdout)


class TestLcomFloorQuirk(unittest.TestCase):
    def test_zero_lcom_still_hints_split_on_clusters(self):
        proc = run(str(LCOM), "--json")
        self.assertEqual(proc.returncode, 0)
        entry = next(r for r in json.loads(proc.stdout) if r["module"] == "ModuleReport")
        self.assertEqual(entry["lcom"], 0)
        self.assertEqual(entry["clusters"], 2)
        self.assertIn("could split", entry["interpretation"])


class TestHelp(unittest.TestCase):
    def test_help_is_short_and_narrow(self):
        proc = run("--help")
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.splitlines()
        self.assertLessEqual(len(lines), 25)
        self.assertLessEqual(max(len(line) for line in lines), 100)


if __name__ == "__main__":
    unittest.main()
