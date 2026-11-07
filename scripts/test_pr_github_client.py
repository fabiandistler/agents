"""Tests for the REST client and the CLI of scripts/pr_github.py; none touches the network."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import urllib.error
from email.message import Message

import pr_github
import pr_github_client
import pytest
from pr_github_fake import NUMBER, REPO, SCRIPT, FakeClient, api_file, fetch


def test_missing_token_without_an_injected_client_raises_before_any_request(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(pr_github_client.MissingTokenError):
        pr_github.fetch_context(REPO, NUMBER)

    with pytest.raises(pr_github_client.MissingTokenError):
        pr_github.fetch_context(REPO, NUMBER, token="")


class FakeHTTPResponse:
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None) -> None:
        self._body = body
        self.status = status
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def test_github_client_sends_auth_and_parses_json():
    captured = {}

    def opener(request, timeout=None):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeHTTPResponse(b'{"ok": true}')

    client = pr_github_client.GitHubClient("s3cret-token", opener=opener)

    response = client.get("/repos/o/r", params={"page": 2})

    assert response.json() == {"ok": True}
    request = captured["request"]
    assert request.full_url == "https://api.github.com/repos/o/r?page=2"
    assert request.get_header("Authorization") == "Bearer s3cret-token"
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert captured["timeout"] == 30


@pytest.mark.parametrize(
    ("method", "payload"),
    [
        ("post", {"a": 1}),
        ("patch", {"a": 1}),
        ("delete", None),
    ],
)
def test_client_write_helpers_send_the_named_method(method, payload):
    captured = {}

    def opener(request, timeout=None):
        captured["request"] = request
        return FakeHTTPResponse(b"{}")

    client = pr_github_client.GitHubClient("token", opener=opener)

    getattr(client, method)("/repos/o/r/thing", payload)

    request = captured["request"]
    assert request.get_method() == method.upper()
    if payload is None:
        assert request.data is None
    else:
        assert json.loads(request.data) == payload


def test_http_error_becomes_fetch_error_without_leaking_the_token():
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            Message(),
            io.BytesIO(b'{"message": "nope"}'),
        )

    client = pr_github_client.GitHubClient("s3cret-token", opener=opener)

    with pytest.raises(pr_github_client.FetchError) as info:
        client.get("/repos/o/r")

    assert info.value.status == 403
    assert "403" in str(info.value)
    assert "s3cret-token" not in str(info.value)


def test_network_error_becomes_fetch_error():
    def opener(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    client = pr_github_client.GitHubClient("token", opener=opener)

    with pytest.raises(pr_github_client.FetchError) as info:
        client.get("/repos/o/r")

    assert "connection refused" in str(info.value)


def test_cli_writes_the_context_and_exits_zero(tmp_path, monkeypatch, capsys):
    context = fetch(FakeClient())
    monkeypatch.setattr(pr_github, "fetch_context", lambda repo, number, token=None: context)
    output = tmp_path / "context.json"

    code = pr_github.main(["--pr", str(NUMBER), "--repo", REPO, "--output", str(output)])

    assert code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == context
    assert json.loads(capsys.readouterr().out)["output"] == str(output)


def test_cli_prints_a_bounded_summary_without_output(monkeypatch, capsys):
    # The full context carries the diff (up to 400 KB); stdout gets a summary.
    context = fetch(
        FakeClient(
            file_pages=([api_file("docs/guide.md")],),
            diff="+" + "x" * 300_000 + "\n",
        )
    )
    monkeypatch.setattr(pr_github, "fetch_context", lambda repo, number, token=None: context)

    code = pr_github.main(["--pr", str(NUMBER), "--repo", REPO])

    out = capsys.readouterr().out
    assert code == 0
    assert len(out) < 1000
    summary = json.loads(out)
    assert "diff" not in summary
    assert summary["number"] == NUMBER
    assert summary["head_sha"] == "abc123"
    assert summary["files"] == 1
    assert summary["diff_status"] == "complete"
    assert summary["diff_bytes"] == 300_002
    assert summary["output"] is None


def test_cli_maps_missing_token_to_exit_five(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    code = pr_github.main(["--pr", str(NUMBER), "--repo", REPO])

    assert code == 5


def test_cli_maps_fetch_failure_to_exit_four(monkeypatch):
    def fail(repo, number, token=None):
        raise pr_github_client.FetchError("boom")

    monkeypatch.setattr(pr_github, "fetch_context", fail)

    assert pr_github.main(["--pr", str(NUMBER), "--repo", REPO]) == 4


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--pr", str(NUMBER)],
        ["--repo", REPO],
        ["--pr", "zero", "--repo", REPO],
        ["--pr", "0", "--repo", REPO],
        ["--pr", str(NUMBER), "--repo", "no-slash"],
        ["--pr", str(NUMBER), "--repo", REPO, "--unknown"],
    ],
)
def test_cli_usage_errors_exit_two(argv):
    assert pr_github.main(argv) == 2


def test_cli_output_write_failure_exits_six(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pr_github,
        "fetch_context",
        lambda repo, number, token=None: {"schema_version": 1, "files": []},
    )

    assert pr_github.main(["--pr", str(NUMBER), "--repo", REPO, "--output", str(tmp_path)]) == 6


def test_cli_help_is_short_and_documents_exit_codes():
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and script path, no shell
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert len(result.stdout.splitlines()) < 25
    assert "usage:" in result.stdout
    assert "exit:" in result.stdout
    assert result.stderr == ""
