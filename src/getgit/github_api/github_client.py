"""Authenticated GitHub REST client with pagination support."""

from typing import Iterator

import httpx

from ..authentication import GithubSettings


class GithubClient:
    """GitHub REST client with auth, pagination, and viewer-identity helpers.

    Built from a `GithubSettings` so the constructor encapsulates the
    auth-header wiring. Acts as a context manager — opens its
    underlying `httpx.Client` on `__enter__` and closes it on
    `__exit__`.
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

    def __enter__(self) -> "GithubClient":
        """Enter the underlying HTTP client's context."""
        self._http.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the underlying HTTP client."""
        self._http.__exit__(*exc)

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        """Perform a single GET — useful when you don't need pagination."""
        return self._http.get(url, params=params)

    def paginate(self, url: str, params: dict | None = None) -> Iterator[dict]:
        """Yield every item across all pages of a GitHub REST endpoint.

        Follows the `Link: ...; rel="next"` header — works for both list
        endpoints (which return arrays) and search endpoints (which wrap
        results under `"items"`). Query params are sent on the first
        request only; the `next` URL already contains them.
        """
        merged_params = dict(params or {})
        merged_params.setdefault("per_page", 100)
        next_url: str | None = url
        next_params: dict | None = merged_params
        while next_url:
            resp = self._http.get(next_url, params=next_params)
            resp.raise_for_status()
            data = resp.json()
            items = data["items"] if isinstance(data, dict) and "items" in data else data
            for item in items:
                yield item
            next_url = resp.links.get("next", {}).get("url")
            next_params = None

    def viewer_login(self) -> str:
        """Return the login of the user whose token is being used."""
        resp = self._http.get("/user")
        resp.raise_for_status()
        return resp.json()["login"]
