"""Tests for the rate-limit handling in GithubClient.

Lives in the same domain as `GithubClient` itself but in a separate
file so each test name reads as `test_<file>::<behavior>` cleanly.
"""

from unittest.mock import Mock

import httpx
import pytest

from getgit.authentication import GithubSettings
from getgit.github import GithubClient, RateLimitExceededError


def _client_with(responses: list[httpx.Response]) -> GithubClient:
    """Build a GithubClient and swap in a Mock that returns `responses` in order."""
    client = GithubClient(GithubSettings(auth_token="t"))
    client._http = Mock()
    client._http.get.side_effect = responses
    return client


def _resp(payload, status: int = 200) -> httpx.Response:
    """Build a real `httpx.Response` (with a request so raise_for_status works)."""
    return httpx.Response(
        status, json=payload, request=httpx.Request("GET", "/")
    )


def test_paginate_raises_on_first_403():
    """A 403 mid-paginate should raise RateLimitExceededError immediately."""
    c = _client_with([_resp({"message": "API rate limit exceeded"}, status=403)])

    with pytest.raises(RateLimitExceededError, match="rate limit"):
        list(c.paginate("/x"))


def test_get_raises_on_403():
    """A 403 from get() should raise RateLimitExceededError, not return the response."""
    c = _client_with([_resp({"message": "forbidden"}, status=403)])

    with pytest.raises(RateLimitExceededError):
        c.get("/x")


def test_subsequent_calls_short_circuit_without_hitting_network():
    """Once a 403 has been observed, further calls must not touch _http."""
    c = _client_with([_resp({"message": "rate-limited"}, status=403)])

    with pytest.raises(RateLimitExceededError):
        c.get("/first")

    # The mock has no more queued responses; if we hit it we'd get StopIteration,
    # so any extra _http call after the lock would surface as something other
    # than RateLimitExceededError.
    with pytest.raises(RateLimitExceededError):
        c.get("/second")
    with pytest.raises(RateLimitExceededError):
        list(c.paginate("/third"))


def test_error_message_includes_github_response_message():
    """The body's `message` field should be surfaced in the exception text."""
    c = _client_with([_resp({"message": "API rate limit exceeded for foo"}, status=403)])

    with pytest.raises(RateLimitExceededError, match="API rate limit exceeded for foo"):
        c.get("/x")


def test_non_403_responses_do_not_lock_the_client():
    """A 200 followed by a successful call should both pass."""
    c = _client_with([_resp({"a": 1}), _resp({"b": 2})])

    assert c.get("/first").status_code == 200
    assert c.get("/second").status_code == 200
