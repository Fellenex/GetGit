"""GitHub domain — clients, providers, services, and result data classes."""

from .clients import (
    GithubClient,
    GithubSettings,
    RateLimitExceededError,
    RepositoryAccessError,
)
from .data import (
    AuthorshipReport,
    Commit,
    PullRequest,
    PullRequestFetchResult,
    Review,
)
from .providers import CommitProvider, PullRequestProvider, RepoProvider
from .services import GithubService

__all__ = [
    "AuthorshipReport",
    "Commit",
    "CommitProvider",
    "GithubClient",
    "GithubService",
    "GithubSettings",
    "PullRequest",
    "PullRequestFetchResult",
    "PullRequestProvider",
    "RateLimitExceededError",
    "RepoProvider",
    "RepositoryAccessError",
    "Review",
]
