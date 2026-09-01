"""GitHub mapper: the wire-shape → domain business rules, with no transport."""

import re
from datetime import datetime
from pathlib import PurePosixPath

from ..data import (
    Commit,
    GithubComment,
    GithubCommit,
    GithubPullRequest,
    GithubPullRequestChangedFile,
    GithubReview,
    PullRequest,
    Review,
)


class GithubMapper:
    """Turns `GithubClient`'s wire-shape objects into internal domain objects.

    A stateless collection of the raw→domain business rules — JIRA-code
    extraction, the per-extension additions/deletions breakdown, comment
    counting, the `merged`/comment-sum derivations, the search-query
    composition, the commit and review assembly. Every method is a
    `@staticmethod`/`@classmethod` over already-fetched values: the
    mapper holds no client and issues no requests, so it is unit-testable
    without a transport double.

    `GithubProvider` owns the fetch orchestration and the partial-result
    error contract and calls into this mapper for each transform; the
    client owns routes and pagination. See [ADR-063] for why the two
    axes (orchestration vs mapping) live in separate classes.
    """

    _JIRA_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")
    """Matches JIRA-style ticket codes (e.g. WD-6000, YWFB-300, PTR-8000)."""

    @staticmethod
    def build_query(
        scope: str, since: datetime | None, target_repo: str | None
    ) -> str:
        """Compose a /search/issues `q=` value with optional `updated:>=` and `repo:` filters."""
        parts = ["type:pr", scope, "is:closed"]
        if since is not None:
            parts.append(f"updated:>={since.isoformat()}")
        if target_repo is not None:
            parts.append(f"repo:{target_repo}")
        return " ".join(parts)

    @classmethod
    def build_pull_request(
        cls,
        detail: GithubPullRequest,
        repo_full: str,
        number: int,
        additions: dict[str, int],
        deletions: dict[str, int],
        comments_by_author: int,
    ) -> PullRequest:
        """Assemble a domain `PullRequest` from a PR detail plus its already-computed parts.

        Applies the wire→domain derivations that must not live on the
        wire object: `merged = merged_at is not None`, the
        `comments + review_comments` sum, and JIRA-code extraction from
        the title and body. `additions`/`deletions` and
        `comments_by_author` are computed by the caller (they need extra
        client calls) and passed in.
        """
        return PullRequest(
            number=number,
            repo=repo_full,
            title=detail.title,
            merged=detail.merged_at is not None,
            created_at=detail.created_at,
            closed_at=detail.closed_at,
            updated_at=detail.updated_at,
            additions=additions,
            deletions=deletions,
            comments=detail.comments + detail.review_comments,
            comments_by_author=comments_by_author,
            jira_codes=cls.extract_jira_codes(detail.title, detail.body),
        )

    @classmethod
    def breakdown_from_files(
        cls, files: list[GithubPullRequestChangedFile]
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Aggregate `additions`/`deletions` from a PR's files keyed by extension.

        Zero-valued entries are omitted: a `.unity` file with 3 deletions
        and 0 additions appears in `deletions` only, not in `additions`.
        Keeps the two dicts asymmetric and lossless — consumers iterate
        only over real edits.
        """
        additions: dict[str, int] = {}
        deletions: dict[str, int] = {}
        for f in files:
            ext = cls._file_extension(f.filename)
            if f.additions:
                additions[ext] = additions.get(ext, 0) + f.additions
            if f.deletions:
                deletions[ext] = deletions.get(ext, 0) + f.deletions
        return additions, deletions

    @staticmethod
    def count_user_comments(comments: list[GithubComment], username: str) -> int:
        """Count comments authored by `username` in a comment stream."""
        return sum(1 for c in comments if c.author_login == username)

    @staticmethod
    def user_reviews(
        reviews: list[GithubReview], repo_full: str, number: int, username: str
    ) -> list[Review]:
        """Keep `username`'s reviews on a PR, assigning each a 1-based per-PR index."""
        out: list[Review] = []
        idx = 0
        for r in reviews:
            if r.author_login != username:
                continue
            idx += 1
            out.append(
                Review(
                    pr_repo=repo_full,
                    pr_number=number,
                    index=idx,
                    state=r.state,
                    submitted_at=r.submitted_at,
                    body=r.body,
                )
            )
        return out

    @staticmethod
    def build_commit(
        payload: GithubCommit, full_name: str, pr_index: dict[tuple[str, str], int]
    ) -> Commit:
        """Materialize a `Commit` from a `GithubCommit`, linking its PR number if indexed."""
        return Commit(
            sha=payload.sha,
            repo=full_name,
            authored_at=payload.authored_at,
            message=payload.message,
            pull_request_number=pr_index.get((full_name, payload.sha)),
        )

    @classmethod
    def extract_jira_codes(cls, *texts: str | None) -> list[str]:
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
    def _file_extension(filename: str) -> str:
        """Return the file extension (with dot), or the bare basename if there is none.

        Falls back to the full basename so extensionless files like
        `Dockerfile`, `Makefile`, or `.gitignore` get a meaningful key
        instead of all collapsing into a single `""` bucket in the
        additions/deletions dict.
        """
        path = PurePosixPath(filename)
        return path.suffix or path.name
