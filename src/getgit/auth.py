"""Authentication strategies for the GitHub API.

Each strategy produces a configured `GithubClient`. Fetchers depend on
the client, never on the token itself, so swapping PAT for OAuth in
phase 2 won't touch fetcher code.
"""

import os
from typing import Protocol

import httpx

from .github_client import GithubClient


class Auth(Protocol):
    """Common interface for any auth strategy.

    An implementation knows how to produce a `GithubClient` that is
    pre-authenticated against `https://api.github.com`.
    """

    def client(self) -> GithubClient:
        """Return a `GithubClient` ready to make authenticated calls."""
        ...


class PersonalTokenAuth:
    """Authenticates via a GitHub Personal Access Token (PAT).

    The token is read from the `GITHUB_TOKEN` environment variable unless
    one is passed explicitly. This is the phase-1 default.
    """

    def __init__(self, token: str | None = None):
        """Capture the PAT, falling back to the `GITHUB_TOKEN` env var.

        Raises `RuntimeError` if no token is available — failing fast at
        construction time beats discovering it mid-scrape.
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise RuntimeError(
                "GITHUB_TOKEN not set. Export your PAT or pass token= explicitly."
            )

    def client(self) -> GithubClient:
        """Build a `GithubClient` with auth headers and the GitHub base URL."""
        http = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "GetGit/0.1",
            },
            timeout=30.0,
        )
        return GithubClient(http)
