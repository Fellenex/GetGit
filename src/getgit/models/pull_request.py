"""Pull request model."""

from dataclasses import dataclass, field
from datetime import datetime

from .base import JSONModel


@dataclass
class PullRequest(JSONModel):
    """A closed (merged or unmerged) pull request authored by the user.

    `state` is `"merged"` if the PR has a `merged_at`, otherwise
    `"closed"`. `comments` sums issue comments and review comments.
    `jira_codes` is the deduped list extracted from title, body, and
    branch name via the regex `[A-Z]{2,10}-\\d+`.
    """

    number: int
    repo: str
    title: str
    state: str
    merged: bool
    created_at: datetime
    closed_at: datetime | None
    additions: int
    deletions: int
    comments: int
    jira_codes: list[str] = field(default_factory=list)
