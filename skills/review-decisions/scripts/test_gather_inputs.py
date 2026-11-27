"""gather_inputs.py on a GitHub or Azure DevOps remote, with fake gh and az on PATH.

Run from the repo root with: python3 -m pytest skills/review-decisions/scripts/
"""

import json

import pytest
from gather_inputs_testkit import (
    AZ_REMOTE,
    GH_REMOTE,
    Forge,
    assert_fallback,
    git,
    make_repo,
    manifest,
)


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


# Full argv, CLI name included: the fake answers only an exact match.
GH_PULLS_FOR_BRANCH = ["gh", "api", "repos/acme/widget/pulls?head=acme:feature&state=open"]
GH_PULL_7 = ["gh", "api", "repos/acme/widget/pulls/7"]
GH_ISSUE_12 = ["gh", "api", "repos/acme/widget/issues/12"]
AZ_PR_LIST = ["az", "repos", "pr", "list", "--source-branch", "feature", "--status", "active"]
AZ_PR_SHOW = ["az", "repos", "pr", "show", "--id", "5"]


def github_routes(forge, check_runs, body="Adds the widget.\n\nCloses #12", mergeable=True):
    pull = {
        "number": 7,
        "title": "Add widget",
        "body": body,
        "base": {"ref": "main"},
        "head": {"sha": "abc123"},
    }
    # The list endpoint returns no mergeability; only the single-PR endpoint does.
    forge.route(GH_PULLS_FOR_BRANCH, [pull])
    forge.route(GH_PULL_7, {**pull, "mergeable": mergeable})
    forge.route(GH_ISSUE_12, {"number": 12, "title": "Widget", "body": "Build the widget."})
    forge.route(
        ["gh", "api", "repos/acme/widget/commits/abc123/check-runs?per_page=100"],
        {"total_count": len(check_runs), "check_runs": check_runs},
    )
    forge.route(
        ["gh", "api", "repos/acme/widget/commits/abc123/status"],
        {"state": "pending", "statuses": []},
    )


def test_github_reads_pr_issue_and_ci(tmp_path, repo):
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)
    github_routes(forge, [{"name": "ci", "status": "completed", "conclusion": "success"}])
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert result.returncode == 0, result.stderr
    found = manifest(out)
    assert found["forge"] == "github"
    assert found["pr"] == {
        "number": 7,
        "target_branch": "main",
        "head_sha": "abc123",
        "merge_status": "clean",
    }
    assert found["issues"] == ["12"]
    assert found["unchecked"] == []
    assert "Add widget" in (out / "pr.md").read_text()
    assert "Build the widget." in (out / "issue.md").read_text()
    ci = json.loads((out / "ci.json").read_text())
    assert ci == {"state": "green", "checks": [{"name": "ci", "state": "green"}]}


def azure_routes(forge, policies, work_items=({"id": 31},), merge_status="succeeded"):
    pull = {
        "pullRequestId": 5,
        "title": "Add widget",
        "description": "Adds the widget.",
        "targetRefName": "refs/heads/main",
        "lastMergeSourceCommit": {"commitId": "def456"},
        "mergeStatus": merge_status,
    }
    forge.route(az_argv(AZ_PR_LIST), [pull])
    forge.route(az_argv(AZ_PR_SHOW), pull)
    forge.route(az_argv(["az", "repos", "pr", "work-item", "list", "--id", "5"]), list(work_items))
    show = ["az", "boards", "work-item", "show", "--id", "31"]
    fields = ["--fields", "System.Title,System.Description", "--expand", "none"]
    forge.route(
        az_argv(show + fields),
        {"id": 31, "fields": {"System.Title": "Widget", "System.Description": "Build it."}},
    )
    forge.route(az_argv(["az", "repos", "pr", "policy", "list", "--id", "5"]), policies)


def az_argv(command):
    """`command` with the flags gather_inputs.py appends to every az call."""
    return [*command, "--detect", "true", "--output", "json"]


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
    assert found["pr"] == {
        "number": 5,
        "target_branch": "main",
        "head_sha": "def456",
        "merge_status": "clean",
    }
    assert found["issues"] == ["31"]
    assert found["unchecked"] == []
    assert "Adds the widget." in (out / "pr.md").read_text()
    assert "Build it." in (out / "issue.md").read_text()
    ci = json.loads((out / "ci.json").read_text())
    assert ci == {"state": "green", "checks": [{"name": "PR build", "state": "green"}]}


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


@pytest.mark.parametrize(
    "remote",
    [
        "https://gitlab.com/acme/widget.git",
        "https://evil.example/github.com/acme/widget.git",
        "https://github.com.evil.example/acme/widget.git",
        "https://evil.example/dev.azure.com/acme/_git/widget",
        None,
    ],
)
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
    forge.route(GH_ISSUE_12, "", code=1)
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


