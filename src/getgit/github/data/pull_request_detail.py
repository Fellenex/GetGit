"""GitHub pull-request detail response object."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PullRequestDetail:
    """A single PR as returned by `/repos/{repo}/pulls/{number}`.

    A wire-shape response object: it mirrors GitHub's fields (with the
    timestamps already parsed to `datetime` at the client boundary) and
    holds *no* derived values. The business rules that turn these into a
    domain `PullRequest` — `merged = merged_at is not None`, summing
    `comments + review_comments`, the `additions`/`deletions` totals vs
    per-extension breakdown, JIRA-code extraction from `title`/`body` —
    live in `GithubProvider`, not here.
    """

    title: str
    body: str | None
    merged_at: datetime | None
    created_at: datetime
    closed_at: datetime | None
    updated_at: datetime
    additions: int
    deletions: int
    comments: int
    review_comments: int
