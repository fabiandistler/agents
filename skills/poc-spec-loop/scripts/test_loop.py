"""Drive assets/loop.sh end to end against stub runner and forge CLIs.

Each stub records its argv; the runner stub commits the file the item's check
looks for, so one item passes and the loop ends with a ready PR.
"""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parent.parent / "assets" / "loop.sh"

RUNNER_STUB = """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$STUB_LOG/$(basename "$0").argv"
for arg in "$@"; do
  if [[ $arg == "Loop infrastructure preflight."* ]]; then
    if [[ ${STUB_PREFLIGHT_FAILURE:-} == 1 ]]; then
      echo 'error building bubblewrap command: app-server socket directory must be' \\
        'a user-owned directory with mode 0700'
      exit 0
    fi
    if [[ ${STUB_PREFLIGHT_FAILURE:-} == 2 ]]; then
      echo shell-ok
      exit 0
    fi
    command=${arg#*$'\\n'}
    command=${command%%$'\\n'*}
    bash -c "$command"
    exit $?
  fi
done
echo task >> "$STUB_LOG/task_calls"
case ${STUB_TASK:-work} in
  fail) # the CLI itself fails: no work done
    echo 'error: 401 Unauthorized' >&2
    exit 1
    ;;
  blocked)
    echo 'BLOCKED: spec contradicts itself'
    exit "${STUB_TASK_EXIT:-0}"
    ;;
esac
echo done > done.txt
git add done.txt
git commit -qm "feat(prd-01): done"
exit "${STUB_TASK_EXIT:-0}"
"""

GH_STUB = """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$STUB_LOG/gh.argv"
"""

# `az extension show` must succeed for the precondition; only `az repos` is logged.
AZ_STUB = """#!/usr/bin/env bash
[[ $1 == repos ]] && printf '%s\\0' "$@" > "$STUB_LOG/az.argv"
exit 0
"""

FORGE_URLS = {
    "github": "https://github.com/o/r.git",
    "azure": "https://dev.azure.com/o/p/_git/r",
}

EXPECTED_ARGV_HEAD = {
    "claude": ["-p"],
    "codex": ["exec", "--sandbox", "danger-full-access"],
    "opencode": ["run", "--auto"],
}

OPEN_ITEM = {
    "id": "prd-01",
    "title": "Create the done marker",
    "deps": [],
    "check": "test -f done.txt",
    "passes": False,
    "attempts": 0,
    "origin": "spec",
}

PRD = {"approved": True, "language": "bash", "target": "cli"}


def git(repo, *args):
    subprocess.run(  # noqa: S603 -- fixture Git commands use argv; no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- Git intentionally resolves from PATH.
        check=True,
        capture_output=True,
    )


def make_poc(parent, origin_url=FORGE_URLS["github"], done_items=()):
    """A greenfield repo released for Phase 2, with a bare origin and stubs on PATH.

    origin carries a forge-looking URL; an insteadOf rewrite sends the push to
    the local bare repo. done_items are prepended as already-passed items.
    """
    parent = Path(parent)
    origin = parent / "origin.git"
    repo = parent / "repo"
    bin_dir = parent / "bin"
    log_dir = parent / "log"
    for d in (repo, bin_dir, log_dir):
        d.mkdir()
    subprocess.run(  # noqa: S603 -- test creates a temporary bare repository with argv.
        [  # noqa: S607 -- PATH lookup is intentional.
            "git",
            "init",
            "-q",
            "--bare",
            str(origin),
        ],
        check=True,
    )
    git(repo, "init", "-q", "-b", "main")
    # Per-repo identity: CI runners have no global one, and loop.sh commits too.
    git(repo, "config", "user.name", "t")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "remote", "add", "origin", origin_url)
    git(repo, "config", f"url.{origin}.insteadOf", origin_url)
    (repo / "plans").mkdir()
    (repo / "plans" / "SPEC.md").write_text(
        "---\nlanguage: bash\ntarget: cli\n---\n## Goal\nA marker.\n"
        "## Definition of Done\n- done.txt exists\n"
    )
    prd = {**PRD, "items": [*done_items, OPEN_ITEM]}
    (repo / "plans" / "prd.json").write_text(json.dumps(prd, indent=2))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "chore(plans): spec and prd")
    for name in EXPECTED_ARGV_HEAD:
        (bin_dir / name).write_text(RUNNER_STUB)
    (bin_dir / "gh").write_text(GH_STUB)
    (bin_dir / "az").write_text(AZ_STUB)
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_LOG": str(log_dir),
    }
    env.pop("POC_AGENT", None)
    env.pop("POC_AGENT_FLAGS", None)
    return repo, log_dir, env


