"""Pull-request fetcher with JIRA-code extraction."""

import re
from datetime import datetime

import httpx

from ..github_api import paginate
from ..models import PullRequest

JIRA_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")
"""Matches JIRA-style ticket codes (e.g. WD-6000, YWFB-300, PTR-8000)."""


def _extract_jira_codes(*texts: str | None) -> list[str]:
    """Pull JIRA codes from any number of text blobs.

    Uses a set internally so deduping is automatic; returns a sorted list
    so the JSON output is deterministic across runs.
    """
    found: set[str] = set()
    for text in texts:
        if text:
            found.update(JIRA_RE.findall(text))
    return sorted(found)


def _parse_dt(s: str | None) -> datetime | None:
    """Parse a GitHub ISO-8601 timestamp, returning None if the input is missing."""
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fetch_pull_requests(
    client: httpx.Client, username: str, limit: int | None = None
) -> list[PullRequest]:
    """Find every closed PR authored by `username` and enrich each with detail fields.

    Search returns lightweight issue records; a follow-up
    `/repos/{owner}/{repo}/pulls/{n}` fetch is required for `additions`,
    `deletions`, `review_comments`, and `merged_at`. JIRA codes are
    extracted from the PR title, body, and head branch name.

    `limit` caps the number of PRs returned — useful for cheap test runs
    so we don't burn rate limit. `None` means no cap.
    """
    query = f"type:pr author:{username} is:closed"
    results: list[PullRequest] = []
    for issue in paginate(client, "/search/issues", {"q": query}):
        if limit is not None and len(results) >= limit:
            break
        repo_url = issue["repository_url"]
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
