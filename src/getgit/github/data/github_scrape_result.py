"""Aggregate result produced by `GithubProvider.fetch_pull_requests`."""

from dataclasses import dataclass, field
from datetime import datetime

from .pull_request import PullRequest
from .review import Review


@dataclass
class GithubScrapeResult:
    """Bundle of everything one PR-side scrape produces.

    Named for the domain, not the endpoint, since it carries the PRs,
    reviews, and commit→PR index that a scrape of GitHub produces (the
    commit list is returned separately by `fetch_commits`).

    `authored` and `participated` partition the PRs the user touched.
    `reviews` is every review the user submitted on either set.
    `commit_pr_index` maps `(repo, commit_sha)` → PR number for any
    commit reachable from any of these PRs.
    """

    authored: list[PullRequest] = field(default_factory=list)
    participated: list[PullRequest] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    commit_pr_index: dict[tuple[str, str], int] = field(default_factory=dict)

    def most_recent_updated_at(
        self, fallback: datetime | None = None
    ) -> datetime | None:
        """Return the newest `updated_at` across authored + participated PRs.

        Falls back to `fallback` when neither set carries a timestamp —
        the caller passes the previous watermark so it holds steady when
        a run collected no PRs.
        """
        timestamps = [
            pr.updated_at
            for pr in (*self.authored, *self.participated)
            if pr.updated_at
        ]
        return max(timestamps) if timestamps else fallback
