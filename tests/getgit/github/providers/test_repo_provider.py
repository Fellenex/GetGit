"""Tests for RepoProvider."""

from unittest.mock import Mock

import pytest

from _support.github import FakeGithubClient

from getgit.github import GithubClient, RateLimitExceededError, RepoProvider


def test_self_path_uses_user_repos_with_owner_affiliation():
    """is_self=True hits /user/repos with affiliation+visibility filters."""
    client = FakeGithubClient(default_items=[{"full_name": "me/r"}])

    out = RepoProvider(client).list_repos("me", is_self=True)

    assert out == [{"full_name": "me/r"}]
    assert client.last_call == (
        "/user/repos",
        {"affiliation": "owner", "visibility": "all"},
    )


def test_stranger_path_uses_users_username_repos():
    """is_self=False hits /users/{u}/repos and skips the visibility/affiliation filters."""
    client = FakeGithubClient(default_items=[{"full_name": "alice/r"}])

    RepoProvider(client).list_repos("alice", is_self=False)

    assert client.last_call == ("/users/alice/repos", None)


def test_returns_list_not_iterator():
    """The result should be materialized into a list (callers iterate multiple times)."""
    client = FakeGithubClient(default_items=[{"full_name": "x/y"}, {"full_name": "x/z"}])

    out = RepoProvider(client).list_repos("x", is_self=False)

    assert isinstance(out, list)
    assert len(out) == 2


def test_rate_limit_attaches_partial_repos_to_exception():
    """If paginate yields some repos then 403s, the partial list should ride on the exception."""
    def yielding_then_403(*_args, **_kwargs):
        yield {"full_name": "x/a"}
        yield {"full_name": "x/b"}
        raise RateLimitExceededError("too many")

    client = Mock(spec=GithubClient)
    client.paginate.side_effect = yielding_then_403

    with pytest.raises(RateLimitExceededError) as excinfo:
        RepoProvider(client).list_repos("x", is_self=False)

    assert excinfo.value.partial == [{"full_name": "x/a"}, {"full_name": "x/b"}]
