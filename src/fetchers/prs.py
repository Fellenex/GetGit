import re
from datetime import datetime

import httpx

from ..github_api import paginate
from ..models import PullRequest

JIRA_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")


def _extract_jira_codes(*texts: str | None) -> list[str]:
    seen: list[str] = []
    for text in texts:
        if not text:
            continue
        for match in JIRA_RE.findall(text):
            if match not in seen:
                seen.append(match)
    return seen


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fetch_pull_requests(client: httpx.Client, username: str) -> list[PullRequest]:
    query = f"type:pr author:{username} is:closed"
    results: list[PullRequest] = []
    for issue in paginate(client, "/search/issues", {"q": query}):
        repo_url = issue["repository_url"]  # https://api.github.com/repos/{owner}/{repo}
        repo_full = "/".join(repo_url.rsplit("/", 2)[-2:])
        number = issue["number"]

        detail_resp = client.get(f"/repos/{repo_full}/pulls/{number}")
        detail_resp.raise_for_status()
        pr = detail_resp.json()

        merged = bool(pr.get("merged_at"))
        results.append(
            PullRequest(
                number=number,
                repo=repo_full,
                title=pr["title"],
                state="merged" if merged else "closed",
                merged=merged,
                created_at=_parse_dt(pr["created_at"]),
                closed_at=_parse_dt(pr.get("closed_at")),
                additions=pr.get("additions", 0),
                deletions=pr.get("deletions", 0),
                comments=pr.get("comments", 0) + pr.get("review_comments", 0),
                jira_codes=_extract_jira_codes(
                    pr.get("title"), pr.get("body"), (pr.get("head") or {}).get("ref")
                ),
            )
        )
    return results
