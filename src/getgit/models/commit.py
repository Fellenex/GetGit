"""Commit model."""

from dataclasses import dataclass
from datetime import datetime

from .json_model import JSONModel


@dataclass
class Commit(JSONModel):
    """A single commit authored by the target user.

    `repo` is the `owner/name` slug. `authored_at` is the author
    timestamp (not the committer timestamp) — they can differ for
    rebased commits. `pull_request_number` is the PR this commit was
    merged in, or `None` for direct pushes / commits we couldn't link.
    """

    sha: str
    repo: str
    authored_at: datetime
    message: str
    pull_request_number: int | None = None
