"""GitHub-domain data classes.

Two families live here: the **wire-shape response objects** that
`GithubClient` builds from raw GitHub JSON (`ReposResponse`,
`IssueSearchResponse`, `PullRequestResponse`, `PullRequestFilesResponse`,
`PullRequestReviewsResponse`, `CommentsResponse`, `CommitsResponse`), and
the **internal domain models** that `GithubProvider` derives from them
(`Commit`, `PullRequest`, `Review`) plus the aggregates
(`AuthorshipReport`, `PullRequestFetchResult`).
"""

from .authorship_report import AuthorshipReport
from .comments_response import CommentsResponse
from .commit import Commit
from .commits_response import CommitsResponse
from .issue_search_response import IssueSearchResponse
from .pull_request import PullRequest
from .pull_request_fetch_result import PullRequestFetchResult
from .pull_request_files_response import PullRequestFilesResponse
from .pull_request_response import PullRequestResponse
from .pull_request_reviews_response import PullRequestReviewsResponse
from .repos_response import ReposResponse
from .review import Review

__all__ = [
    "AuthorshipReport",
    "CommentsResponse",
    "Commit",
    "CommitsResponse",
    "IssueSearchResponse",
    "PullRequest",
    "PullRequestFetchResult",
    "PullRequestFilesResponse",
    "PullRequestResponse",
    "PullRequestReviewsResponse",
    "ReposResponse",
    "Review",
]
