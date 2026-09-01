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
    GithubComment,
    GithubCommit,
    GithubIssue,
    GithubPullRequest,
    GithubPullRequestChangedFile,
    GithubRepo,
    GithubReview,
    PullRequest,
    PullRequestFetchResult,
    Review,
)
from .providers import GithubMapper, GithubProvider
from .services import GithubService

__all__ = [
    "AuthorshipReport",
    "Commit",
    "GithubClient",
    "GithubComment",
    "GithubCommit",
    "GithubIssue",
    "GithubMapper",
    "GithubProvider",
    "GithubPullRequest",
    "GithubPullRequestChangedFile",
    "GithubRepo",
    "GithubReview",
    "GithubService",
    "GithubSettings",
    "PullRequest",
    "PullRequestFetchResult",
    "RateLimitExceededError",
    "RepositoryAccessError",
    "Review",
]
