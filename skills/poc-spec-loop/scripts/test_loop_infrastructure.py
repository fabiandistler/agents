"""loop.sh infrastructure stops (exit 2 and 4): missing runner, failed preflight, failed agent."""

import json
import shlex
import tempfile
import unittest

from loop_fixtures import (
    LOOP,
    current_branch,
    fail_command,
    make_poc,
    run_loop,
    stop_diagnosis,
    task_calls,
)


class LoopInfrastructureStopTest(unittest.TestCase):
    def poc(self, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return make_poc(tmp.name, **kwargs)

    def assert_restart_guidance(self, stderr, repo):
        """Exit 4 names a copyable restart and the recovery reference, repairing nothing."""
        lines = [line.strip() for line in stderr.splitlines()]
        commands = [shlex.split(line) for line in lines if line.startswith(("cd ", "POC_AGENT="))]
        self.assertEqual(
            commands, [["cd", str(repo.resolve())], ["POC_AGENT=codex", "bash", str(LOOP)]]
        )
        self.assertIn(str(LOOP.parent.parent / "references" / "runner-recovery.md"), stderr)
        self.assertIn("Runner flags cannot grant", stderr)
        self.assertIn("separate human approval", stderr)

    def test_missing_or_unknown_runner_exits_2(self):
        for agent in (None, "", "gpt"):
            with self.subTest(agent=agent):
                repo, log_dir, env = self.poc()
                if agent is not None:
                    env["POC_AGENT"] = agent
                result = run_loop(repo, env)
                self.assertEqual(result.returncode, 2)
                self.assertIn("claude, codex, opencode", result.stderr)
                self.assertEqual(list(log_dir.iterdir()), [])

    def test_shell_failure_aborts_without_attempts_and_can_restart(self):
        repo, log_dir, env = self.poc()
        env["POC_AGENT"] = "codex"
        env["STUB_PREFLIGHT_FAILURE"] = "1"
        before = (repo / "plans/prd.json").read_bytes()
        result = run_loop(repo, env)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("app-server socket directory", result.stderr)
        self.assert_restart_guidance(result.stderr, repo)
        self.assertEqual((repo / "plans/prd.json").read_bytes(), before)
        self.assertEqual(current_branch(repo), "main")
        self.assertFalse((repo / "plans/BLOCKED.md").exists())
        self.assertFalse((repo / "done.txt").exists())
        self.assertFalse((log_dir / "gh.argv").exists())
        env.pop("STUB_PREFLIGHT_FAILURE")
        result = run_loop(repo, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads((repo / "plans/prd.json").read_text())["items"][0]["passes"])

    def test_printed_success_without_shell_proof_is_rejected(self):
        repo, log_dir, env = self.poc()
        env.update(POC_AGENT="codex", STUB_PREFLIGHT_FAILURE="2")
        before = (repo / "plans/prd.json").read_bytes()
        result = run_loop(repo, env)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("proof missing", result.stderr)
        self.assertEqual((repo / "plans/prd.json").read_bytes(), before)
        self.assertEqual(current_branch(repo), "main")
        self.assertFalse((log_dir / "gh.argv").exists())

    def test_driver_git_metadata_write_failure_stops_before_runner(self):
        # Log directory, preflight directory (the EROFS report in #660), driver write probe.
        for command, arg_glob in (
            ("mkdir", "*/poc-loop"),
            ("mktemp", "*/poc-loop/preflight.*"),
            ("mktemp", "*/objects/poc-preflight.*"),
        ):
            with self.subTest(command=command, arg_glob=arg_glob):
                repo, log_dir, env = self.poc()
                env["POC_AGENT"] = "codex"
                fail_command(repo, command, arg_glob)
                before = (repo / "plans/prd.json").read_bytes()
                result = run_loop(repo, env)
                self.assertEqual(result.returncode, 4, result.stderr)
                self.assertIn("Git metadata is not writable", result.stderr)
                self.assert_restart_guidance(result.stderr, repo)
                self.assertEqual((repo / "plans/prd.json").read_bytes(), before)
                self.assertEqual(current_branch(repo), "main")
                self.assertFalse((repo / "plans/BLOCKED.md").exists())
                self.assertEqual(list(log_dir.iterdir()), [])  # no runner or forge call

    def test_agent_failure_mid_run_stops_without_spending_attempts(self):
        repo, log_dir, env = self.poc()
        env.update(POC_AGENT="codex", STUB_TASK="fail")
        result = run_loop(repo, env)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertEqual(task_calls(log_dir), 1)
        prd = json.loads((repo / "plans/prd.json").read_text())
        self.assertEqual(prd["items"][0]["attempts"], 0)
        self.assertIs(prd["items"][0]["passes"], False)
        self.assertFalse((repo / "plans/BLOCKED.md").exists())
        diagnosis = stop_diagnosis(result.stderr)
        self.assertIn("prd-01", diagnosis)
        self.assertIn("agent exited 1", diagnosis)
        self.assertIn("run_prd-01.log", diagnosis)
        self.assertNotIn("preflight", diagnosis)
        self.assertIn("401 Unauthorized", result.stderr)
        self.assert_restart_guidance(result.stderr, repo)
        self.assertFalse((log_dir / "gh.argv").exists())
        # Restored infrastructure: the restart resumes the same item at attempt 1.
        env.pop("STUB_TASK")
        result = run_loop(repo, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads((repo / "plans/prd.json").read_text())["items"][0]["passes"])

    def test_preflight_stop_message_makes_no_branch_claim(self):
        repo, _, env = self.poc()
        env.update(POC_AGENT="codex", STUB_PREFLIGHT_FAILURE="2")
        diagnosis = stop_diagnosis(run_loop(repo, env).stderr)
        self.assertIn("preflight", diagnosis)
        self.assertNotIn("branch", diagnosis)


if __name__ == "__main__":
    unittest.main()
