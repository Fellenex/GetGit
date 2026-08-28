"""Exception raised when a scoped GitHub search names a repo the token can't access."""


class RepositoryAccessError(RuntimeError):
    """Raised when a `repo:`-scoped `/search/issues` call returns 422.

    GitHub's Search API answers a `repo:OWNER/NAME` qualifier with 422 —
    not empty results — when the token cannot see the repository or it
    does not exist. GitHub deliberately conflates "missing" and
    "forbidden" (a direct `GET /repos/{owner}/{name}` 404s rather than
    403s) so a token can't probe for the existence of private resources.
    In practice this almost always means the PAT is not authorized for
    the org: a classic PAT needs SSO authorization; a fine-grained PAT
    needs the org to grant it access.

    Unlike `RateLimitExceededError` (a global 403 that locks the client),
    a 422 is specific to the one scoped query, so this is raised at the
    provider boundary rather than inside `GithubClient`. Carries the
    offending `repo` so callers can render a message that names it.
    """

    def __init__(self, repo: str):
        """Build an actionable message naming `repo` and the authorization fix."""
        self.repo = repo
        super().__init__(
            f"Repository '{repo}' could not be searched. It may not exist, or "
            "your token cannot see it. If it is a private org repo, authorize "
            "your PAT for the organization (classic PAT: Configure SSO; "
            "fine-grained PAT: the org must grant the token access)."
        )
