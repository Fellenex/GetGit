"""Pull-request fetcher: PRs (authored + participated), reviews, commit→PR index."""

import re
from datetime import datetime
from pathlib import PurePosixPath

import httpx

from ..github_api import paginate
from ..models import PullRequest, Review
from .pull_request_fetch_result import PullRequestFetchResult

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


def _file_extension(filename: str) -> str:
    """Return the file extension (with dot), or the bare basename if there is none.

    Falls back to the full basename so extensionless files like
    `Dockerfile`, `Makefile`, or `.gitignore` get a meaningful key
    instead of all collapsing into a single `""` bucket in the
    additions/deletions dict.
    """
    path = PurePosixPath(filename)
    return path.suffix or path.name


def _key_from_repo_url(repo_url: str) -> str:
    """Convert `https://api.github.com/repos/owner/repo` → `owner/repo`."""
    return "/".join(repo_url.rsplit("/", 2)[-2:])


def _search_keys(client: httpx.Client, query: str) -> set[tuple[str, int]]:
    """Run a /search/issues query and collect `(repo, number)` tuples."""
    keys: set[tuple[str, int]] = set()
    for issue in paginate(client, "/search/issues", {"q": query}):
        keys.add((_key_from_repo_url(issue["repository_url"]), issue["number"]))
    return keys


def _ext_breakdown(
    client: httpx.Client, repo_full: str, number: int
) -> tuple[dict[str, int], dict[str, int]]:
    """Aggregate `additions`/`deletions` from `/pulls/{n}/files` keyed by extension."""
    additions: dict[str, int] = {}
    deletions: dict[str, int] = {}
    for raw in paginate(client, f"/repos/{repo_full}/pulls/{number}/files"):
        ext = _file_extension(raw["filename"])
        additions[ext] = additions.get(ext, 0) + raw.get("additions", 0)
        deletions[ext] = deletions.get(ext, 0) + raw.get("deletions", 0)
    return additions, deletions


def _count_user_comments(
    client: httpx.Client, comments_url: str, username: str
) -> int:
    """Paginate a comments endpoint and count comments authored by `username`."""
    return sum(
        1
        for c in paginate(client, comments_url)
        if (c.get("user") or {}).get("login") == username
    )


def _fetch_user_reviews(
    client: httpx.Client, repo_full: str, number: int, username: str
) -> list[Review]:
    """Return reviews on a PR submitted by `username`, with 1-based per-PR index."""
    reviews: list[Review] = []
    idx = 0
    for raw in paginate(client, f"/repos/{repo_full}/pulls/{number}/reviews"):
        if (raw.get("user") or {}).get("login") != username:
            continue
        idx += 1
        reviews.append(
            Review(
                pr_repo=repo_full,
                pr_number=number,
                index=idx,
                state=raw.get("state", ""),
                submitted_at=_parse_dt(raw.get("submitted_at")),
                body=raw.get("body") or "",
            )
        )
    return reviews


def _hydrate_pr(
    client: httpx.Client,
    repo_full: str,
    number: int,
    username: str,
    fetch_extensions: bool,
) -> tuple[PullRequest, list[Review]]:
    """Fetch all per-PR data and assemble a `PullRequest` plus the user's reviews on it."""
    detail_resp = client.get(f"/repos/{repo_full}/pulls/{number}")
    detail_resp.raise_for_status()
    pr = detail_resp.json()

    if fetch_extensions:
        additions, deletions = _ext_breakdown(client, repo_full, number)
    else:
        additions = {"*": pr.get("additions", 0)}
        deletions = {"*": pr.get("deletions", 0)}

    issue_comments_by_user = _count_user_comments(
        client, f"/repos/{repo_full}/issues/{number}/comments", username
    )
    review_comments_by_user = _count_user_comments(
        client, f"/repos/{repo_full}/pulls/{number}/comments", username
    )

    reviews = _fetch_user_reviews(client, repo_full, number, username)

    pr_obj = PullRequest(
        number=number,
        repo=repo_full,
        title=pr["title"],
        merged=bool(pr.get("merged_at")),
        created_at=_parse_dt(pr["created_at"]),
        closed_at=_parse_dt(pr.get("closed_at")),
        additions=additions,
        deletions=deletions,
        comments=pr.get("comments", 0) + pr.get("review_comments", 0),
        comments_by_author=issue_comments_by_user + review_comments_by_user,
        jira_codes=_extract_jira_codes(
            pr.get("title"), pr.get("body"), (pr.get("head") or {}).get("ref")
        ),
    )
    return pr_obj, reviews


def _index_pr_commits(
    client: httpx.Client, repo_full: str, number: int, index: dict[tuple[str, str], int]
) -> None:
    """Walk a PR's commits and insert each `(repo, sha)` → number into `index`."""
    for c in paginate(client, f"/repos/{repo_full}/pulls/{number}/commits"):
        index[(repo_full, c["sha"])] = number


def fetch_pull_requests(
    client: httpx.Client,
    username: str,
    limit: int | None = None,
    fetch_extensions: bool = True,
) -> PullRequestFetchResult:
    """Collect every closed PR the user authored or participated in.

    "Authored" comes from `author:USER`; "participated" is the union of
    `commenter:USER` and `reviewed-by:USER` minus authored. Per PR we
    fetch detail, file-level additions/deletions (unless
    `fetch_extensions=False`), the user's reviews, both comment streams
    for the user's comment count, and the PR's commit list for the
    `commit_pr_index`.

    `limit` caps each set independently — useful for cheap test runs.
    """
    out = PullRequestFetchResult()

    authored_keys: set[tuple[str, int]] = set()
    for issue in paginate(
        client, "/search/issues", {"q": f"type:pr author:{username} is:closed"}
    ):
        if limit is not None and len(out.authored) >= limit:
            break
        repo_full = _key_from_repo_url(issue["repository_url"])
        number = issue["number"]
        authored_keys.add((repo_full, number))

        pr_obj, reviews = _hydrate_pr(client, repo_full, number, username, fetch_extensions)
        out.authored.append(pr_obj)
        out.reviews.extend(reviews)
        _index_pr_commits(client, repo_full, number, out.commit_pr_index)

    participated_keys = (
        _search_keys(client, f"type:pr commenter:{username} is:closed")
        | _search_keys(client, f"type:pr reviewed-by:{username} is:closed")
    ) - authored_keys

    for repo_full, number in sorted(participated_keys):
        if limit is not None and len(out.participated) >= limit:
            break
        pr_obj, reviews = _hydrate_pr(client, repo_full, number, username, fetch_extensions)
        out.participated.append(pr_obj)
        out.reviews.extend(reviews)
        _index_pr_commits(client, repo_full, number, out.commit_pr_index)

    return out
