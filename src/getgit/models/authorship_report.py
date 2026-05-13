"""Top-level authorship report — what gets written to disk as JSON."""

from dataclasses import dataclass
from datetime import datetime

from .json_model import JSONModel
from .commit import Commit
from .pull_request import PullRequest
from .review import Review


@dataclass
class AuthorshipReport(JSONModel):
    """The full export for one user.

    PRs are split into two collections: `authored_pull_requests` are
    PRs the user opened; `participated_pull_requests` are PRs the user
    commented on or reviewed but did not author. `reviews` is a flat
    list of every review the user submitted, on either set of PRs.
    """

    username: str
    generated_at: datetime
    commits: list[Commit]
    authored_pull_requests: list[PullRequest]
    participated_pull_requests: list[PullRequest]
    reviews: list[Review]
