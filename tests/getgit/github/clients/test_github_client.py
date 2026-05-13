"""Tests for GithubClient — paginate logic and viewer_login.

Uses real `httpx.Response` instances (so `.json()`, `.links`, and
`.raise_for_status()` are the real implementations) and a `Mock` for
the underlying `httpx.Client` to script the response sequence.
"""

from unittest.mock import Mock

import httpx

from getgit.authentication import GithubSettings
from getgit.github import GithubClient


def _client_with(responses: list[httpx.Response]) -> GithubClient:
    """Build a GithubClient and swap in a Mock that returns `responses` in order."""
    client = GithubClient(GithubSettings(auth_token="t"))
    mock_http = Mock()
    mock_http.get.side_effect = responses
    client._http = mock_http
    return client


def _resp(payload, links_header: str | None = None, status: int = 200) -> httpx.Response:
    """Build a real `httpx.Response`. `links_header` populates the `Link` header httpx parses for us."""
    headers = {"Link": links_header} if links_header else {}
    # `request` must be set so raise_for_status() works; URL is irrelevant under the mock transport.
    return httpx.Response(
        status, json=payload, headers=headers, request=httpx.Request("GET", "/")
    )


def test_paginate_yields_a_single_page_array():
    """When there's no `next` link, we get every item from the one response."""
    c = _client_with([_resp([{"a": 1}, {"a": 2}])])

    assert list(c.paginate("/x")) == [{"a": 1}, {"a": 2}]


def test_paginate_follows_next_link_across_pages():
    """The Link header's `next` URL is followed until exhausted."""
    page1 = _resp([{"n": 1}], links_header='</x?page=2>; rel="next"')
    page2 = _resp([{"n": 2}, {"n": 3}])
    c = _client_with([page1, page2])

    assert list(c.paginate("/x")) == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_paginate_handles_search_envelope():
    """`/search/...` endpoints wrap results under `items` — we should unwrap."""
    c = _client_with([_resp({"total_count": 2, "items": [{"a": 1}, {"a": 2}]})])

    assert list(c.paginate("/search/issues", {"q": "type:pr"})) == [{"a": 1}, {"a": 2}]


def test_paginate_sets_per_page_default_on_first_call_only():
    """`per_page=100` is added to first request; following pages reuse the next URL as-is."""
    page1 = _resp([{"n": 1}], links_header='</x?page=2>; rel="next"')
    page2 = _resp([{"n": 2}])
    c = _client_with([page1, page2])

    list(c.paginate("/x"))

    assert c._http.get.call_args_list[0].args == ("/x",)
    assert c._http.get.call_args_list[0].kwargs == {"params": {"per_page": 100}}
    assert c._http.get.call_args_list[1].args == ("/x?page=2",)
    assert c._http.get.call_args_list[1].kwargs == {"params": None}


def test_viewer_login_returns_login_field():
    """viewer_login() should call /user and return the `login` field."""
    c = _client_with([_resp({"login": "alice", "id": 42})])

    assert c.viewer_login() == "alice"
    c._http.get.assert_called_with("/user")
