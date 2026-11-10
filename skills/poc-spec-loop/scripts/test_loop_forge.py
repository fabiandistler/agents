"""loop.sh forge handling: supported origins and Azure Repos pull requests."""

import tempfile
import unittest

from loop_fixtures import (
    FORGE_URLS,
    committed,
    make_poc,
    read_argv,
    run_loop,
)


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
