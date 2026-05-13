"""Stand-in for `GithubClient` that raises an HTTPStatusError on every paginate call."""

import httpx


class ErroringGithubClient:
    """Always raises `httpx.HTTPStatusError` with the configured status code.

    Used to exercise CommitProvider's 404/409 skip path without spinning
    up real HTTP machinery.
    """

    def __init__(self, status_code: int):
        """Configure which HTTP status the next paginate call should raise."""
        self._code = status_code

    def paginate(self, url: str, params: dict | None = None):
        """Always raise an `httpx.HTTPStatusError` with the configured status."""
        resp = httpx.Response(self._code, request=httpx.Request("GET", url))
        raise httpx.HTTPStatusError("fake", request=resp.request, response=resp)
