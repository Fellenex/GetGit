"""Tests for RepoProvider."""

from getgit.github import RepoProvider


class _RecordingClient:
    """Records the (url, params) of the last paginate call."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.last_call: tuple | None = None

    def paginate(self, url: str, params: dict | None = None):
        self.last_call = (url, params)
        return iter(self._items)


def test_self_path_uses_user_repos_with_owner_affiliation():
    """is_self=True hits /user/repos with affiliation+visibility filters."""
    client = _RecordingClient([{"full_name": "me/r"}])

    out = RepoProvider(client).list_repos("me", is_self=True)

    assert out == [{"full_name": "me/r"}]
    assert client.last_call == (
        "/user/repos",
        {"affiliation": "owner", "visibility": "all"},
    )


def test_stranger_path_uses_users_username_repos():
    """is_self=False hits /users/{u}/repos and skips the visibility/affiliation filters."""
    client = _RecordingClient([{"full_name": "alice/r"}])

    RepoProvider(client).list_repos("alice", is_self=False)

    assert client.last_call == ("/users/alice/repos", None)


def test_returns_list_not_iterator():
    """The result should be materialized into a list (callers iterate multiple times)."""
    client = _RecordingClient([{"full_name": "x/y"}, {"full_name": "x/z"}])

    out = RepoProvider(client).list_repos("x", is_self=False)

    assert isinstance(out, list)
    assert len(out) == 2
