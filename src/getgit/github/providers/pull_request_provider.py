"""Pull-request provider: PRs (authored + participated), reviews, commit→PR index."""

import re
from datetime import datetime
from pathlib import PurePosixPath

from ..clients import GithubClient, RateLimitExceededError
from ..data import PullRequest, PullRequestFetchResult, Review


class PullRequestProvider:
    """Collects PRs (authored + participated), reviews, and a commit→PR index."""

    _JIRA_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")
    """Matches JIRA-style ticket codes (e.g. WD-6000, YWFB-300, PTR-8000)."""

    def __init__(self, client: GithubClient):
        """Bind to a `GithubClient` for all subsequent calls."""
        self._client = client

    def fetch(
        self,
        username: str,
        limit: int | None = None,
        fetch_extensions: bool = True,
        since: datetime | None = None,
    ) -> PullRequestFetchResult:
        """Collect every closed PR the user authored or participated in.

        "Authored" comes from `author:USER`; "participated" is the union
        of `commenter:USER` and `reviewed-by:USER` minus authored. Per
        PR we fetch detail, file-level additions/deletions (unless
        `fetch_extensions=False`), the user's reviews, both comment
        streams for the user's comment count, and the PR's commit list
        for the `commit_pr_index`.

        `since` constrains every search query with `updated:>=<since>`
        so resumed runs skip PRs that haven't changed. `limit` caps
        each set independently. On rate limit, attaches the
        partially-built `PullRequestFetchResult` to the raised
        `RateLimitExceededError` so the orchestrator can still emit a
        partial report.
        """
        out = PullRequestFetchResult()
        try:
            authored_keys: set[tuple[str, int]] = set()
            for issue in self._client.paginate(
                "/search/issues",
                {"q": self._build_query(f"author:{username}", since)},
            ):
                if limit is not None and len(out.authored) >= limit:
                    break
                repo_full = self._key_from_repo_url(issue["repository_url"])
                number = issue["number"]
                authored_keys.add((repo_full, number))

                pr_obj, reviews = self._hydrate_pr(
                    repo_full, number, username, fetch_extensions
                )
                out.authored.append(pr_obj)
                out.reviews.extend(reviews)
                self._index_pr_commits(repo_full, number, out.commit_pr_index)

            participated_keys = (
                self._search_keys(self._build_query(f"commenter:{username}", since))
                | self._search_keys(self._build_query(f"reviewed-by:{username}", since))
            ) - authored_keys

            for repo_full, number in sorted(participated_keys):
                if limit is not None and len(out.participated) >= limit:
                    break
                pr_obj, reviews = self._hydrate_pr(
                    repo_full, number, username, fetch_extensions
                )
                out.participated.append(pr_obj)
                out.reviews.extend(reviews)
                self._index_pr_commits(repo_full, number, out.commit_pr_index)

            return out
        except RateLimitExceededError as e:
            e.partial = out
            raise

    @staticmethod
    def _build_query(scope: str, since: datetime | None) -> str:
        """Compose a /search/issues `q=` value, appending `updated:>=` when `since` is set."""
        parts = ["type:pr", scope, "is:closed"]
        if since is not None:
            parts.append(f"updated:>={since.isoformat()}")
        return " ".join(parts)

    def _search_keys(self, query: str) -> set[tuple[str, int]]:
        """Run a /search/issues query and collect `(repo, number)` tuples."""
        keys: set[tuple[str, int]] = set()
        for issue in self._client.paginate("/search/issues", {"q": query}):
            keys.add(
                (self._key_from_repo_url(issue["repository_url"]), issue["number"])
            )
        return keys

    def _hydrate_pr(
        self, repo_full: str, number: int, username: str, fetch_extensions: bool
    ) -> tuple[PullRequest, list[Review]]:
        """Fetch all per-PR data and assemble a `PullRequest` plus the user's reviews on it."""
        detail_resp = self._client.get(f"/repos/{repo_full}/pulls/{number}")
        detail_resp.raise_for_status()
        pr = detail_resp.json()

        if fetch_extensions:
            additions, deletions = self._ext_breakdown(repo_full, number)
        else:
            total_a = pr.get("additions", 0)
            total_d = pr.get("deletions", 0)
            additions = {"*": total_a} if total_a else {}
            deletions = {"*": total_d} if total_d else {}

        issue_comments_by_user = self._count_user_comments(
            f"/repos/{repo_full}/issues/{number}/comments", username
        )
        review_comments_by_user = self._count_user_comments(
            f"/repos/{repo_full}/pulls/{number}/comments", username
        )

        reviews = self._fetch_user_reviews(repo_full, number, username)

        pr_obj = PullRequest(
            number=number,
            repo=repo_full,
            title=pr["title"],
            merged=bool(pr.get("merged_at")),
            created_at=self._parse_dt(pr["created_at"]),
            closed_at=self._parse_dt(pr.get("closed_at")),
            updated_at=self._parse_dt(pr["updated_at"]),
            additions=additions,
            deletions=deletions,
            comments=pr.get("comments", 0) + pr.get("review_comments", 0),
            comments_by_author=issue_comments_by_user + review_comments_by_user,
            jira_codes=self._extract_jira_codes(pr.get("body")),
        )
        return pr_obj, reviews

    def _ext_breakdown(
        self, repo_full: str, number: int
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Aggregate `additions`/`deletions` from `/pulls/{n}/files` keyed by extension.

        Zero-valued entries are omitted: a `.unity` file with 3 deletions
        and 0 additions appears in `deletions` only, not in `additions`.
        Keeps the two dicts asymmetric and lossless — consumers iterate
        only over real edits.
        """
        additions: dict[str, int] = {}
        deletions: dict[str, int] = {}
        for raw in self._client.paginate(f"/repos/{repo_full}/pulls/{number}/files"):
            ext = self._file_extension(raw["filename"])
            a = raw.get("additions", 0)
            d = raw.get("deletions", 0)
            if a:
                additions[ext] = additions.get(ext, 0) + a
            if d:
                deletions[ext] = deletions.get(ext, 0) + d
        return additions, deletions

    def _count_user_comments(self, comments_url: str, username: str) -> int:
        """Paginate a comments endpoint and count comments authored by `username`."""
        return sum(
            1
            for c in self._client.paginate(comments_url)
            if (c.get("user") or {}).get("login") == username
        )

    def _fetch_user_reviews(
        self, repo_full: str, number: int, username: str
    ) -> list[Review]:
        """Return reviews on a PR submitted by `username`, with 1-based per-PR index."""
        reviews: list[Review] = []
        idx = 0
        for raw in self._client.paginate(f"/repos/{repo_full}/pulls/{number}/reviews"):
            if (raw.get("user") or {}).get("login") != username:
                continue
            idx += 1
            reviews.append(
                Review(
                    pr_repo=repo_full,
                    pr_number=number,
                    index=idx,
                    state=raw.get("state", ""),
                    submitted_at=self._parse_dt(raw.get("submitted_at")),
                    body=raw.get("body") or "",
                )
            )
        return reviews

    def _index_pr_commits(
        self, repo_full: str, number: int, index: dict[tuple[str, str], int]
    ) -> None:
        """Walk a PR's commits and insert each `(repo, sha)` → number into `index`."""
        for c in self._client.paginate(f"/repos/{repo_full}/pulls/{number}/commits"):
            index[(repo_full, c["sha"])] = number

    @classmethod
    def _extract_jira_codes(cls, *texts: str | None) -> list[str]:
        """Pull JIRA codes from any number of text blobs.

        Uses a set internally so deduping is automatic; returns a sorted
        list so the JSON output is deterministic across runs. An input
        with no codes yields an empty list.
        """
        found: set[str] = set()
        for text in texts:
            if text:
                found.update(cls._JIRA_RE.findall(text))
        return sorted(found)

    @staticmethod
    def _parse_dt(s: str | None) -> datetime | None:
        """Parse a GitHub ISO-8601 timestamp, returning None if the input is missing."""
        if not s:
            return None
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    @staticmethod
    def _file_extension(filename: str) -> str:
        """Return the file extension (with dot), or the bare basename if there is none.

        Falls back to the full basename so extensionless files like
        `Dockerfile`, `Makefile`, or `.gitignore` get a meaningful key
        instead of all collapsing into a single `""` bucket in the
        additions/deletions dict.
        """
        path = PurePosixPath(filename)
        return path.suffix or path.name

    @staticmethod
    def _key_from_repo_url(repo_url: str) -> str:
        """Convert `https://api.github.com/repos/owner/repo` → `owner/repo`."""
        return "/".join(repo_url.rsplit("/", 2)[-2:])
