"""Per-username state — what GitHub data we've collected, used for resumable runs."""

from dataclasses import dataclass, field
from datetime import datetime

from ...infrastructure.data import JSONModel


@dataclass
class UserState(JSONModel):
    """Persistent record of how far we've gotten collecting data for a user.

    Stored at `output/<username>/state.json`. The watermarks drive the
    next run's GitHub API calls (PR search via `updated:>=`, per-repo
    commits via `since=`) so we don't traverse data we've already seen.

    `pr_search_updated_since` is the most recent `updated_at` across
    materialized PRs. `commits_per_repo` maps `owner/repo` → the most
    recent commit `authored_at` for that repo. `last_run_at` /
    `last_run_status` are housekeeping ("did the last run finish
    cleanly?"). On a `partial` run the watermarks intentionally do
    *not* advance, so the next run re-fetches the same window.

    Inherits `to_jsonable()` from `JSONModel` for consistent
    serialization with the rest of the data layer.
    """

    pr_search_updated_since: datetime | None = None
    commits_per_repo: dict[str, datetime] = field(default_factory=dict)
    last_run_at: datetime | None = None
    last_run_status: str = "never"
