"""Repository discovery — the only place self vs stranger diverges."""

from ..clients import GithubClient, RateLimitExceededError


class RepoProvider:
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
        (public only). On rate limit, attaches the partial list already
        collected to the raised `RateLimitExceededError`.
        """
        repos: list[dict] = []
        try:
            if is_self:
                pages = self._client.paginate(
                    "/user/repos", {"affiliation": "owner", "visibility": "all"}
                )
            else:
                pages = self._client.paginate(f"/users/{username}/repos")
            for repo in pages:
                repos.append(repo)
            return repos
        except RateLimitExceededError as e:
            e.partial = repos
            raise
