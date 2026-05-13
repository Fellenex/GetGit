"""Low-level helpers for the GitHub REST API."""

from typing import Iterator

import httpx


def paginate(client: httpx.Client, url: str, params: dict | None = None) -> Iterator[dict]:
    """Yield every item across all pages of a GitHub REST endpoint.

    Follows the `Link: ...; rel="next"` header — works for both list
    endpoints (which return arrays) and search endpoints (which wrap
    results under `"items"`). Query params are sent on the first request
    only; the `next` URL already contains them.
    """
    params = dict(params or {})
    params.setdefault("per_page", 100)
    next_url: str | None = url
    next_params: dict | None = params
    while next_url:
        resp = client.get(next_url, params=next_params)
        resp.raise_for_status()
        data = resp.json()
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        for item in items:
            yield item
        next_url = resp.links.get("next", {}).get("url")
        next_params = None
