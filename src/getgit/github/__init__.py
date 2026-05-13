"""GitHub domain — clients, providers, services, and result data classes."""

from .clients import GithubClient
from .data import PullRequestFetchResult
from .providers import CommitProvider, PullRequestProvider, RepoProvider
from .services import GithubService

__all__ = [
    "GithubClient",
    "GithubService",
    "CommitProvider",
    "PullRequestProvider",
    "RepoProvider",
    "PullRequestFetchResult",
]
