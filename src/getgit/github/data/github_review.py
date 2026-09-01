"""GitHub pull-request review wire-shape object."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class GithubReview:
    """One review as returned by `/repos/{repo}/pulls/{number}/reviews`.

    A wire-shape object. `author_login` is the review author's login (or
    `None` when GitHub omits the `user`), which `GithubProvider` filters
    on to keep only the target user's reviews before assigning the per-PR
    ordinal index and building a domain `Review`.
    """

    author_login: str | None
    state: str
    submitted_at: datetime | None
    body: str
