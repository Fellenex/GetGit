"""Dataclasses describing every JSON shape GetGit emits.

Fetchers return these instances; serialization happens at the storage
boundary via `to_jsonable`. Phase 2 will lift these into FastAPI response
models.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class Commit:
    """A single commit authored by the target user.

    `repo` is the `owner/name` slug. `authored_at` is the author timestamp
    (not the committer timestamp) — these can differ for rebased commits.
    """

    sha: str
    repo: str
    authored_at: datetime
    message: str


@dataclass
class PullRequest:
    """A closed (merged or unmerged) pull request authored by the user.

    `state` is `"merged"` if `merged_at` is set on the underlying PR,
    otherwise `"closed"`. `comments` sums issue comments and review
    comments. `jira_codes` is the deduped list extracted from title,
    body, and branch name via the regex `[A-Z]{2,10}-\\d+`.
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


@dataclass
class AuthorshipReport:
    """The full export for one user — what gets written to disk as JSON."""

    username: str
    generated_at: datetime
    commits: list[Commit]
    pull_requests: list[PullRequest]


def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses, datetimes, and containers into JSON-safe primitives.

    Datetimes become ISO-8601 strings; dataclasses become dicts; lists and
    dicts are walked. Anything else is returned unchanged and must already
    be JSON-serializable.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj
