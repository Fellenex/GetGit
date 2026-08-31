"""GitHub provider: turns client response objects into internal domain objects."""

import re
from datetime import datetime
from pathlib import PurePosixPath

import httpx

from ..clients import GithubClient, RateLimitExceededError, RepositoryAccessError
from ..data import (
    Comment,
    Commit,
    CommitPayload,
    GithubScrapeResult,
    PullRequest,
    RepoSummary,
    Review,
)


class GithubProvider:
    """Unravels GitHub wire-shape response objects into internal domain objects.

    Consumes the typed response objects from `GithubClient` and emits the
    domain `Commit`, `PullRequest`, and `Review` objects. Holds every
    raw→domain business rule that used to be spread across the three
    per-resource providers — JIRA-code extraction, the extension
    breakdown, the self-vs-stranger repo scope, comment counting, the
    commit→PR index, the `merged`/comment-sum derivations — but knows *no*
    route strings or pagination; those live only in the client.

    Also owns the partial-result / per-resource error contract:
    - a rate-limit `RateLimitExceededError` re-raises with whatever was
      collected attached to `.partial`, so the orchestrator can still
      write a partial report;
    - a per-repo 403/404/409 while walking commits is skipped so one
      inaccessible repo never derails the run;
    - a `--repo`-scoped 422 from search becomes `RepositoryAccessError`.
    """

    _JIRA_RE = re.compile(r"\b[A-Z]{2,10}-\d+\b")
    """Matches JIRA-style ticket codes (e.g. WD-6000, YWFB-300, PTR-8000)."""

    def __init__(self, client: GithubClient):
        """Bind to a `GithubClient` for all subsequent calls."""
        self._client = client

    def list_repos(self, username: str, is_self: bool) -> list[RepoSummary]:
        """List repos `username` has access to; self-vs-stranger is the only branch.

        `is_self=True` covers owned + collaborator + org-member repos
        (public + private the PAT can see); `is_self=False` covers the
        user's public repos only — the client method encapsulates which
        route each uses. On rate limit, attaches the partial list already
        collected to the raised `RateLimitExceededError`.
        """
        repos: list[RepoSummary] = []
        try:
            repos.extend(
                self._client.list_own_repos()
                if is_self
                else self._client.list_user_repos(username)
            )
            return repos
        except RateLimitExceededError as e:
            e.partial = repos
            raise

    def fetch_pull_requests(
        self,
        username: str,
        limit: int | None = None,
        fetch_extensions: bool = True,
        since: datetime | None = None,
        target_repo: str | None = None,
    ) -> GithubScrapeResult:
        """Collect every closed PR the user authored or participated in.

        "Authored" comes from `author:USER`; "participated" is the union
        of `commenter:USER` and `reviewed-by:USER` minus authored. Per PR
        we fetch detail, file-level additions/deletions (unless
        `fetch_extensions=False`), the user's reviews, both comment
        streams for the user's comment count, and the PR's commit list
        for the `commit_pr_index`.

        `since` constrains every search with `updated:>=<since>` so
        resumed runs skip unchanged PRs. `target_repo` (e.g.
        `"octocat/hello-world"`) constrains every search with
        `repo:OWNER/NAME`. `limit` caps each set independently. On rate
        limit, attaches the partially-built `GithubScrapeResult` to
        the raised `RateLimitExceededError`. When `target_repo` is set and
        the scoped search returns 422 (repo missing or invisible to the
        token), raises `RepositoryAccessError` instead of leaking the raw
        `HTTPStatusError`.
        """
        out = GithubScrapeResult()
        try:
            authored_keys: set[tuple[str, int]] = set()
            for hit in self._client.search_issues(
                self._build_query(f"author:{username}", since, target_repo)
            ):
                if limit is not None and len(out.authored) >= limit:
                    break
                authored_keys.add((hit.repo_full_name, hit.number))
                pr_obj, reviews = self._hydrate_pr(
                    hit.repo_full_name, hit.number, username, fetch_extensions
                )
                out.authored.append(pr_obj)
                out.reviews.extend(reviews)
                self._index_pr_commits(hit.repo_full_name, hit.number, out.commit_pr_index)

            participated_keys = (
                self._search_keys(
                    self._build_query(f"commenter:{username}", since, target_repo)
                )
                | self._search_keys(
                    self._build_query(f"reviewed-by:{username}", since, target_repo)
                )
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
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422 and target_repo is not None:
                raise RepositoryAccessError(target_repo) from e
            raise

    def fetch_commits(
        self,
        repos: list[RepoSummary],
        username: str,
        limit: int | None = None,
        pr_index: dict[tuple[str, str], int] | None = None,
        since_per_repo: dict[str, datetime] | None = None,
    ) -> list[Commit]:
        """Collect commits authored by `username` across `repos`.

        Per-repo failures are skipped so one bad repo never derails the
        walk: empty repos return 409, deleted or now-private repos return
        404, and repos the PAT can't access (e.g. an org repo behind SAML
        SSO) return 403. A rate-limit 403 is distinct — the client raises
        `RateLimitExceededError`, which aborts the walk.

        `since_per_repo` maps `owner/name` → datetime; when present for a
        repo, only commits authored on/after it are collected. `limit`
        caps the number of commits. `pr_index` (built by
        `fetch_pull_requests`) maps `(repo, sha)` → PR number; commits not
        in the index keep `pull_request_number=None`. On rate limit,
        attaches the partial commit list already collected to the raised
        `RateLimitExceededError`.
        """
        pr_index = pr_index or {}
        since_per_repo = since_per_repo or {}
        commits: list[Commit] = []
        try:
            for repo in repos:
                if limit is not None and len(commits) >= limit:
                    break
                full_name = repo.full_name
                try:
                    payloads = self._client.list_repo_commits(
                        full_name,
                        author=username,
                        since=since_per_repo.get(full_name),
                    )
                except httpx.HTTPStatusError as e:
                    # Per-repo conditions — skip this repo, keep walking:
                    #   404 = deleted or now-private, 409 = empty repo,
                    #   403 = access denied for this repo (e.g. an org repo
                    #   behind SAML SSO the PAT isn't authorized for). A
                    #   genuine rate-limit 403 never reaches here — the client
                    #   raises RateLimitExceededError for those and aborts.
                    if e.response.status_code in (403, 404, 409):
                        continue
                    raise
                for payload in payloads:
                    commits.append(self._build_commit(payload, full_name, pr_index))
                    if limit is not None and len(commits) >= limit:
                        break
            return commits
        except RateLimitExceededError as e:
            e.partial = commits
            raise

    @staticmethod
    def _build_query(
        scope: str, since: datetime | None, target_repo: str | None
    ) -> str:
        """Compose a /search/issues `q=` value with optional `updated:>=` and `repo:` filters."""
        parts = ["type:pr", scope, "is:closed"]
        if since is not None:
            parts.append(f"updated:>={since.isoformat()}")
        if target_repo is not None:
            parts.append(f"repo:{target_repo}")
        return " ".join(parts)

    def _search_keys(self, query: str) -> set[tuple[str, int]]:
        """Run a search and collect `(repo, number)` tuples from the hits."""
        return {
            (hit.repo_full_name, hit.number)
            for hit in self._client.search_issues(query)
        }

    def _hydrate_pr(
        self, repo_full: str, number: int, username: str, fetch_extensions: bool
    ) -> tuple[PullRequest, list[Review]]:
        """Fetch all per-PR data and assemble a `PullRequest` plus the user's reviews on it."""
        detail = self._client.get_pull_request(repo_full, number)

        if fetch_extensions:
            additions, deletions = self._ext_breakdown(repo_full, number)
        else:
            additions = {"*": detail.additions} if detail.additions else {}
            deletions = {"*": detail.deletions} if detail.deletions else {}

        comments_by_user = self._count_user_comments(
            self._client.list_issue_comments(repo_full, number), username
        ) + self._count_user_comments(
            self._client.list_review_comments(repo_full, number), username
        )

        reviews = self._fetch_user_reviews(repo_full, number, username)

        pr_obj = PullRequest(
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
            comments_by_author=comments_by_user,
            jira_codes=self._extract_jira_codes(detail.title, detail.body),
        )
        return pr_obj, reviews

    def _ext_breakdown(
        self, repo_full: str, number: int
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Aggregate `additions`/`deletions` from a PR's files keyed by extension.

        Zero-valued entries are omitted: a `.unity` file with 3 deletions
        and 0 additions appears in `deletions` only, not in `additions`.
        Keeps the two dicts asymmetric and lossless — consumers iterate
        only over real edits.
        """
        additions: dict[str, int] = {}
        deletions: dict[str, int] = {}
        for f in self._client.list_pull_request_files(repo_full, number):
            ext = self._file_extension(f.filename)
            if f.additions:
                additions[ext] = additions.get(ext, 0) + f.additions
            if f.deletions:
                deletions[ext] = deletions.get(ext, 0) + f.deletions
        return additions, deletions

    @staticmethod
    def _count_user_comments(comments: list[Comment], username: str) -> int:
        """Count comments authored by `username` in a comment stream."""
        return sum(1 for c in comments if c.author_login == username)

    def _fetch_user_reviews(
        self, repo_full: str, number: int, username: str
    ) -> list[Review]:
        """Return reviews on a PR submitted by `username`, with 1-based per-PR index."""
        reviews: list[Review] = []
        idx = 0
        for r in self._client.list_pull_request_reviews(repo_full, number):
            if r.author_login != username:
                continue
            idx += 1
            reviews.append(
                Review(
                    pr_repo=repo_full,
                    pr_number=number,
                    index=idx,
                    state=r.state,
                    submitted_at=r.submitted_at,
                    body=r.body,
                )
            )
        return reviews

    def _index_pr_commits(
        self, repo_full: str, number: int, index: dict[tuple[str, str], int]
    ) -> None:
        """Walk a PR's commit SHAs and insert each `(repo, sha)` → number into `index`."""
        for sha in self._client.list_pull_request_commits(repo_full, number):
            index[(repo_full, sha)] = number

    @staticmethod
    def _build_commit(
        payload: CommitPayload, full_name: str, pr_index: dict[tuple[str, str], int]
    ) -> Commit:
        """Materialize a `Commit` from a `CommitPayload`, linking its PR number if indexed."""
        return Commit(
            sha=payload.sha,
            repo=full_name,
            authored_at=payload.authored_at,
            message=payload.message,
            pull_request_number=pr_index.get((full_name, payload.sha)),
        )

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
    def _file_extension(filename: str) -> str:
        """Return the file extension (with dot), or the bare basename if there is none.

        Falls back to the full basename so extensionless files like
        `Dockerfile`, `Makefile`, or `.gitignore` get a meaningful key
        instead of all collapsing into a single `""` bucket in the
        additions/deletions dict.
        """
        path = PurePosixPath(filename)
        return path.suffix or path.name
