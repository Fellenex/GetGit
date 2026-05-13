"""Stand-in for the `httpx.Client` GithubClient wraps internally."""


class FakeHttp:
    """Returns queued `FakeResponse`s in order; records every call.

    Use `calls` to assert on the URLs and params GithubClient produced.
    """

    def __init__(self, responses):
        """Take a list of `FakeResponse` instances to return in sequence."""
        self._responses = list(responses)
        self.calls: list[tuple] = []

    def get(self, url: str, params: dict | None = None):
        """Pop and return the next queued response; record the call."""
        self.calls.append((url, params))
        return self._responses.pop(0)
