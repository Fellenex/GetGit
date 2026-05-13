"""Repository discovery — the only place self vs stranger diverges."""

from ..github_client import GithubClient


class RepoFetcher:
    """Lists repositories owned by a target user.

    The `is_self` branch is the entire client-side scope check: the
    GitHub API enforces visibility server-side based on the PAT.
    """

    def __init__(self, client: GithubClient):
        """Bind to a `GithubClient` for all subsequent calls."""
        self._client = client

    def list_repos(self, username: str, is_self: bool) -> list[dict]:
        """List repos owned by `username`.

        `is_self=True` uses `/user/repos` (returns public + private the
        PAT can see). `is_self=False` uses `/users/{username}/repos`
        (public only).
        """
        if is_self:
            return list(
                self._client.paginate(
                    "/user/repos", {"affiliation": "owner", "visibility": "all"}
                )
            )
        return list(self._client.paginate(f"/users/{username}/repos"))
