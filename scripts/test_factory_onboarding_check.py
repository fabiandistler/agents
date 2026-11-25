"""Tests for the read-only factory onboarding check (scripts/factory_onboarding_check.py)."""

from __future__ import annotations

from dataclasses import dataclass, field

import factory_onboarding_check as check
import pytest
from factory_handoff import STATE_LABELS
from pr_github_client import FetchError, Response
from pr_github_fake import contents_response, json_response

REPO = "octo/target"
BRANCH = "trunk"
SHA = "a" * 40
OTHER_SHA = "b" * 40
SENTINEL = "SENTINEL-c0ffee-do-not-print"
BY_NAME_BLOCK = (
    "    secrets:\n      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}\n"
)
WORKFLOWS_PATH = f"/repos/{REPO}/contents/.github/workflows"

IMPLEMENTER_WITH = "    with:\n      check_command: scripts/check.sh\n"
CALLERS = {
    "factory-implementer.yml": IMPLEMENTER_WITH + "      queue_workflow: implementer-queue.yml\n",
    "factory-implementer-queue.yml": None,
    "factory-pr-review.yml": "",
    "factory-issue-triage.yml": "",
    "factory-triage-label.yml": None,
    "factory-rework.yml": "    with:\n      check_command: scripts/check.sh\n",
    "factory-fix-task.yml": None,
}


def caller(
    factory_file: str,
    *,
    ref: str = SHA,
    permissions: str = "permissions: {}\n",
    with_block: str | None = None,
    secrets: str | None = None,
) -> str:
    if with_block is None:
        with_block = CALLERS[factory_file] or ""
    if secrets is None:
        secrets = "" if CALLERS[factory_file] is None else BY_NAME_BLOCK
    return (
        f"# {SENTINEL}\nname: x\non:\n  issues:\n    types: [opened]\n{permissions}"
        "jobs:\n  run:\n    permissions:\n      issues: write\n"
        f"    uses: fabiandistler/agents/.github/workflows/{factory_file}@{ref} # 2026-11-14\n"
        f"{with_block}{secrets}"
    )


def all_callers(**overrides: str) -> dict[str, str]:
    files = {f"{name.removeprefix('factory-')}": caller(name) for name in check.REQUIREMENTS}
    files.update(overrides)
    return files


@dataclass
class RoutedFake:
    """Answers GETs from a route table and records every call with its method."""

    private: bool = True
    labels: tuple[str, ...] = STATE_LABELS
    workflows: dict[str, str] | None = field(default_factory=all_callers)
    compare_status: str | None = "behind"
    errors: dict[str, FetchError] = field(default_factory=dict)
    calls: list[tuple[str, str, dict]] = field(default_factory=list)

    def get(self, path: str, params: dict | None = None, accept: str | None = None) -> Response:
        self.calls.append(("GET", path, dict(params or {})))
        if path in self.errors:
            raise self.errors[path]
        if path == f"/repos/{REPO}":
            return json_response({"private": self.private, "default_branch": BRANCH})
        if path == f"/repos/{REPO}/labels":
            page = (params or {}).get("page", 1)
            return json_response([{"name": name} for name in self.labels] if page == 1 else [])
        if path == WORKFLOWS_PATH:
            if self.workflows is None:
                raise FetchError(f"GitHub API returned 404 for {path}", status=404)
            listing = [
                {"type": "file", "path": f".github/workflows/{name}"} for name in self.workflows
            ]
            return json_response(listing)
        if path.startswith(WORKFLOWS_PATH + "/"):
            name = path.removeprefix(WORKFLOWS_PATH + "/")
            return json_response(contents_response((self.workflows or {})[name]))
        if path.startswith("/repos/fabiandistler/agents/compare/main..."):
            if self.compare_status is None:
                raise FetchError(f"GitHub API returned 404 for {path}", status=404)
            return json_response({"status": self.compare_status})
        raise AssertionError(f"unexpected GET {path}")

    def _write(self, method: str, path: str) -> Response:
        self.calls.append((method, path, {}))
        raise AssertionError(f"unexpected {method} {path}")

    def post(self, path: str, payload: dict | None = None) -> Response:
        return self._write("POST", path)

    def patch(self, path: str, payload: dict | None = None) -> Response:
        return self._write("PATCH", path)

    def delete(self, path: str, payload: dict | None = None) -> Response:
        return self._write("DELETE", path)


def run(fake: RoutedFake, capsys, monkeypatch) -> tuple[int, dict[str, tuple[str, str]], str]:
    monkeypatch.setenv("GH_TOKEN", "test-token")
    code = check.main(["--repo", REPO], client=fake)
    captured = capsys.readouterr()
    lines = {}
    for line in captured.out.splitlines():
        status, item, detail = line.split("\t")
        lines[item] = (status, detail)
    return code, lines, captured.err


