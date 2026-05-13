"""Just enough of `httpx.Response` to satisfy GithubClient under test."""


class FakeResponse:
    """Minimal stand-in for `httpx.Response` — payload + links + status."""

    def __init__(self, payload, links: dict | None = None, status: int = 200):
        """Capture the JSON payload, optional Link map, and HTTP status."""
        self._payload = payload
        self.links = links or {}
        self.status_code = status

    def json(self):
        """Return the payload as-is — already pre-parsed by the fake."""
        return self._payload

    def raise_for_status(self) -> None:
        """Mirror httpx: raise on 4xx/5xx, otherwise no-op."""
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
