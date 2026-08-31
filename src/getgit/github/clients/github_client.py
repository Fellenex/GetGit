"""Authenticated GitHub REST client with pagination support."""

from typing import Iterator

import httpx

from .github_settings import GithubSettings
from .rate_limit_exceeded_error import RateLimitExceededError


class GithubClient:
    """GitHub REST client with auth, pagination, and viewer-identity helpers.

    Built from a `GithubSettings` so the constructor encapsulates the
    auth-header wiring. Acts as a context manager — opens its
    underlying `httpx.Client` on `__enter__` and closes it on
    `__exit__`. Once a *rate-limit* 403 is observed (identified by its
    `Retry-After` / `X-RateLimit-Remaining` headers), the client locks
    itself: every subsequent call raises `RateLimitExceededError`
    without hitting the network. A non-rate-limit 403 (e.g. a per-repo
    access denial) is not a lock — it surfaces as a normal
    `httpx.HTTPStatusError` for the caller to handle.
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
        """Lock the client and raise if `response` is a *rate-limit* 403.

        GitHub reuses 403 for several conditions. Only a genuine rate
        limit should lock the client and abort the whole scrape; a
        per-resource access 403 (e.g. an org repo behind SAML SSO the
        PAT isn't authorized for) must stay a local failure the caller
        can skip. We classify by reliable headers, never the response
        body (which varies across endpoint families):

        - a `Retry-After` header → secondary (abuse) rate limit.
        - `X-RateLimit-Remaining: 0` → primary rate limit.

        A 403 matching neither is left alone: the caller's
        `raise_for_status()` surfaces it as a normal
        `httpx.HTTPStatusError` for per-resource handling.
        """
        if response.status_code == 403 and self._is_rate_limit_403(response):
            self._rate_limited = True
            raise RateLimitExceededError(self._extract_message(response))

    @staticmethod
    def _is_rate_limit_403(response: httpx.Response) -> bool:
        """True when a 403 carries GitHub's rate-limit headers (primary or secondary)."""
        if response.headers.get("Retry-After") is not None:
            return True
        return response.headers.get("X-RateLimit-Remaining") == "0"

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
