"""Per-username checkpoint — tracks what GitHub data has already been collected."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Checkpoint:
    """Persistent watermark of the most recent data we've seen for a user.

    `pr_search_updated_since` is the most recent `updated_at` among PRs
    we've materialized — used to constrain the next run's PR search via
    `updated:>=<...>`. `commits_per_repo` maps `owner/repo` to the most
    recent commit `authored_at` we've seen in that repo — used to pass
    `since=<...>` to `/repos/{repo}/commits`. `last_run_at` /
    `last_run_status` are housekeeping for "did the last run finish
    cleanly?". On `partial` runs the watermarks intentionally do *not*
    advance, so the next run re-fetches the same window.
    """

    pr_search_updated_since: datetime | None = None
    commits_per_repo: dict[str, datetime] = field(default_factory=dict)
    last_run_at: datetime | None = None
    last_run_status: str = "never"