def test_fully_onboarded_private_repo_exits_0(capsys, monkeypatch):
    code, lines, _ = run(RoutedFake(), capsys, monkeypatch)

    assert code == 0
    assert list(lines) == [
        "labels",
        "visibility",
        "rulesets",
        "app-installation",
        "secret:CLAUDE_CODE_OAUTH_TOKEN",
        "actions-policy",
        "caller:factory-implementer.yml",
        "caller:factory-implementer-queue.yml",
        "caller:factory-pr-review.yml",
        "caller:factory-issue-triage.yml",
        "caller:factory-triage-label.yml",
        "caller:factory-rework.yml",
        "caller:factory-fix-task.yml",
        "pin",
    ]
    assert lines["labels"][0] == "OK"
    assert lines["visibility"] == ("OK", "private")
    assert lines["rulesets"][0] == "OK"
    assert "push guard" in lines["rulesets"][1]
    assert lines["caller:factory-pr-review.yml"] == ("OK", ".github/workflows/pr-review.yml")
    assert lines["pin"][0] == "OK"


def test_missing_label_is_named(capsys, monkeypatch):
    fake = RoutedFake(labels=tuple(label for label in STATE_LABELS if label != "wontfix"))

    code, lines, _ = run(fake, capsys, monkeypatch)

    assert code == 1
    assert lines["labels"] == ("MISSING", "absent: wontfix")


def test_public_repo_rulesets_cannot_be_verified(capsys, monkeypatch):
    code, lines, _ = run(RoutedFake(private=False), capsys, monkeypatch)

    assert code == 0
    assert lines["visibility"] == ("OK", "public")
    assert lines["rulesets"][0] == "CANNOT-VERIFY"


def test_manual_items_are_cannot_verify_without_a_request(capsys, monkeypatch):
    fake = RoutedFake()
    _, lines, _ = run(fake, capsys, monkeypatch)

    for item in ("app-installation", "secret:CLAUDE_CODE_OAUTH_TOKEN", "actions-policy"):
        assert lines[item][0] == "CANNOT-VERIFY"
        assert f"https://github.com/{REPO}/settings" in lines[item][1]
    for _, path, _ in fake.calls:
        assert not path.endswith("/installation")
        assert "/actions/secrets" not in path
        assert "/actions/permissions" not in path
        assert "/rulesets" not in path


def test_contents_requests_carry_the_default_branch(capsys, monkeypatch):
    fake = RoutedFake()
    run(fake, capsys, monkeypatch)

    contents = [(path, params) for _, path, params in fake.calls if "/contents/" in path]
    assert contents
    assert all(params == {"ref": BRANCH} for _, params in contents)


def test_no_workflows_directory_makes_every_caller_and_the_pin_missing(capsys, monkeypatch):
    code, lines, _ = run(RoutedFake(workflows=None), capsys, monkeypatch)

    assert code == 1
    for name in check.REQUIREMENTS:
        assert lines[f"caller:{name}"] == ("MISSING", f"no workflow on {BRANCH} calls it")
    assert lines["pin"][0] == "MISSING"


def test_an_implementer_without_a_queue_caller_is_missing(capsys, monkeypatch):
    # Without one, the claim releases blocked and at-capacity issues instead of
    # letting them wait (fabiandistler/repo-maintenance#205).
    workflows = all_callers()
    del workflows["implementer-queue.yml"]

    code, lines, _ = run(RoutedFake(workflows=workflows), capsys, monkeypatch)

    assert code == 1
    assert lines["caller:factory-implementer.yml"][0] == "OK"
    assert lines["caller:factory-implementer-queue.yml"] == (
        "MISSING",
        f"no workflow on {BRANCH} calls it",
    )


def test_one_missing_caller(capsys, monkeypatch):
    workflows = all_callers()
    del workflows["implementer.yml"]

    code, lines, _ = run(RoutedFake(workflows=workflows), capsys, monkeypatch)

    assert code == 1
    assert lines["caller:factory-implementer.yml"][0] == "MISSING"
    assert lines["caller:factory-triage-label.yml"][0] == "OK"
    assert lines["pin"][0] == "OK"


