from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class Commit:
    sha: str
    repo: str
    authored_at: datetime
    message: str


@dataclass
class PullRequest:
    number: int
    repo: str
    title: str
    state: str  # "merged" or "closed"
    merged: bool
    created_at: datetime
    closed_at: datetime | None
    additions: int
    deletions: int
    comments: int
    jira_codes: list[str] = field(default_factory=list)


@dataclass
class AuthorshipReport:
    username: str
    generated_at: datetime
    commits: list[Commit]
    pull_requests: list[PullRequest]


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj
