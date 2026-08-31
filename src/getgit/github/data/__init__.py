"""GitHub-domain data classes.

Two families live here: the **wire-shape response objects** that
`GithubClient` builds from raw GitHub JSON (`RepoSummary`,
`IssueSearchResult`, `PullRequestDetail`, `PullRequestFile`,
`PullRequestReview`, `Comment`, `CommitPayload`), and the **internal
domain models** that `GithubProvider` derives from them (`Commit`,
`PullRequest`, `Review`) plus the aggregates (`AuthorshipReport`,
`GithubScrapeResult`).
"""

from .authorship_report import AuthorshipReport
from .comment import Comment
from .commit import Commit
from .commit_payload import CommitPayload
from .github_scrape_result import GithubScrapeResult
from .issue_search_result import IssueSearchResult
from .pull_request import PullRequest
from .pull_request_detail import PullRequestDetail
from .pull_request_file import PullRequestFile
from .pull_request_review import PullRequestReview
from .repo_summary import RepoSummary
from .review import Review

__all__ = [
    "AuthorshipReport",
    "Comment",
    "Commit",
    "CommitPayload",
    "GithubScrapeResult",
    "IssueSearchResult",
    "PullRequest",
    "PullRequestDetail",
    "PullRequestFile",
    "PullRequestReview",
    "RepoSummary",
    "Review",
]
