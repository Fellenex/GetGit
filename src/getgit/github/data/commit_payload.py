"""GitHub commit-listing response object."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CommitPayload:
    """One commit as returned by `/repos/{full_name}/commits`.

    A wire-shape response object: `GithubClient` flattens GitHub's nested
    `commit.author.date` / `commit.message` shape into these flat fields
    (parsing the author date to `datetime` at the boundary). The domain
    `Commit` — including the PR-number lookup against the commit→PR index
    — is assembled from this by `GithubProvider`.
    """

    sha: str
    authored_at: datetime
    message: str
