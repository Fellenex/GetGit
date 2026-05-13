"""Unified stand-in for `GithubClient` used across provider tests."""


class FakeGithubClient:
    """Yields canned items per URL and records every call.

    `pages` maps a URL to the items that endpoint should yield. URLs not
    present in `pages` fall back to `default_items` — useful for tests
    where only one endpoint is exercised and the URL doesn't matter.
    `calls` is the list of `(url, params)` recorded across every
    `paginate` invocation.
    """

    def __init__(
        self,
        pages: dict[str, list[dict]] | None = None,
        default_items: list[dict] | None = None,
    ):
        """Capture the per-URL pages and the fallback `default_items`."""
        self._pages = pages or {}
        self._default = default_items or []
        self.calls: list[tuple] = []

    @property
    def last_call(self) -> tuple | None:
        """The most recent `(url, params)` pair, or `None` if no calls yet."""
        return self.calls[-1] if self.calls else None

    def paginate(self, url: str, params: dict | None = None):
        """Record the call and yield items registered for `url` (or the default)."""
        self.calls.append((url, params))
        return iter(self._pages.get(url, self._default))
