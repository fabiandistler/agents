import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CHURN = Path(__file__).with_name("churn.py")


def load_churn():
    spec = importlib.util.spec_from_file_location("churn", CHURN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up by name.
    spec.loader.exec_module(module)
    return module


def run(*args, env=None):
    base = None
    if env is not None:
        base = dict(os.environ)
        base.update(env)
    return subprocess.run(  # noqa: S603 -- test invokes churn.py with argv, no shell.
        [sys.executable, str(CHURN), *args],
        capture_output=True,
        text=True,
        check=False,
        env=base,
    )


def git(repo, *args):
    result = subprocess.run(  # noqa: S603 -- fixture Git commands use argv; no shell.
        [  # noqa: S607 -- PATH lookup is intentional.
            "git",
            "-C",
            str(repo),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result


def make_repo(parent):
    """A three-file repo where every file has two commits inside any window."""
    repo = Path(parent) / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    for i in range(3):
        (repo / f"mod{i}.py").write_text(f"VALUE = {i}\n", encoding="utf-8")
    git(repo, "add", ".")
    for n in range(2):
        for i in range(3):
            with open(repo / f"mod{i}.py", "a", encoding="utf-8") as handle:
                handle.write(f"EXTRA_{n} = {n}\n")
        git(repo, "add", ".")
        git(repo, "-c", "commit.gpgsign=false", "commit", "-qm", f"change {n}")
    return repo


class TestJsonBounded(unittest.TestCase):
    def test_default_json_under_10k_and_top_truncates(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            default = run("--since", "2020-01-01", "--json", str(repo))
            self.assertEqual(default.returncode, 0)
            self.assertLess(len(default.stdout), 10000)
            full = json.loads(default.stdout)
            self.assertEqual(full["files_ranked"], 3)
            self.assertFalse(full["shallow"])
            top = run("--since", "2020-01-01", "--json", "--top", "1", str(repo))
            self.assertEqual(len(json.loads(top.stdout)["files"]), 1)
            everything = run("--since", "2020-01-01", "--json", "--top", "0", str(repo))
            self.assertEqual(len(json.loads(everything.stdout)["files"]), 3)


class TestUsageErrors(unittest.TestCase):
    def test_bad_since_exits_two_with_empty_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run("--since", "not-a-real-date-xyz", str(make_repo(tmp)))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("--since", proc.stderr)

    def test_negative_top_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run("--top", "-1", str(make_repo(tmp)))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")

    def test_documented_since_forms_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            for since in ("2020-01-01", "12 months ago", "2.weeks.ago", "yesterday"):
                proc = run("--since", since, "--min-commits", "1", str(repo))
                self.assertEqual(proc.returncode, 0, since)


class TestOutputFile(unittest.TestCase):
    def test_json_output_file_matches_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            dest = Path(tmp) / "hotspots.json"
            proc = run("--since", "2020-01-01", "--json", "--output", str(dest), str(repo))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(len(json.loads(dest.read_text(encoding="utf-8"))["files"]), 3)

    def test_unwritable_output_is_a_path_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run(
                "--since",
                "2020-01-01",
                str(repo),
                "--output",
                str(repo / "mod0.py" / "hotspots.json"),
            )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cannot write", proc.stderr)


class TestHelp(unittest.TestCase):
    def test_help_fits_25_lines_and_states_exit_codes(self):
        proc = run("--help", env={"COLUMNS": "80"})
        self.assertEqual(proc.returncode, 0)
        self.assertLessEqual(len(proc.stdout.splitlines()), 25)
        self.assertIn("exit codes", proc.stdout)


class TestShallowWorktree(unittest.TestCase):
    def test_shallow_flag_fires_inside_a_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = make_repo(tmp)
            shallow = Path(tmp) / "shallow"
            clone = subprocess.run(  # noqa: S603 -- local fixture clone uses argv; no shell.
                [  # noqa: S607 -- PATH lookup is intentional.
                    "git",
                    "clone",
                    "-q",
                    "--depth",
                    "1",
                    "--no-local",
                    str(src),
                    str(shallow),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(clone.returncode, 0, clone.stderr)
            worktree = Path(tmp) / "wt"
            git(shallow, "worktree", "add", "-q", str(worktree))
            proc = run("--since", "2020-01-01", "--min-commits", "1", "--json", str(worktree))
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(json.loads(proc.stdout)["shallow"])
            self.assertIn("shallow", proc.stderr)


class TestDroppedFiles(unittest.TestCase):
    """Unreadable and deleted files are dropped, each under its own count."""

    ARGS = ("--since", "2020-01-01", "--min-commits", "1")

    def run_main(self, repo, *args, unreadable=None):
        """Run churn.main in-process; reading `unreadable` raises PermissionError.

        The failure is injected because CI may run as root, where chmod 000
        does not stop a read.
        """
        churn = load_churn()
        real_read_bytes = Path.read_bytes

        def read_bytes(path):
            if unreadable is not None and path.name == unreadable:
                raise PermissionError(13, "Permission denied", str(path))
            return real_read_bytes(path)

        out = io.StringIO()
        patch = mock.patch.object(Path, "read_bytes", autospec=True, side_effect=read_bytes)
        with patch, contextlib.redirect_stdout(out):
            code = churn.main([*self.ARGS, *args, str(repo)])
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_unreadable_file_is_counted_as_unreadable_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            report = json.loads(self.run_main(repo, "--json", unreadable="mod1.py"))
        self.assertNotIn("mod1.py", [f["path"] for f in report["files"]])
        self.assertEqual(report["files_ranked"], 2)
        self.assertEqual(report["dropped_unreadable"], 1)
        self.assertEqual(report["dropped_missing"], 0)

    def test_deleted_file_is_still_counted_as_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            (repo / "mod2.py").unlink()
            report = json.loads(self.run_main(repo, "--json"))
        self.assertNotIn("mod2.py", [f["path"] for f in report["files"]])
        self.assertEqual(report["dropped_missing"], 1)
        self.assertEqual(report["dropped_unreadable"], 0)

    def test_text_output_names_a_nonzero_unreadable_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            text = self.run_main(repo, unreadable="mod1.py")
        head = text.splitlines()[0]
        self.assertIn("1 unreadable", head)
        self.assertIn("2 files ranked", head)

    def test_text_output_is_silent_about_zero_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            (repo / "mod2.py").unlink()
            text = self.run_main(repo)
        self.assertIn("1 gone from the tree", text)
        self.assertNotIn("unreadable", text)


if __name__ == "__main__":
    unittest.main()
