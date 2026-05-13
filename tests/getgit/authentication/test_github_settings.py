"""Tests for GithubSettings."""

from getgit.authentication import GithubSettings


def test_defaults_for_base_url_and_timeout():
    """Only `auth_token` is required; the others have sensible defaults."""
    s = GithubSettings(auth_token="t")

    assert s.auth_token == "t"
    assert s.base_url == "https://api.github.com"
    assert s.timeout == 30.0


def test_overrides_take_effect():
    """All three fields can be set explicitly."""
    s = GithubSettings(
        auth_token="t", base_url="https://github.example.com", timeout=10.0
    )

    assert s.base_url == "https://github.example.com"
    assert s.timeout == 10.0
