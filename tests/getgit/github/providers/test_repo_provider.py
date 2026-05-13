"""Tests for RepoProvider."""

from _support.github import FakeGithubClient

from getgit.github import RepoProvider


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
