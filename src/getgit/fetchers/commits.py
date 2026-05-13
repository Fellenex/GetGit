"""Commit-history fetcher."""

from datetime import datetime

import httpx

from ..github_client import GithubClient
from ..models import Commit


class CommitFetcher:
    """Walks repos and collects commits authored by a target user."""

    def __init__(self, client: GithubClient):
        """Bind to a `GithubClient` for all subsequent calls."""
        self._client = client

    def fetch(
        self,
        repos: list[dict],
        username: str,
        limit: int | None = None,
        pr_index: dict[tuple[str, str], int] | None = None,
    ) -> list[Commit]:
        """Collect commits authored by `username` across `repos`.

        Uses `/repos/{full_name}/commits?author=...`, which avoids the
        /search/commits rate cap. Empty repos return 409 and are
        skipped; repos that 404 (deleted or now-private) are also
        skipped.

        `limit` caps the number of commits returned. `pr_index` (built
        by `PullRequestFetcher.fetch`) maps `(repo, sha)` → PR number;
        commits not in the index keep `pull_request_number=None`.
        """
        pr_index = pr_index or {}
        commits: list[Commit] = []
        for repo in repos:
            if limit is not None and len(commits) >= limit:
                break
            full_name = repo["full_name"]
            try:
                for raw in self._client.paginate(
                    f"/repos/{full_name}/commits", {"author": username}
                ):
                    commits.append(self._build_commit(raw, full_name, pr_index))
                    if limit is not None and len(commits) >= limit:
                        break
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 409):
                    continue
                raise
        return commits

    @staticmethod
    def _build_commit(
        raw: dict, full_name: str, pr_index: dict[tuple[str, str], int]
    ) -> Commit:
        """Materialize a `Commit` from a raw GitHub commit payload."""
        ca = raw["commit"]["author"]
        return Commit(
            sha=raw["sha"],
            repo=full_name,
            authored_at=datetime.fromisoformat(ca["date"].replace("Z", "+00:00")),
            message=raw["commit"]["message"],
            pull_request_number=pr_index.get((full_name, raw["sha"])),
        )
