"""Tests for the PersonalTokenAuth strategy."""

import pytest

from getgit.authentication import PersonalTokenAuth


def test_explicit_token_wins_over_env(monkeypatch):
    """A token passed to the constructor should override `GITHUB_TOKEN`."""
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")

    auth = PersonalTokenAuth(token="explicit")

    assert auth.token == "explicit"


def test_falls_back_to_env_var(monkeypatch):
    """With no explicit token, the env var should be picked up."""
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")

    assert PersonalTokenAuth().token == "env-token"


def test_raises_when_no_token_available(monkeypatch):
    """Missing token must fail fast at construction, not mid-scrape."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="GITHUB_TOKEN not set"):
        PersonalTokenAuth()
