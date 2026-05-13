"""Commit-history fetcher."""

from datetime import datetime

import httpx

from ..github_api import paginate
from ..models import Commit


def fetch_commits(
    client: httpx.Client,
    repos: list[dict],
    username: str,
    limit: int | None = None,
    pr_index: dict[tuple[str, str], int] | None = None,
) -> list[Commit]:
    """Walk every repo and collect commits authored by `username`.

    Uses `/repos/{full_name}/commits?author=...`, which avoids the
    /search/commits rate cap. Empty repos return 409 and are skipped;
    repos that 404 (deleted or now-private) are also skipped.

    `limit` caps the number of commits returned — useful for cheap test
    runs so we don't burn rate limit. `None` means no cap.

    `pr_index` (built by `prs.build_commit_pr_index`) maps
    `(repo, sha)` → PR number, so each commit gets its merging PR
    attached. Commits not in the index (direct pushes) keep
    `pull_request_number=None`.
    """
    pr_index = pr_index or {}
    commits: list[Commit] = []
    for repo in repos:
        if limit is not None and len(commits) >= limit:
            break
        full_name = repo["full_name"]
        try:
            for raw in paginate(
                client, f"/repos/{full_name}/commits", {"author": username}
            ):
                ca = raw["commit"]["author"]
                commits.append(
                    Commit(
                        sha=raw["sha"],
                        repo=full_name,
                        authored_at=datetime.fromisoformat(ca["date"].replace("Z", "+00:00")),
                        message=raw["commit"]["message"],
                        pull_request_number=pr_index.get((full_name, raw["sha"])),
                    )
                )
                if limit is not None and len(commits) >= limit:
                    break
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 409):
                continue
            raise
    return commits
