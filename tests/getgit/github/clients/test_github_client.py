"""Tests for GithubClient — paginate logic and viewer_login."""

from getgit.authentication import GithubSettings
from getgit.github import GithubClient


class _FakeResponse:
    """Just enough of httpx.Response to satisfy GithubClient's calls."""

    def __init__(self, payload, links=None, status=200):
        self._payload = payload
        self.links = links or {}
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeHttp:
    """Returns the queued responses in order; records calls."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[tuple] = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return self._responses.pop(0)


def _client_with(responses):
    """Build a GithubClient and swap in a fake http transport."""
    c = GithubClient(GithubSettings(auth_token="t"))
    c._http = _FakeHttp(responses)
    return c


def test_paginate_yields_a_single_page_array():
    """When there's no `next` link, we get every item from the one response."""
    c = _client_with([_FakeResponse([{"a": 1}, {"a": 2}])])

    out = list(c.paginate("/x"))

    assert out == [{"a": 1}, {"a": 2}]


def test_paginate_follows_next_link_across_pages():
    """The Link header's `next` URL is followed until exhausted."""
    page1 = _FakeResponse([{"n": 1}], links={"next": {"url": "/x?page=2"}})
    page2 = _FakeResponse([{"n": 2}, {"n": 3}])
    c = _client_with([page1, page2])

    out = list(c.paginate("/x"))

    assert out == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_paginate_handles_search_envelope():
    """`/search/...` endpoints wrap results under `items` — we should unwrap."""
    c = _client_with([_FakeResponse({"total_count": 2, "items": [{"a": 1}, {"a": 2}]})])

    out = list(c.paginate("/search/issues", {"q": "type:pr"}))

    assert out == [{"a": 1}, {"a": 2}]


def test_paginate_sets_per_page_default_on_first_call_only():
    """`per_page=100` is added to first request; following pages reuse the next URL as-is."""
    page1 = _FakeResponse([{"n": 1}], links={"next": {"url": "/x?page=2"}})
    page2 = _FakeResponse([{"n": 2}])
    c = _client_with([page1, page2])

    list(c.paginate("/x"))

    assert c._http.calls[0] == ("/x", {"per_page": 100})
    assert c._http.calls[1] == ("/x?page=2", None)


def test_viewer_login_returns_login_field():
    """viewer_login() should call /user and return the `login` field."""
    c = _client_with([_FakeResponse({"login": "alice", "id": 42})])

    assert c.viewer_login() == "alice"
    assert c._http.calls[0] == ("/user", None)
