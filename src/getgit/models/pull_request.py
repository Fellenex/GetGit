"""Pull request model."""

from dataclasses import dataclass, field
from datetime import datetime

from .base import JSONModel


@dataclass
class PullRequest(JSONModel):
    """A closed (merged or unmerged) pull request the target user touched.

    `merged` distinguishes the two terminal states (we only query
    `is:closed`, so an unmerged PR here means closed-without-merge).
    `comments` sums issue comments and review comments (all authors).
    `comments_by_author` is the subset authored by the target user —
    for an authored PR this is "self-replies", for a participated PR
    it's the reason the PR is in the report.
    `additions` and `deletions` are dicts keyed by file extension
    (e.g. `{".py": 20, ".yml": 5}`); the empty key `""` is files with no
    extension. The sentinel key `"*"` means the per-extension breakdown
    was disabled (`--no-extension-breakdown`) and the value is the
    aggregate total.
    `jira_codes` is keyed by project prefix and maps to the sorted,
    deduped list of full codes for that project (e.g.
    `{"WD": ["WD-1234", "WD-5678"], "YWFB": ["YWFB-99"]}`). Codes are
    extracted from title, body, and branch name via the regex
    `[A-Z]{2,10}-\\d+`.
    """

    number: int
    repo: str
    title: str
    merged: bool
    created_at: datetime
    closed_at: datetime | None
    additions: dict[str, int]
    deletions: dict[str, int]
    comments: int
    comments_by_author: int
    jira_codes: dict[str, list[str]] = field(default_factory=dict)
