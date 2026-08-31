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
from .providers import CommitProvider, PullRequestProvider, RepoProvider
from .services import GithubService

__all__ = [
    "AuthorshipReport",
    "Comment",
    "Commit",
    "CommitPayload",
    "CommitProvider",
    "GithubClient",
    "GithubService",
    "GithubSettings",
    "IssueSearchResult",
    "PullRequest",
    "PullRequestDetail",
    "PullRequestFetchResult",
    "PullRequestFile",
    "PullRequestProvider",
    "PullRequestReview",
    "RateLimitExceededError",
    "RepoProvider",
    "RepoSummary",
    "RepositoryAccessError",
    "Review",
]
