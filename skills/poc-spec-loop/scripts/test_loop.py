"""Drive assets/loop.sh end to end against stub runner and gh CLIs.

Each stub records its argv; the runner stub commits the file the item's check
looks for, so one item passes and the loop ends with a ready PR.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

LOOP = Path(__file__).resolve().parent.parent / "assets" / "loop.sh"

RUNNER_STUB = """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$STUB_LOG/$(basename "$0").argv"
echo done > done.txt
git add done.txt
git commit -qm "feat(prd-01): done"
"""

GH_STUB = """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$STUB_LOG/gh.argv"
"""

EXPECTED_ARGV_HEAD = {
    "claude": ["-p"],
    "codex": ["exec", "--sandbox", "danger-full-access"],
    "opencode": ["run", "--auto"],
}

PRD = {
    "approved": True,
    "language": "bash",
    "target": "cli",
    "items": [
        {
            "id": "prd-01",
            "title": "Create the done marker",
            "deps": [],
            "check": "test -f done.txt",
            "passes": False,
            "attempts": 0,
            "origin": "spec",
        }
    ],
}


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_poc(parent):
    """A greenfield repo released for Phase 2, with a bare origin and stubs on PATH."""
    parent = Path(parent)
    origin = parent / "origin.git"
    repo = parent / "repo"
    bin_dir = parent / "bin"
    log_dir = parent / "log"
    for d in (repo, bin_dir, log_dir):
        d.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "remote", "add", "origin", str(origin))
    (repo / "plans").mkdir()
    (repo / "plans" / "SPEC.md").write_text(
        "---\nlanguage: bash\ntarget: cli\n---\n## Goal\nA marker.\n"
        "## Definition of Done\n- done.txt exists\n"
    )
    (repo / "plans" / "prd.json").write_text(json.dumps(PRD, indent=2))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "chore(plans): spec and prd")
    for name in EXPECTED_ARGV_HEAD:
        (bin_dir / name).write_text(RUNNER_STUB)
    (bin_dir / "gh").write_text(GH_STUB)
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_LOG": str(log_dir),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    env.pop("POC_AGENT", None)
    env.pop("POC_AGENT_FLAGS", None)
    return repo, log_dir, env


def run_loop(repo, env):
    return subprocess.run(
        ["bash", str(LOOP)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )


def committed(repo, path):
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{path}"], check=True, capture_output=True, text=True
    ).stdout


def read_argv(log_dir, name):
    return (log_dir / f"{name}.argv").read_text().split("\0")[:-1]


class LoopRunnerTest(unittest.TestCase):
    def poc(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return make_poc(tmp.name)

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
                self.assertEqual(gh[:2], ["pr", "create"])
                self.assertNotIn("--draft", gh)
                self.assertEqual(gh[gh.index("--body-file") + 1], "plans/PR.md")
                self.assertIn("- [x] prd-01", committed(repo, "plans/PR.md"))

    def test_flags_override_replaces_defaults(self):
        repo, log_dir, env = self.poc()
        env["POC_AGENT"] = "codex"
        env["POC_AGENT_FLAGS"] = "--sandbox workspace-write"
        self.assertEqual(run_loop(repo, env).returncode, 0)
        self.assertEqual(read_argv(log_dir, "codex")[:3], ["exec", "--sandbox", "workspace-write"])


if __name__ == "__main__":
    unittest.main()