def run_loop(repo, env):
    return subprocess.run(  # noqa: S603 -- test runs the repo's loop against controlled stubs.
        ["bash", str(LOOP)],  # noqa: S607 -- Bash resolves from PATH in the test environment.
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def committed(repo, path):
    return subprocess.run(  # noqa: S603 -- test reads a temporary repository with argv.
        [  # noqa: S607 -- PATH lookup is intentional.
            "git",
            "-C",
            str(repo),
            "show",
            f"HEAD:{path}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def current_branch(repo):
    return subprocess.run(  # noqa: S603 -- test reads a temporary repository with argv.
        [  # noqa: S607 -- PATH lookup is intentional.
            "git",
            "-C",
            str(repo),
            "branch",
            "--show-current",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def read_argv(log_dir, name):
    return (log_dir / f"{name}.argv").read_text().split("\0")[:-1]


def task_calls(log_dir):
    """Number of task (non-preflight) runner calls the stub recorded."""
    calls = log_dir / "task_calls"
    return len(calls.read_text().splitlines()) if calls.exists() else 0


def stop_diagnosis(stderr):
    """The one-line reason infrastructure_stop prints before the shared guidance."""
    return next(line for line in stderr.splitlines() if line.startswith("Infrastructure stop:"))


def fail_command(repo, name, arg_glob):
    """Put a `name` wrapper on PATH that fails like a read-only file system.

    The wrapper exits 1 when any argument matches the bash glob arg_glob and
    otherwise runs the real command.
    """
    real = shlex.quote(shutil.which(name))
    wrapper = repo.parent / "bin" / name
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'for arg in "$@"; do\n'
        f"  if [[ $arg == {arg_glob} ]]; then\n"
        f'    echo "{name}: $arg: Read-only file system" >&2\n'
        "    exit 1\n"
        "  fi\n"
        f'done\nexec {real} "$@"\n'
    )
    wrapper.chmod(0o755)


class LoopRunnerTest(unittest.TestCase):
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

    def test_preflight_stop_message_makes_no_branch_claim(self):
        repo, _, env = self.poc()
        env.update(POC_AGENT="codex", STUB_PREFLIGHT_FAILURE="2")
        diagnosis = stop_diagnosis(run_loop(repo, env).stderr)
        self.assertIn("preflight", diagnosis)
        self.assertNotIn("branch", diagnosis)

    def test_flags_override_replaces_defaults(self):
        repo, log_dir, env = self.poc()
        env["POC_AGENT"] = "codex"
        env["POC_AGENT_FLAGS"] = "--sandbox workspace-write"
        self.assertEqual(run_loop(repo, env).returncode, 0)
        self.assertEqual(read_argv(log_dir, "codex")[:3], ["exec", "--sandbox", "workspace-write"])


class LoopForgeTest(unittest.TestCase):
    def poc(self, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo, log_dir, env = make_poc(tmp.name, **kwargs)
        env["POC_AGENT"] = "claude"
        return repo, log_dir, env

    def test_unsupported_forge_exits_2(self):
        for url in ("https://gitlab.com/o/r.git", "/srv/git/r.git"):
            with self.subTest(url=url):
                repo, log_dir, env = self.poc(origin_url=url)
                result = run_loop(repo, env)
                self.assertEqual(result.returncode, 2)
                self.assertIn("github.com or dev.azure.com", result.stderr)
                self.assertEqual(list(log_dir.iterdir()), [])

    def test_azure_opens_pr_with_az_repos(self):
        for url in (FORGE_URLS["azure"], "https://o.visualstudio.com/p/_git/r"):
            with self.subTest(url=url):
                repo, log_dir, env = self.poc(origin_url=url)
                result = run_loop(repo, env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((log_dir / "gh.argv").exists())
                az = read_argv(log_dir, "az")
                self.assertEqual(az[:3], ["repos", "pr", "create"])
                self.assertEqual(az[az.index("--target-branch") + 1], "main")
                self.assertEqual(az[az.index("--draft") + 1], "false")
                description = az[az.index("--description") + 1]
                self.assertIn("- [x] prd-01", description)
                self.assertIn("plans/PR.md", description)
                self.assertIn("## Deployment", committed(repo, "plans/PR.md"))

    def test_azure_description_stays_under_cap(self):
        done = [
            {
                "id": f"prd-{n:02d}",
                "title": "Long finished item — " + "x" * 300,
                "deps": [],
                "check": "true",
                "passes": True,
                "attempts": 0,
                "origin": "spec",
            }
            for n in range(2, 40)
        ]
        repo, log_dir, env = self.poc(origin_url=FORGE_URLS["azure"], done_items=done)
        self.assertEqual(run_loop(repo, env).returncode, 0)
        az = read_argv(log_dir, "az")
        description = az[az.index("--description") + 1]
        self.assertLessEqual(len(description), 4000)
        self.assertIn("plans/PR.md", description)
        self.assertGreater(len(committed(repo, "plans/PR.md")), 4000)


if __name__ == "__main__":
    unittest.main()
