"""GitHub-domain data classes.

Two families live here: the **wire-shape objects** that `GithubClient`
builds from raw GitHub JSON (`GithubRepo`, `GithubIssue`, `GithubCommit`,
`GithubPullRequest`, `GithubPullRequestChangedFile`, `GithubReview`,
`GithubComment`), and the **internal domain models** that `GithubProvider`
derives from them (`Commit`, `PullRequest`, `Review`) plus the aggregates
(`AuthorshipReport`, `PullRequestFetchResult`).
"""

from .authorship_report import AuthorshipReport
from .commit import Commit
from .github_comment import GithubComment
from .github_commit import GithubCommit
from .github_issue import GithubIssue
from .github_pull_request import GithubPullRequest
from .github_pull_request_changed_file import GithubPullRequestChangedFile
from .github_repo import GithubRepo
from .github_review import GithubReview
from .pull_request import PullRequest
from .pull_request_fetch_result import PullRequestFetchResult
from .review import Review

__all__ = [
    "AuthorshipReport",
    "Commit",
    "GithubComment",
    "GithubCommit",
    "GithubIssue",
    "GithubPullRequest",
    "GithubPullRequestChangedFile",
    "GithubRepo",
    "GithubReview",
    "PullRequest",
    "PullRequestFetchResult",
    "Review",
]
