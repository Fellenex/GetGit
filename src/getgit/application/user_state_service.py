"""Service coordinating a user's `UserState` load / advance / save."""

from datetime import datetime
from pathlib import Path

from ..github import Commit, GithubScrapeResult
from .data import UserState
from .user_state_repository import UserStateRepository


class UserStateService:
    """Loads, advances, and persists one user's `UserState`.

    Wraps a `UserStateRepository` so callers deal in domain operations
    ("load the current state", "save the next state after this run")
    instead of raw load/save plus watermark arithmetic. The repository
    owns file I/O; this service owns the transition logic.
    """

    def __init__(self, state_repository: UserStateRepository):
        """Bind the repository this service loads from and saves to."""
        self._state_repository = state_repository

    def load_current_state(self) -> UserState:
        """Return the persisted state, or an empty first-run state."""
        return self._state_repository.load()

    def save_new_state(
        self,
        previous: UserState,
        pr_result: GithubScrapeResult,
        commits: list[Commit],
        started_at: datetime,
        partial: bool,
    ) -> Path:
        """Compute the next state from this run's data and persist it.

        Returns the path written.
        """
        return self._state_repository.save(
            self._next_state(previous, pr_result, commits, started_at, partial)
        )

    def _next_state(
        self,
        previous: UserState,
        pr_result: GithubScrapeResult,
        commits: list[Commit],
        started_at: datetime,
        partial: bool,
    ) -> UserState:
        """Compute the next `UserState` to persist.

        On a complete run we advance watermarks to the newest data we
        collected. On a partial run we keep the previous watermarks so
        the next run re-fetches the same window — trying to advance a
        partial creates gaps in coverage between the old watermark and
        the oldest item we managed to collect this time.
        """
        if partial:
            return UserState(
                pr_search_updated_since=previous.pr_search_updated_since,
                commits_per_repo=dict(previous.commits_per_repo),
                last_run_at=started_at,
                last_run_status="partial",
            )

        return UserState(
            pr_search_updated_since=pr_result.most_recent_updated_at(
                previous.pr_search_updated_since
            ),
            commits_per_repo=self._merge_commit_watermarks(
                previous.commits_per_repo, commits
            ),
            last_run_at=started_at,
            last_run_status="complete",
        )

    @staticmethod
    def _merge_commit_watermarks(
        previous: dict[str, datetime], commits: list[Commit]
    ) -> dict[str, datetime]:
        """Merge previous per-repo commit watermarks with the newest `authored_at` per repo from this run."""
        merged = dict(previous)
        for commit in commits:
            existing = merged.get(commit.repo)
            if existing is None or commit.authored_at > existing:
                merged[commit.repo] = commit.authored_at
        return merged
