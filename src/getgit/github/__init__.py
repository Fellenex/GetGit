"""GitHub domain — clients, providers, and result data classes."""

from .clients import GithubClient
from .data import PullRequestFetchResult
from .providers import CommitProvider, PullRequestProvider, RepoProvider

__all__ = [
    "GithubClient",
    "CommitProvider",
    "PullRequestProvider",
    "RepoProvider",
    "PullRequestFetchResult",
]
