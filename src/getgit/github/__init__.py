"""GitHub domain — clients, providers, services, and result data classes."""

from .clients import (
    GithubClient,
    GithubSettings,
    RateLimitExceededError,
    RepositoryAccessError,
)
from .data import (
    AuthorshipReport,
    Comment,
    Commit,
    CommitPayload,
    IssueSearchResult,
    PullRequest,
    PullRequestDetail,
    PullRequestFetchResult,
    PullRequestFile,
    PullRequestReview,
    RepoSummary,
    Review,
)
from .providers import GithubProvider
from .services import GithubService

__all__ = [
    "AuthorshipReport",
    "Comment",
    "Commit",
    "CommitPayload",
    "GithubClient",
    "GithubProvider",
    "GithubService",
    "GithubSettings",
    "IssueSearchResult",
    "PullRequest",
    "PullRequestDetail",
    "PullRequestFetchResult",
    "PullRequestFile",
    "PullRequestReview",
    "RateLimitExceededError",
    "RepoSummary",
    "RepositoryAccessError",
    "Review",
]
