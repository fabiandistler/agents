"""Fake gh and az CLIs and a git repository for the gather_inputs.py test suites.

The fakes answer from routes a test registers and log every argv, so a suite
can assert both the manifest and the forge calls made.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("gather_inputs.py")

# A fake forge CLI: answers the first route whose key occurs in its joined
# argv, logs every argv to $FAKE_LOG, and exits 1 when no route matches.
FAKE_CLI = """\
import json, os, sys
argv = sys.argv[1:]
joined = " ".join(argv)
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps([os.path.basename(sys.argv[0]), *argv]) + "\\n")
for key, stdout, code in json.load(open(os.environ["FAKE_ROUTES"])):
    if key in joined:
        sys.stdout.write(stdout)
        sys.exit(code)
sys.stderr.write("fake: no route\\n")
sys.exit(1)
"""

GH_REMOTE = "https://github.com/acme/widget.git"
AZ_REMOTE = "https://dev.azure.com/acme/widget/_git/widget"


def git(repo, *args):
    subprocess.run(  # noqa: S603 -- test git setup with argv, no shell.
        ["git", "-C", str(repo), *args],  # noqa: S607 -- git from PATH.
        check=True,
        capture_output=True,
    )


def make_repo(tmp_path):
    """A git repository with one commit on branch `feature`."""
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "feature")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("a\n")
    git(path, "add", "a.txt")
    git(path, "commit", "-q", "-m", "init")
    return path


class Forge:
    """Fake CLIs on PATH plus the routes they answer."""

    def __init__(self, tmp_path, clis=("gh", "az")):
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.log = tmp_path / "cli.log"
        self.routes_file = tmp_path / "routes.json"
        self.routes = []
        for name in clis:
            cli = self.bin / name
            cli.write_text(f"#!{sys.executable}\n{FAKE_CLI}")
            cli.chmod(0o755)

    def route(self, key, payload, code=0):
        stdout = payload if isinstance(payload, str) else json.dumps(payload)
        self.routes.append([key, stdout, code])

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def run(self, repo, out, *args, extra_env=None):
        self.routes_file.write_text(json.dumps(self.routes))
        # Only the fake CLIs and git: a gh or az installed on the machine
        # (GitHub runners have both) must not answer for a missing fake.
        git_bin = shutil.which("git")
        assert git_bin, "git is needed to run these tests"
        link = self.bin / "git"
        if not link.exists():
            link.symlink_to(git_bin)
        env = {
            "PATH": str(self.bin),
            "HOME": os.environ["HOME"],
            "FAKE_LOG": str(self.log),
            "FAKE_ROUTES": str(self.routes_file),
            **(extra_env or {}),
        }
        return subprocess.run(  # noqa: S603 -- test invokes its own script with argv, no shell.
            [sys.executable, str(SCRIPT), "--repo", str(repo), "--out", str(out), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )


def manifest(out):
    return json.loads((out / "inputs.json").read_text())


def assert_fallback(result, out, reason):
    assert result.returncode == 3, result.stderr
    found = manifest(out)
    assert found["files"] == {}
    assert [u["input"] for u in found["unchecked"]] == ["pr", "issue", "ci"]
    assert all(reason in u["reason"] for u in found["unchecked"])
    assert not (out / "ci.json").exists()
