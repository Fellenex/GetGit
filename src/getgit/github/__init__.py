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
    GithubScrapeResult,
    IssueSearchResult,
    PullRequest,
    PullRequestDetail,
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
    "GithubScrapeResult",
    "GithubService",
    "GithubSettings",
    "IssueSearchResult",
    "PullRequest",
    "PullRequestDetail",
    "PullRequestFile",
    "PullRequestReview",
    "RateLimitExceededError",
    "RepoSummary",
    "RepositoryAccessError",
    "Review",
]
