"""High-level facade over `GithubClient` + `GithubProvider`."""

from datetime import datetime

from ...application import ScrapeSettings
from ..clients import GithubClient
from ..data import Commit, GithubScrapeResult, RepoSummary
from ..providers import GithubProvider


class GithubService:
    """Binds a `GithubProvider` with the shared `ScrapeSettings`.

    Callers see one object; `ScrapeSettings` is wired in once at
    construction so each call site stops re-threading `username`,
    `max_*`, `fetch_extensions`, and `target_repo`. The provider does the
    raw→domain unravelling and the client does the transport — the
    service is a coordinator, not a new transport.
    """

    def __init__(self, provider: GithubProvider, settings: ScrapeSettings):
        """Bind the provider and the settings it draws per-scrape fields from."""
        self._provider = provider
        self._settings = settings

    @classmethod
    def build(cls, client: GithubClient, settings: ScrapeSettings) -> "GithubService":
        """Compose a `GithubService` over a `GithubProvider` from a live client.

        The composition root for the GitHub domain: callers hand over a
        `GithubClient` and `ScrapeSettings` and get back a fully wired
        service without constructing the provider themselves.
        """
        return cls(provider=GithubProvider(client), settings=settings)

    def fetch_repositories(self, *, is_self: bool) -> list[RepoSummary]:
        """List repos owned by the target user (public-only when `is_self=False`)."""
        return self._provider.list_repos(self._settings.username, is_self=is_self)

    def fetch_pull_requests(
        self, since: datetime | None = None
    ) -> GithubScrapeResult:
        """Collect authored + participated PRs, reviews, and a commit→PR index.

        `since`, when set, scopes each search to PRs updated on/after that
        timestamp. `target_repo` (from settings) further scopes searches
        to a single `repo:OWNER/NAME` when set.
        """
        return self._provider.fetch_pull_requests(
            self._settings.username,
            limit=self._settings.max_prs,
            fetch_extensions=self._settings.fetch_extensions,
            since=since,
            target_repo=self._settings.target_repo,
        )

    def fetch_commits(
        self,
        repos: list[RepoSummary],
        pr_index: dict[tuple[str, str], int],
        since_per_repo: dict[str, datetime] | None = None,
    ) -> list[Commit]:
        """Walk `repos` and collect commits authored by the target user.

        `pr_index` (typically `GithubScrapeResult.commit_pr_index`)
        attaches the merging PR number to each commit it covers.
        `since_per_repo`, when supplied, restricts each repo's commit
        listing to commits authored on/after the given timestamp.
        """
        return self._provider.fetch_commits(
            repos,
            self._settings.username,
            limit=self._settings.max_commits,
            pr_index=pr_index,
            since_per_repo=since_per_repo,
        )