@pytest.mark.parametrize(
    ("name", "text", "problem"),
    [
        (
            "pr-review.yml",
            caller("factory-pr-review.yml", permissions=""),
            "no top-level permissions: {}",
        ),
        (
            "pr-review.yml",
            caller("factory-pr-review.yml", secrets="    secrets: inherit\n"),
            "uses secrets: inherit",
        ),
        (
            "implementer.yml",
            caller("factory-implementer.yml", with_block="    with:\n      issue: '1'\n"),
            "does not pass input check_command",
        ),
        (
            "issue-triage.yml",
            caller("factory-issue-triage.yml", secrets=""),
            "does not pass secret CLAUDE_CODE_OAUTH_TOKEN",
        ),
        (
            "implementer.yml",
            caller("factory-implementer.yml", with_block=IMPLEMENTER_WITH),
            "does not pass input queue_workflow",
        ),
    ],
)
def test_incomplete_caller_is_missing(capsys, monkeypatch, name, text, problem):
    fake = RoutedFake(workflows=all_callers(**{name: text}))

    code, lines, _ = run(fake, capsys, monkeypatch)

    status, detail = lines[f"caller:factory-{name}"]
    assert code == 1
    assert status == "MISSING"
    assert problem in detail
    assert detail.startswith(f".github/workflows/{name}: ")


def test_tag_pin_is_missing(capsys, monkeypatch):
    workflows = all_callers(**{"pr-review.yml": caller("factory-pr-review.yml", ref="v1")})

    code, lines, _ = run(RoutedFake(workflows=workflows), capsys, monkeypatch)

    assert code == 1
    assert lines["pin"] == ("MISSING", "not a full commit SHA: .github/workflows/pr-review.yml@v1")


def test_unequal_shas_are_named(capsys, monkeypatch):
    workflows = all_callers(**{"pr-review.yml": caller("factory-pr-review.yml", ref=OTHER_SHA)})

    code, lines, _ = run(RoutedFake(workflows=workflows), capsys, monkeypatch)

    assert code == 1
    status, detail = lines["pin"]
    assert status == "MISSING"
    assert f".github/workflows/pr-review.yml@{OTHER_SHA}" in detail
    assert f".github/workflows/implementer.yml@{SHA}" in detail


@pytest.mark.parametrize("compare_status", ["ahead", "diverged", None])
def test_sha_not_on_main_is_missing(capsys, monkeypatch, compare_status):
    fake = RoutedFake(compare_status=compare_status)

    code, lines, _ = run(fake, capsys, monkeypatch)

    assert code == 1
    assert lines["pin"][0] == "MISSING"
    assert ("GET", f"/repos/fabiandistler/agents/compare/main...{SHA}", {}) in fake.calls


def test_identical_sha_is_ok(capsys, monkeypatch):
    _, lines, _ = run(RoutedFake(compare_status="identical"), capsys, monkeypatch)

    assert lines["pin"][0] == "OK"


def test_file_content_and_token_never_printed_and_only_gets(capsys, monkeypatch):
    fake = RoutedFake(
        workflows=all_callers(**{"pr-review.yml": caller("factory-pr-review.yml", permissions="")})
    )

    monkeypatch.setenv("GH_TOKEN", "test-token")
    check.main(["--repo", REPO], client=fake)
    captured = capsys.readouterr()

    for stream in (captured.out, captured.err):
        assert SENTINEL not in stream
        assert "test-token" not in stream
    assert fake.calls
    assert {method for method, _, _ in fake.calls} == {"GET"}


def test_api_error_exits_3_naming_endpoint_and_status(capsys, monkeypatch):
    path = f"/repos/{REPO}/labels"
    fake = RoutedFake(errors={path: FetchError(f"GitHub API returned 500 for {path}", 500)})

    code, _, err = run(fake, capsys, monkeypatch)

    assert code == 3
    assert err.strip() == f"factory_onboarding_check.py: GitHub API returned 500 for {path}"


@pytest.mark.parametrize("argv", [["--repo", "not-a-repo"], ["--repo", "a/b/c"], []])
def test_bad_repo_is_a_usage_error(capsys, monkeypatch, argv):
    monkeypatch.setenv("GH_TOKEN", "test-token")
    fake = RoutedFake()

    assert check.main(argv, client=fake) == 2
    assert fake.calls == []


def test_missing_token_is_a_usage_error(capsys, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    fake = RoutedFake()

    assert check.main(["--repo", REPO], client=fake) == 2
    assert "GH_TOKEN" in capsys.readouterr().err
    assert fake.calls == []


def test_help_is_short(capsys):
    assert check.main(["--help"]) == 0
    out = capsys.readouterr().out

    assert len(out.splitlines()) < 25
    assert "--repo" in out
    assert "Exit:" in out


def test_bad_repo_value_prints_the_expected_form(capsys, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    code = check.main(["--repo", "nonsense"])
    assert code == 2
    assert "expected OWNER/NAME" in capsys.readouterr().err
