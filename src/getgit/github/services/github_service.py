"""High-level facade aggregating per-resource GitHub providers."""

from datetime import datetime

from ...application import AppSettings
from ..data import Commit, PullRequestFetchResult
from ..providers import CommitProvider, PullRequestProvider, RepoProvider


class GithubService:
    """Bundles per-resource providers with the shared `AppSettings`.

    Callers see one object instead of three; `AppSettings` is wired in
    once at construction so each call site stops re-threading
    `username`, `max_*`, and `fetch_extensions`. Each provider still
    talks to the same `GithubClient` it was constructed with — the
    service is a coordinator, not a new transport.
    """

    def __init__(
        self,
        repo_provider: RepoProvider,
        pull_request_provider: PullRequestProvider,
        commit_provider: CommitProvider,
        settings: AppSettings,
    ):
        """Bind the three providers and the settings they all draw from."""
        self._repo_provider = repo_provider
        self._pull_request_provider = pull_request_provider
        self._commit_provider = commit_provider
        self._settings = settings

    def fetch_repositories(self, *, is_self: bool) -> list[dict]:
        """List repos owned by the target user (public-only when `is_self=False`)."""
        return self._repo_provider.list_repos(
            self._settings.username, is_self=is_self
        )

    def fetch_pull_requests(
        self, since: datetime | None = None
    ) -> PullRequestFetchResult:
        """Collect authored + participated PRs, reviews, and a commit→PR index.

        `since`, when set, scopes each search to PRs updated on/after
        that timestamp — passed through to `PullRequestProvider.fetch`.
        """
        return self._pull_request_provider.fetch(
            self._settings.username,
            limit=self._settings.max_prs,
            fetch_extensions=self._settings.fetch_extensions,
            since=since,
        )

    def fetch_commits(
        self,
        repos: list[dict],
        pr_index: dict[tuple[str, str], int],
        since_per_repo: dict[str, datetime] | None = None,
    ) -> list[Commit]:
        """Walk `repos` and collect commits authored by the target user.

        `pr_index` (typically `PullRequestFetchResult.commit_pr_index`)
        attaches the merging PR number to each commit it covers.
        `since_per_repo`, when supplied, restricts each repo's commit
        listing to commits authored on/after the given timestamp.
        """
        return self._commit_provider.fetch(
            repos,
            self._settings.username,
            limit=self._settings.max_commits,
            pr_index=pr_index,
            since_per_repo=since_per_repo,
        )
