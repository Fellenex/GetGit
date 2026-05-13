from typing import Iterator

import httpx


def paginate(client: httpx.Client, url: str, params: dict | None = None) -> Iterator[dict]:
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
