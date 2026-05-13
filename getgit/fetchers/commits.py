from datetime import datetime

import httpx

from ..github_api import paginate
from ..models import Commit


def fetch_commits(client: httpx.Client, repos: list[dict], username: str) -> list[Commit]:
    commits: list[Commit] = []
    for repo in repos:
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
                    )
                )
        except httpx.HTTPStatusError as e:
            # Empty repos return 409; skip silently.
            if e.response.status_code in (404, 409):
                continue
            raise
    return commits
