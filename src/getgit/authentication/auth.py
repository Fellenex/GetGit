"""The `Auth` protocol — abstract interface every auth strategy implements."""

from typing import Protocol

from ..github_api import GithubClient


class Auth(Protocol):
    """Common interface for any auth strategy.

    An implementation knows how to produce a `GithubClient` that is
    pre-authenticated against `https://api.github.com`. Fetchers depend
    on this protocol, never on a concrete strategy or the token itself,
    so swapping PAT for OAuth in phase 2 won't touch fetcher code.
    """

    def client(self) -> GithubClient:
        """Return a `GithubClient` ready to make authenticated calls."""
        ...
