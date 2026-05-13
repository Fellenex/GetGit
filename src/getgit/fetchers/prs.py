"""Pull-request fetcher with JIRA-code extraction and commit→PR indexing."""

import re
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from ..github_api import paginate
from ..models import PullRequest

JIRA_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")
"""Matches JIRA-style ticket codes (e.g. WD-6000, YWFB-300, PTR-8000)."""


@dataclass
class PullRequestFetchResult:
    """Bundle of everything one pass over the PR list produces.

    `pull_requests` is the list of materialized PRs. `commit_pr_index`
    maps `(repo, commit_sha)` → PR number for every commit reachable
    from those PRs — built in the same loop so we walk the PR list once.
    """

    pull_requests: list[PullRequest] = field(default_factory=list)
    commit_pr_index: dict[tuple[str, str], int] = field(default_factory=dict)


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
) -> PullRequestFetchResult:
    """Find every closed PR authored by `username`, enrich it, and index its commits.

    Each PR costs two GitHub calls — one to `/repos/.../pulls/{n}` for
    detail fields the search API doesn't return (`additions`,
    `deletions`, `merged_at`, branch ref, `review_comments`) and one to
    `/repos/.../pulls/{n}/commits` to populate the commit→PR index.
    Both happen in the same loop so we traverse the PR list exactly once.

    `limit` caps the number of PRs processed — useful for cheap test runs
    so we don't burn rate limit. `None` means no cap.
    """
    query = f"type:pr author:{username} is:closed"
    out = PullRequestFetchResult()
    for issue in paginate(client, "/search/issues", {"q": query}):
        if limit is not None and len(out.pull_requests) >= limit:
            break
        repo_url = issue["repository_url"]
        repo_full = "/".join(repo_url.rsplit("/", 2)[-2:])
        number = issue["number"]

        detail_resp = client.get(f"/repos/{repo_full}/pulls/{number}")
        detail_resp.raise_for_status()
        pr = detail_resp.json()

        out.pull_requests.append(
            PullRequest(
                number=number,
                repo=repo_full,
                title=pr["title"],
                merged=bool(pr.get("merged_at")),
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

        for commit in paginate(client, f"/repos/{repo_full}/pulls/{number}/commits"):
            out.commit_pr_index[(repo_full, commit["sha"])] = number

    return out