def test_a_failing_cli_does_not_echo_its_stderr(tmp_path, repo):
    # The forge's error text may quote the PR or the issue; only the reason is reported.
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)

    result = forge.run(repo, tmp_path / "out")

    assert result.returncode == 3
    assert "fake: no route" not in result.stderr


def test_a_usage_error_exits_1(tmp_path, repo):
    result = Forge(tmp_path).run(repo, tmp_path / "out", "--pr", "seven")

    assert result.returncode == 1
    assert "usage:" in result.stderr


def test_the_forge_is_always_read_from_origin(tmp_path, repo):
    result = Forge(tmp_path).run(repo, tmp_path / "out", "--remote", "upstream")

    assert result.returncode == 1
    assert "--remote" in result.stderr


def test_a_directory_outside_git_exits_2(tmp_path, assert_exit_cause):
    plain = tmp_path / "plain"
    plain.mkdir()

    result = Forge(tmp_path).run(plain, tmp_path / "out")

    _, stderr = assert_exit_cause(result, 2)
    assert "--repo is not inside a git repository" in stderr
    assert not (tmp_path / "out" / "inputs.json").exists()


@pytest.mark.parametrize(
    "remote",
    [
        "git@github.com:acme/widget.git",
        "ssh://git@github.com/acme/widget.git",
        "git@ssh.dev.azure.com:v3/acme/widget/widget",
        "https://acme.visualstudio.com/widget/_git/widget",
    ],
)
def test_ssh_and_legacy_remotes_are_recognised(tmp_path, repo, remote):
    git(repo, "remote", "add", "origin", remote)
    forge = Forge(tmp_path, clis=())
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert_fallback(result, out, "is not installed")


def test_no_pull_request_for_the_branch_points_to_pr_for_forks(tmp_path, repo):
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)
    forge.route(GH_PULLS_FOR_BRANCH, [])
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert result.returncode == 3, result.stderr
    reasons = [u["reason"] for u in manifest(out)["unchecked"]]
    assert all("--pr" in reason for reason in reasons)


@pytest.mark.parametrize(
    ("mergeable", "status"),
    [(True, "clean"), (False, "conflicts"), (None, "unknown")],
)
def test_github_merge_status_comes_from_the_single_pr_endpoint(tmp_path, repo, mergeable, status):
    # GitHub returns mergeable null while it computes the test merge in the background.
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)
    github_routes(forge, [], mergeable=mergeable)
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert result.returncode == 0, result.stderr
    assert manifest(out)["pr"]["merge_status"] == status
    assert GH_PULL_7 in forge.calls()


def test_github_pr_number_reads_the_single_pr_endpoint_once(tmp_path, repo):
    git(repo, "remote", "add", "origin", GH_REMOTE)
    forge = Forge(tmp_path)
    github_routes(forge, [], mergeable=False)
    out = tmp_path / "out"

    result = forge.run(repo, out, "--pr", "7")

    assert result.returncode == 0, result.stderr
    assert manifest(out)["pr"]["merge_status"] == "conflicts"
    pulls = [call for call in forge.calls() if "pulls" in call[-1]]
    assert pulls == [GH_PULL_7]


@pytest.mark.parametrize(
    ("merge_status", "status"),
    [
        ("succeeded", "clean"),
        ("conflicts", "conflicts"),
        ("queued", "unknown"),
        ("notSet", "unknown"),
        ("rejectedByPolicy", "unknown"),
        ("failure", "unknown"),
    ],
)
def test_azure_merge_status_maps_to_clean_conflicts_or_unknown(
    tmp_path, repo, merge_status, status
):
    git(repo, "remote", "add", "origin", AZ_REMOTE)
    forge = Forge(tmp_path)
    azure_routes(forge, [policy("Build", "approved")], merge_status=merge_status)
    out = tmp_path / "out"

    result = forge.run(repo, out)

    assert result.returncode == 0, result.stderr
    assert manifest(out)["pr"]["merge_status"] == status


def test_azure_pr_number_reads_that_pull_request(tmp_path, repo):
    git(repo, "remote", "add", "origin", AZ_REMOTE)
    forge = Forge(tmp_path)
    azure_routes(forge, [policy("Build", "approved")])
    out = tmp_path / "out"

    result = forge.run(repo, out, "--pr", "5")

    assert result.returncode == 0, result.stderr
    assert manifest(out)["pr"]["number"] == 5
    assert az_argv(AZ_PR_SHOW) in forge.calls()
    assert az_argv(AZ_PR_LIST) not in forge.calls()
