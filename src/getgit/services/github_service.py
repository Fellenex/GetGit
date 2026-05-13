"""High-level facade aggregating per-resource fetchers."""

from ..application import AppSettings
from ..fetchers import (
    CommitFetcher,
    PullRequestFetcher,
    PullRequestFetchResult,
    RepoFetcher,
)
from ..models import Commit


class GithubService:
    """Bundles per-resource fetchers with the shared `AppSettings`.

    Callers see one object instead of three; `AppSettings` is wired in
    once at construction so each call site stops re-threading
    `username`, `max_*`, and `fetch_extensions`. Each fetcher still
    talks to the same `GithubClient` it was constructed with — the
    service is a coordinator, not a new transport.
    """

    def __init__(
        self,
        repo_fetcher: RepoFetcher,
        pull_request_fetcher: PullRequestFetcher,
        commit_fetcher: CommitFetcher,
        settings: AppSettings,
    ):
        """Bind the three fetchers and the settings they all draw from."""
        self._repo_fetcher = repo_fetcher
        self._pull_request_fetcher = pull_request_fetcher
        self._commit_fetcher = commit_fetcher
        self._settings = settings

    def fetch_repositories(self, *, is_self: bool) -> list[dict]:
        """List repos owned by the target user (public-only when `is_self=False`)."""
        return self._repo_fetcher.list_repos(
            self._settings.username, is_self=is_self
        )

    def fetch_pull_requests(self) -> PullRequestFetchResult:
        """Collect authored + participated PRs, reviews, and a commit→PR index."""
        return self._pull_request_fetcher.fetch(
            self._settings.username,
            limit=self._settings.max_prs,
            fetch_extensions=self._settings.fetch_extensions,
        )

    def fetch_commits(
        self, repos: list[dict], pr_index: dict[tuple[str, str], int]
    ) -> list[Commit]:
        """Walk `repos` and collect commits authored by the target user.

        `pr_index` (typically `PullRequestFetchResult.commit_pr_index`)
        attaches the merging PR number to each commit it covers.
        """
        return self._commit_fetcher.fetch(
            repos,
            self._settings.username,
            limit=self._settings.max_commits,
            pr_index=pr_index,
        )
