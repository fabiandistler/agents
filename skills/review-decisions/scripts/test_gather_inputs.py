"""gather_inputs.py through its command line, with fake gh and az on PATH.

Run from the repo root with: python3 -m pytest skills/review-decisions/scripts/
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.fixture
def repo(tmp_path):
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
        env = {
            "PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
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


def github_routes(forge, check_runs, body="Adds the widget.\n\nCloses #12"):
    forge.route(
        "pulls?head=acme:feature",
        [
            {
                "number": 7,
                "title": "Add widget",
                "body": body,
                "base": {"ref": "main"},
                "head": {"sha": "abc123"},
            }
        ],
    )
    forge.route("issues/12", {"number": 12, "title": "Widget", "body": "Build the widget."})
    forge.route(
        "commits/abc123/check-runs", {"total_count": len(check_runs), "check_runs": check_runs}
    )
    forge.route("commits/abc123/status", {"state": "pending", "statuses": []})


def test_github_reads_pr_issue_and_ci(tmp_path, repo):
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)
    github_routes(forge, [{"name": "ci", "status": "completed", "conclusion": "success"}])
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert result.returncode == 0, result.stderr
    found = manifest(out)
    assert found["forge"] == "github"
    assert found["pr"] == {"number": 7, "target_branch": "main", "head_sha": "abc123"}
    assert found["issues"] == ["12"]
    assert found["unchecked"] == []
    assert "Add widget" in (out / "pr.md").read_text()
    assert "Build the widget." in (out / "issue.md").read_text()
    ci = json.loads((out / "ci.json").read_text())
    assert ci == {"state": "green", "checks": [{"name": "ci", "state": "green"}]}


def azure_routes(forge, policies, work_items=({"id": 31},)):
    forge.route(
        "repos pr list --source-branch feature",
        [
            {
                "pullRequestId": 5,
                "title": "Add widget",
                "description": "Adds the widget.",
                "targetRefName": "refs/heads/main",
                "lastMergeSourceCommit": {"commitId": "def456"},
            }
        ],
    )
    forge.route("repos pr work-item list --id 5", list(work_items))
    forge.route(
        "boards work-item show --id 31",
        {"id": 31, "fields": {"System.Title": "Widget", "System.Description": "Build it."}},
    )
    forge.route("repos pr policy list --id 5", policies)


def policy(type_name, status, display=None):
    settings = {"displayName": display} if display else {}
    return {
        "status": status,
        "configuration": {"type": {"displayName": type_name}, "settings": settings},
    }


def test_azure_reads_pr_work_item_and_ci(tmp_path, repo):
    git(repo, "remote", "add", "origin", AZ_REMOTE)
    forge = Forge(tmp_path)
    azure_routes(
        forge,
        [
            policy("Build", "approved", "PR build"),
            policy("Minimum number of reviewers", "rejected"),
        ],
    )
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert result.returncode == 0, result.stderr
    found = manifest(out)
    assert found["forge"] == "azure"
    assert found["pr"] == {"number": 5, "target_branch": "main", "head_sha": "def456"}
    assert found["issues"] == ["31"]
    assert found["unchecked"] == []
    assert "Adds the widget." in (out / "pr.md").read_text()
    assert "Build it." in (out / "issue.md").read_text()
    ci = json.loads((out / "ci.json").read_text())
    assert ci == {"state": "green", "checks": [{"name": "PR build", "state": "green"}]}


def assert_fallback(result, out, reason):
    assert result.returncode == 3, result.stderr
    found = manifest(out)
    assert found["files"] == {}
    assert [u["input"] for u in found["unchecked"]] == ["pr", "issue", "ci"]
    assert all(reason in u["reason"] for u in found["unchecked"])
    assert not (out / "ci.json").exists()


@pytest.mark.parametrize("remote", [GH_REMOTE, AZ_REMOTE])
def test_missing_cli_falls_back_and_names_what_is_unchecked(tmp_path, repo, remote):
    git(repo, "remote", "add", "origin", remote)
    forge = Forge(tmp_path, clis=())
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert_fallback(result, out, "is not installed")


@pytest.mark.parametrize("remote", [GH_REMOTE, AZ_REMOTE])
def test_failing_cli_falls_back(tmp_path, repo, remote):
    git(repo, "remote", "add", "origin", remote)
    forge = Forge(tmp_path)
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert_fallback(result, out, "failed (exit 1)")


@pytest.mark.parametrize("remote", ["https://gitlab.com/acme/widget.git", None])
def test_unsupported_or_missing_remote_falls_back(tmp_path, repo, remote):
    if remote:
        git(repo, "remote", "add", "origin", remote)
    forge = Forge(tmp_path)
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert_fallback(result, out, "neither GitHub nor Azure DevOps")
    assert forge.calls() == []


def test_failed_issue_read_keeps_pr_and_ci(tmp_path, repo):
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)
    forge.route("issues/12", "", code=1)
    github_routes(forge, [{"name": "ci", "status": "completed", "conclusion": "success"}])
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert result.returncode == 3, result.stderr
    found = manifest(out)
    assert sorted(found["files"]) == ["ci", "pr"]
    assert [u["input"] for u in found["unchecked"]] == ["issue"]
    assert "failed (exit 1)" in found["unchecked"][0]["reason"]


def test_pr_without_closing_issue_marks_issue_unchecked(tmp_path, repo):
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)
    github_routes(forge, [], body="Adds the widget.")
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert result.returncode == 3, result.stderr
    found = manifest(out)
    assert found["unchecked"] == [
        {"input": "issue", "reason": "the PR text names no closing issue (Closes #n)"}
    ]
    assert json.loads((out / "ci.json").read_text()) == {"state": "none", "checks": []}


@pytest.mark.parametrize(
    ("runs", "state"),
    [
        (
            [
                {"name": "lint", "status": "completed", "conclusion": "success"},
                {"name": "test", "status": "completed", "conclusion": "failure"},
            ],
            "failing",
        ),
        (
            [
                {"name": "lint", "status": "completed", "conclusion": "skipped"},
                {"name": "test", "status": "in_progress", "conclusion": None},
            ],
            "pending",
        ),
    ],
)
def test_github_ci_state_is_failing_or_pending_unless_all_green(tmp_path, repo, runs, state):
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)
    github_routes(forge, runs)
    out = tmp_path / "out"

    forge.run(repo, out)

    assert json.loads((out / "ci.json").read_text())["state"] == state


def test_azure_rejected_build_is_failing(tmp_path, repo):
    git(repo, "remote", "add", "origin", AZ_REMOTE)
    forge = Forge(tmp_path)
    azure_routes(forge, [policy("Build", "rejected", "PR build"), policy("Status", "running")])
    out = tmp_path / "out"

    forge.run(repo, out)

    ci = json.loads((out / "ci.json").read_text())
    assert ci == {
        "state": "failing",
        "checks": [
            {"name": "PR build", "state": "failing"},
            {"name": "Status", "state": "pending"},
        ],
    }


def test_no_credential_in_argv_or_output(tmp_path, repo):
    secret = "not-a-real-credential-7f3a"  # noqa: S105 -- fake value to trace.
    git(
        repo,
        "remote",
        "add",
        "origin",
        f"https://x-access-token:{secret}@github.com/acme/widget.git",
    )
    forge = Forge(tmp_path)
    github_routes(forge, [])
    out = tmp_path / "out"

    result = forge.run(repo, out, extra_env={"GH_TOKEN": secret})

    assert result.returncode == 0, result.stderr
    assert forge.calls()
    assert all(secret not in arg for call in forge.calls() for arg in call)
    assert secret not in result.stdout + result.stderr
    assert all(secret not in path.read_text() for path in out.iterdir())


GH_WRITE_FLAGS = {"-X", "--method", "-f", "--raw-field", "-F", "--field", "--input"}
AZ_READ_VERBS = {"show", "list"}


def is_forge_read(call):
    cli, *args = call
    if cli == "gh":
        return args[:1] == ["api"] and not GH_WRITE_FLAGS.intersection(args)
    words = [arg for arg in args if not arg.startswith("-")]
    return cli == "az" and bool(AZ_READ_VERBS.intersection(words[2:4]))


@pytest.mark.parametrize(
    ("remote", "routes"),
    [
        (GH_REMOTE, lambda f: github_routes(f, [{"name": "ci", "status": "completed"}])),
        (AZ_REMOTE, lambda f: azure_routes(f, [policy("Build", "approved")])),
    ],
)
def test_every_forge_call_is_a_read(tmp_path, repo, remote, routes):
    git(repo, "remote", "add", "origin", remote)
    forge = Forge(tmp_path)
    routes(forge)

    forge.run(repo, tmp_path / "out")

    assert forge.calls()
    assert [call for call in forge.calls() if not is_forge_read(call)] == []
