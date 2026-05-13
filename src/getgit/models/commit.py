"""Commit model."""

from dataclasses import dataclass
from datetime import datetime

from .base import JSONModel


@dataclass
class Commit(JSONModel):
    """A single commit authored by the target user.

    `repo` is the `owner/name` slug. `authored_at` is the author
    timestamp (not the committer timestamp) — they can differ for
    rebased commits.
    """

    sha: str
    repo: str
    authored_at: datetime
    message: str
