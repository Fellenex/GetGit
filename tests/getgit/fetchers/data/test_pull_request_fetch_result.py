"""Tests for PullRequestFetchResult."""

from getgit.fetchers import PullRequestFetchResult


def test_defaults_are_empty_collections():
    """Each field defaults to its own empty container."""
    out = PullRequestFetchResult()

    assert out.authored == []
    assert out.participated == []
    assert out.reviews == []
    assert out.commit_pr_index == {}


def test_default_factories_are_independent_per_instance():
    """Two instances must not share the same default list (mutable-default trap)."""
    a = PullRequestFetchResult()
    b = PullRequestFetchResult()

    a.authored.append("x")

    assert b.authored == []
