"""Top-level authorship report — what gets written to disk as JSON."""

from dataclasses import dataclass
from datetime import datetime

from .base import JSONModel
from .commit import Commit
from .pull_request import PullRequest


@dataclass
class AuthorshipReport(JSONModel):
    """The full export for one user."""

    username: str
    generated_at: datetime
    commits: list[Commit]
    pull_requests: list[PullRequest]
