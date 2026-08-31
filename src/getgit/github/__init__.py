"""GitHub domain — clients, providers, services, and result data classes."""

from .clients import (
    GithubClient,
    GithubSettings,
    RateLimitExceededError,
    RepositoryAccessError,
)
from .data import (
    AuthorshipReport,
    CommentsResponse,
    Commit,
    CommitsResponse,
    IssueSearchResponse,
    PullRequest,
    PullRequestFetchResult,
    PullRequestFilesResponse,
    PullRequestResponse,
    PullRequestReviewsResponse,
    ReposResponse,
    Review,
)
from .providers import CommitProvider, PullRequestProvider, RepoProvider
from .services import GithubService

__all__ = [
    "AuthorshipReport",
    "CommentsResponse",
    "Commit",
    "CommitsResponse",
    "CommitProvider",
    "GithubClient",
    "GithubService",
    "GithubSettings",
    "IssueSearchResponse",
    "PullRequest",
    "PullRequestFetchResult",
    "PullRequestFilesResponse",
    "PullRequestProvider",
    "PullRequestResponse",
    "PullRequestReviewsResponse",
    "RateLimitExceededError",
    "RepoProvider",
    "ReposResponse",
    "RepositoryAccessError",
    "Review",
]
