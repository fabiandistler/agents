"""The GitHub REST transport shared by the PR review pipeline.

``GitHubClient`` is a small stdlib client with an injectable opener, so tests
run without a network. ``FetchError`` is the one error every GitHub call
raises; ``REPO_PATTERN`` is the OWNER/REPO shape every API path is built from.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

BASE_URL = "https://api.github.com"
TIMEOUT_SECONDS = 30
JSON_ACCEPT = "application/vnd.github+json"
USER_AGENT = "agents-pr-review"
API_VERSION = "2022-11-28"

REPO_PATTERN = re.compile(r"^[^/\s]+/[^/\s]+$")


class FetchError(RuntimeError):
    """A GitHub request failed or returned an unusable payload."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class MissingTokenError(FetchError):
    """No token was supplied and no client was injected."""


@dataclass(frozen=True)
class Response:
    """The parts of an HTTP response this pipeline reads."""

    status: int
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class ReadClient(Protocol):
    """The read surface ``fetch_context`` needs; ``GitHubClient`` and fakes implement it."""

    def get(
        self,
        path: str,
        params: dict[str, object] | None = None,
        accept: str | None = None,
    ) -> Response: ...


class GitHubClient:
    """A small stdlib REST client with injectable transport for tests."""

    def __init__(
        self,
        token: str | None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.token = token
        self._opener: Callable[..., Any] = opener or urllib.request.urlopen

    def get(
        self,
        path: str,
        params: dict[str, object] | None = None,
        accept: str | None = None,
    ) -> Response:
        return self._request("GET", path, params=params, accept=accept)

    def post(self, path: str, payload: dict[str, object] | None = None) -> Response:
        return self._request("POST", path, payload=payload)

    def patch(self, path: str, payload: dict[str, object] | None = None) -> Response:
        return self._request("PATCH", path, payload=payload)

    def delete(self, path: str, payload: dict[str, object] | None = None) -> Response:
        return self._request("DELETE", path, payload=payload)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, object] | None = None,
        accept: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> Response:
        url = BASE_URL + path
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        headers = {
            "Accept": accept or JSON_ACCEPT,
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        # BASE_URL is fixed; repo and number are validated before this call.
        request = urllib.request.Request(  # noqa: S310
            url, data=data, headers=headers, method=method
        )
        try:
            with self._opener(request, timeout=TIMEOUT_SECONDS) as response:
                return Response(
                    status=response.status,
                    body=response.read(),
                    headers=dict(response.headers),
                )
        except urllib.error.HTTPError as error:
            raise FetchError(
                f"GitHub API returned {error.code} for {path}", status=error.code
            ) from error
        except urllib.error.URLError as error:
            raise FetchError(f"GitHub API request failed for {path}: {error.reason}") from error
