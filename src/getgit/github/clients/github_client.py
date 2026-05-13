"""Authenticated GitHub REST client with pagination support."""

from typing import Iterator

import httpx

from ...authentication import GithubSettings
from .rate_limit_exceeded_error import RateLimitExceededError


class GithubClient:
    """GitHub REST client with auth, pagination, and viewer-identity helpers.

    Built from a `GithubSettings` so the constructor encapsulates the
    auth-header wiring. Acts as a context manager — opens its
    underlying `httpx.Client` on `__enter__` and closes it on
    `__exit__`. Once a 403 is observed, the client locks itself: every
    subsequent call raises `RateLimitExceededError` without hitting the
    network.
    """

    def __init__(self, settings: GithubSettings):
        """Build the underlying `httpx.Client` from `settings`."""
        self._http = httpx.Client(
            base_url=settings.base_url,
            headers={
                "Authorization": f"Bearer {settings.auth_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "GetGit/0.1",
            },
            timeout=settings.timeout,
        )
        self._rate_limited = False

    def __enter__(self) -> "GithubClient":
        """Enter the underlying HTTP client's context."""
        self._http.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the underlying HTTP client."""
        self._http.__exit__(*exc)

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        """Perform a single GET. Raises `RateLimitExceededError` on 403."""
        self._guard_rate_limit()
        response = self._http.get(url, params=params)
        self._check_rate_limit(response)
        return response

    def paginate(self, url: str, params: dict | None = None) -> Iterator[dict]:
        """Yield every item across all pages of a GitHub REST endpoint.

        Follows the `Link: ...; rel="next"` header — works for both list
        endpoints (which return arrays) and search endpoints (which wrap
        results under `"items"`). Query params are sent on the first
        request only; the `next` URL already contains them. Aborts (and
        locks the client) on the first 403.
        """
        merged_params = dict(params or {})
        merged_params.setdefault("per_page", 100)
        next_url: str | None = url
        next_params: dict | None = merged_params
        while next_url:
            self._guard_rate_limit()
            resp = self._http.get(next_url, params=next_params)
            self._check_rate_limit(resp)
            resp.raise_for_status()
            data = resp.json()
            items = data["items"] if isinstance(data, dict) and "items" in data else data
            for item in items:
                yield item
            next_url = resp.links.get("next", {}).get("url")
            next_params = None

    def viewer_login(self) -> str:
        """Return the login of the user whose token is being used."""
        resp = self.get("/user")
        resp.raise_for_status()
        return resp.json()["login"]

    def _guard_rate_limit(self) -> None:
        """Refuse to make a network call once a 403 has been seen."""
        if self._rate_limited:
            raise RateLimitExceededError(
                "Refusing further requests: a previous call returned 403."
            )

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """Lock the client and raise if `response` is a 403."""
        if response.status_code == 403:
            self._rate_limited = True
            raise RateLimitExceededError(self._extract_message(response))

    @staticmethod
    def _extract_message(response: httpx.Response) -> str:
        """Build a human-readable message from a 403 response body."""
        try:
            body = response.json()
            msg = body.get("message", "").strip()
            if msg:
                return f"GitHub returned 403: {msg}"
        except (ValueError, AttributeError):
            pass
        return "GitHub returned 403"
