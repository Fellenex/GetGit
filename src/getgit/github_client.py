"""Authenticated GitHub REST client with pagination support."""

from typing import Iterator

import httpx


class GithubClient:
    """Thin wrapper over `httpx.Client` adding GitHub-aware helpers.

    Owns the lifecycle of an HTTP client (works as a context manager)
    and exposes the small set of operations every fetcher needs:
    `get`, `paginate`, and `viewer_login`. Auth headers and base URL
    are baked into the underlying `httpx.Client` by the `Auth` layer
    before we receive it.
    """

    def __init__(self, http: httpx.Client):
        """Wrap a pre-authenticated `httpx.Client`."""
        self._http = http

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
        """Return the login of the user whose PAT is being used."""
        resp = self._http.get("/user")
        resp.raise_for_status()
        return resp.json()["login"]
