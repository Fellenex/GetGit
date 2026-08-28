"""Repository discovery — the only place self vs stranger diverges."""

from ..clients import GithubClient, RateLimitExceededError


class RepoProvider:
    """Lists repositories a target user has access to.

    The `is_self` branch is the entire client-side scope check: the
    GitHub API enforces visibility server-side based on the PAT.
    """

    def __init__(self, client: GithubClient):
        """Bind to a `GithubClient` for all subsequent calls."""
        self._client = client

    def list_repos(self, username: str, is_self: bool) -> list[dict]:
        """List repos `username` has access to.

        `is_self=True` uses `/user/repos` with
        `affiliation=owner,collaborator,organization_member` so the
        result covers not just repos the user owns but also ones they
        collaborate on and org-owned repos they're a member of (e.g. a
        company org's repos) — returning public + private the PAT can
        see. `is_self=False` uses `/users/{username}/repos` (public
        repos the user owns only). On rate limit, attaches the partial
        list already collected to the raised `RateLimitExceededError`.
        """
        repos: list[dict] = []
        try:
            if is_self:
                pages = self._client.paginate(
                    "/user/repos",
                    {
                        "affiliation": "owner,collaborator,organization_member",
                        "visibility": "all",
                    },
                )
            else:
                pages = self._client.paginate(f"/users/{username}/repos")
            for repo in pages:
                repos.append(repo)
            return repos
        except RateLimitExceededError as e:
            e.partial = repos
            raise
