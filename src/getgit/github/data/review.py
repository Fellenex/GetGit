"""Code-review model."""

from dataclasses import dataclass
from datetime import datetime

from ...infrastructure.data import JSONModel


@dataclass
class Review(JSONModel):
    """A code review submitted by the target user on some PR.

    `index` is a 1-based ordinal among the user's reviews on the source
    PR, in submission order — useful for distinguishing repeat reviews
    on the same PR. `state` is GitHub's review state
    (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`, `DISMISSED`).
    """

    pr_repo: str
    pr_number: int
    index: int
    state: str
    submitted_at: datetime | None
    body: str
