"""Tests for RepositoryAccessError — the message it builds from a repo name."""

from getgit.github import RepositoryAccessError


def test_carries_the_offending_repo():
    """The `repo` attribute exposes the repo the caller can render/point at."""
    err = RepositoryAccessError("octocat/hello-world")
    assert err.repo == "octocat/hello-world"


def test_message_names_the_repo_and_points_at_the_sso_fix():
    """The message should name the repo and mention authorizing the PAT."""
    text = str(RepositoryAccessError("octocat/hello-world"))
    assert "octocat/hello-world" in text
    assert "SSO" in text


def test_is_a_runtime_error():
    """Subclasses RuntimeError so broad `except RuntimeError` handlers still catch it."""
    assert isinstance(RepositoryAccessError("o/r"), RuntimeError)
