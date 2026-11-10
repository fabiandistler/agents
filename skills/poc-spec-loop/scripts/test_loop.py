"""loop.sh task outcomes: a passing item, a failing check, the BLOCKED: marker, agent exit status,
runner flags.
"""

import json
import tempfile
import unittest

from loop_fixtures import (
    EXPECTED_ARGV_HEAD,
    committed,
    current_branch,
    make_poc,
    read_argv,
    run_loop,
    task_calls,
)


class LoopTaskTest(unittest.TestCase):
    def poc(self, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return make_poc(tmp.name, **kwargs)

    def test_runner_passes_item_and_opens_ready_pr(self):
        for agent, head in sorted(EXPECTED_ARGV_HEAD.items()):
            with self.subTest(agent=agent):
                repo, log_dir, env = self.poc()
                env["POC_AGENT"] = agent
                result = run_loop(repo, env)
                self.assertEqual(result.returncode, 0, result.stderr)

                argv = read_argv(log_dir, agent)
                self.assertEqual(argv[: len(head)], head)
                self.assertIn("id: prd-01", argv[len(head)])
                default_flags = (
                    ["--allowedTools", "Bash,Read,Edit,Write,Glob,Grep"]
                    if agent == "claude"
                    else []
                )
                self.assertEqual(argv[len(head) + 1 :], default_flags)

                prd = json.loads((repo / "plans" / "prd.json").read_text())
                self.assertIs(prd["items"][0]["passes"], True)
                gh = read_argv(log_dir, "gh")
                # REST, not GraphQL-backed `gh pr create`: cloud sessions block GraphQL.
                self.assertEqual(gh[:4], ["api", "repos/{owner}/{repo}/pulls", "--method", "POST"])
                fields = gh[4:]
                branch = current_branch(repo)
                self.assertIn("base=main", fields)
                self.assertIn(f"head={branch}", fields)
                self.assertIn(f"title=PoC loop {branch}", fields)
                self.assertEqual(fields[fields.index("body=@plans/PR.md") - 1], "-F")
                self.assertFalse(any(f.startswith("draft=") for f in fields))
                self.assertIn("- [x] prd-01", committed(repo, "plans/PR.md"))

    def test_agent_failure_after_passing_work_warns_and_continues(self):
        repo, log_dir, env = self.poc()
        env.update(POC_AGENT="codex", STUB_TASK_EXIT="1")
        result = run_loop(repo, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARN: agent exited 1 on prd-01", result.stderr)
        self.assertTrue(json.loads((repo / "plans/prd.json").read_text())["items"][0]["passes"])
        self.assertTrue((log_dir / "gh.argv").exists())

    def test_blocked_marker_wins_over_agent_exit_status(self):
        for exit_status in ("0", "1"):
            with self.subTest(exit_status=exit_status):
                repo, log_dir, env = self.poc()
                env.update(POC_AGENT="codex", STUB_TASK="blocked", STUB_TASK_EXIT=exit_status)
                result = run_loop(repo, env)
                self.assertEqual(result.returncode, 3, result.stderr)  # prd-01 blocked
                self.assertEqual(task_calls(log_dir), 1)
                self.assertIn(
                    "BLOCKED: spec contradicts itself", committed(repo, "plans/BLOCKED.md")
                )
                prd = json.loads((repo / "plans/prd.json").read_text())
                self.assertEqual(prd["items"][0]["attempts"], 3)

    def test_silent_check_failure_blocks_with_command_and_status(self):
        # A failing check that prints nothing (or only whitespace) gets a reason naming
        # its exit status and command, in BLOCKED.md and in the next attempt's prompt.
        for check, status, env_extra in (
            ("test -f done.txt", 1, {}),
            ("echo; test -f done.txt", 1, {}),
            ("sleep 5", 124, {"CHECK_TIMEOUT": "1"}),
        ):
            with self.subTest(check=check):
                repo, log_dir, env = self.poc(check=check)
                env.update(POC_AGENT="codex", STUB_TASK="idle", **env_extra)
                result = run_loop(repo, env)
                self.assertEqual(result.returncode, 3, result.stderr)  # prd-01 blocked
                self.assertEqual(task_calls(log_dir), 3)
                reason = f"check exited {status} with no output: {check}"
                self.assertIn(
                    f"## prd-01 — Create the done marker\n\n```\n{reason}\n```\n",
                    committed(repo, "plans/BLOCKED.md"),
                )
                prompt = read_argv(log_dir, "codex")[3]  # third attempt sees the second's failure
                self.assertIn(f"previous failure output:\n```\n{reason}\n```", prompt)

    def test_check_failure_output_is_the_block_reason(self):
        repo, _, env = self.poc(check="echo 'done.txt missing' >&2; test -f done.txt")
        env.update(POC_AGENT="codex", STUB_TASK="idle")
        result = run_loop(repo, env)
        self.assertEqual(result.returncode, 3, result.stderr)
        blocked = committed(repo, "plans/BLOCKED.md")
        self.assertIn("```\ndone.txt missing\n```\n", blocked)
        self.assertNotIn("with no output", blocked)

    def test_flags_override_replaces_defaults(self):
        repo, log_dir, env = self.poc()
        env["POC_AGENT"] = "codex"
        env["POC_AGENT_FLAGS"] = "--sandbox workspace-write"
        self.assertEqual(run_loop(repo, env).returncode, 0)
        self.assertEqual(read_argv(log_dir, "codex")[:3], ["exec", "--sandbox", "workspace-write"])


if __name__ == "__main__":
    unittest.main()
