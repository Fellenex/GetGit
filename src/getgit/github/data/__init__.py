"""GitHub-domain data classes — DTOs returned by providers and aggregated by services."""

from .authorship_report import AuthorshipReport
from .commit import Commit
from .pull_request import PullRequest
from .pull_request_fetch_result import PullRequestFetchResult
from .review import Review

__all__ = [
    "AuthorshipReport",
    "Commit",
    "PullRequest",
    "PullRequestFetchResult",
    "Review",
]
