"""Commit-history provider."""

from datetime import datetime

import httpx

from ..clients import GithubClient, RateLimitExceededError
from ..data import Commit


class CommitProvider:
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
        since_per_repo: dict[str, datetime] | None = None,
    ) -> list[Commit]:
        """Collect commits authored by `username` across `repos`.

        Uses `/repos/{full_name}/commits?author=...`, which avoids the
        /search/commits rate cap. Empty repos return 409 and are
        skipped; repos that 404 (deleted or now-private) are also
        skipped.

        `since_per_repo` maps `owner/name` → datetime; when present for
        a repo, the call adds `since=<...>` to skip commits already
        collected in a previous run. `limit` caps the number of commits
        returned. `pr_index` (built by `PullRequestProvider.fetch`) maps
        `(repo, sha)` → PR number; commits not in the index keep
        `pull_request_number=None`. On rate limit, attaches the partial
        commit list already collected to the raised
        `RateLimitExceededError`.
        """
        pr_index = pr_index or {}
        since_per_repo = since_per_repo or {}
        commits: list[Commit] = []
        try:
            for repo in repos:
                if limit is not None and len(commits) >= limit:
                    break
                full_name = repo["full_name"]
                params: dict[str, str] = {"author": username}
                if full_name in since_per_repo:
                    params["since"] = since_per_repo[full_name].isoformat()
                try:
                    for raw in self._client.paginate(
                        f"/repos/{full_name}/commits", params
                    ):
                        commits.append(self._build_commit(raw, full_name, pr_index))
                        if limit is not None and len(commits) >= limit:
                            break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (404, 409):
                        continue
                    raise
            return commits
        except RateLimitExceededError as e:
            e.partial = commits
            raise

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
