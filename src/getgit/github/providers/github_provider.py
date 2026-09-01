"""GitHub provider: orchestrates the fetch sequences and owns the error contract."""

from datetime import datetime

import httpx

from ..clients import GithubClient, RateLimitExceededError, RepositoryAccessError
from ..data import (
    Commit,
    GithubRepo,
    PullRequest,
    PullRequestFetchResult,
    Review,
)
from .github_mapper import GithubMapper


class GithubProvider:
    """Sequences the multi-call GitHub fetches and owns the partial/error contract.

    Drives the searches and per-PR / per-repo walks against a
    `GithubClient`, and delegates every raw→domain transform to
    `GithubMapper` (JIRA-code extraction, the extension breakdown,
    comment counting, the `merged`/comment-sum derivations, the query
    composition, commit/review assembly). It therefore knows *no* route
    strings or pagination (those live in the client) and holds *no*
    stateless mapping rules (those live in the mapper) — its own job is
    the orchestration between them.

    It also owns the partial-result / per-resource error contract:
    - a rate-limit `RateLimitExceededError` re-raises with whatever was
      collected attached to `.partial`, so the orchestrator can still
      write a partial report;
    - a per-repo 403/404/409 while walking commits is skipped so one
      inaccessible repo never derails the run;
    - a `--repo`-scoped 422 from search becomes `RepositoryAccessError`.
    """

    def __init__(self, client: GithubClient):
        """Bind to a `GithubClient` for all subsequent calls."""
        self._client = client

    def list_repos(self, username: str, is_self: bool) -> list[GithubRepo]:
        """List repos `username` has access to; self-vs-stranger is the only branch.

        `is_self=True` covers owned + collaborator + org-member repos
        (public + private the PAT can see); `is_self=False` covers the
        user's public repos only — the client method encapsulates which
        route each uses. On rate limit, attaches the partial list already
        collected to the raised `RateLimitExceededError`.
        """
        repos: list[GithubRepo] = []
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
    ) -> PullRequestFetchResult:
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
        limit, attaches the partially-built `PullRequestFetchResult` to
        the raised `RateLimitExceededError`. When `target_repo` is set and
        the scoped search returns 422 (repo missing or invisible to the
        token), raises `RepositoryAccessError` instead of leaking the raw
        `HTTPStatusError`.
        """
        out = PullRequestFetchResult()
        try:
            authored_keys: set[tuple[str, int]] = set()
            for hit in self._client.search_issues(
                GithubMapper.build_query(f"author:{username}", since, target_repo)
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
                    GithubMapper.build_query(f"commenter:{username}", since, target_repo)
                )
                | self._search_keys(
                    GithubMapper.build_query(f"reviewed-by:{username}", since, target_repo)
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
        repos: list[GithubRepo],
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
                    commits.append(
                        GithubMapper.build_commit(payload, full_name, pr_index)
                    )
                    if limit is not None and len(commits) >= limit:
                        break
            return commits
        except RateLimitExceededError as e:
            e.partial = commits
            raise

    def _search_keys(self, query: str) -> set[tuple[str, int]]:
        """Run a search and collect `(repo, number)` tuples from the hits."""
        return {
            (hit.repo_full_name, hit.number)
            for hit in self._client.search_issues(query)
        }

    def _hydrate_pr(
        self, repo_full: str, number: int, username: str, fetch_extensions: bool
    ) -> tuple[PullRequest, list[Review]]:
        """Fetch all per-PR data and assemble a `PullRequest` plus the user's reviews on it.

        Sequences the five per-PR client calls (detail, changed files,
        both comment streams, reviews) and hands the fetched values to
        `GithubMapper` for the actual raw→domain assembly. When
        `fetch_extensions=False` the changed-files call is skipped and the
        breakdown collapses to the `"*"` aggregate key.
        """
        detail = self._client.get_pull_request(repo_full, number)

        if fetch_extensions:
            additions, deletions = self._ext_breakdown(repo_full, number)
        else:
            additions = {"*": detail.additions} if detail.additions else {}
            deletions = {"*": detail.deletions} if detail.deletions else {}

        comments_by_user = GithubMapper.count_user_comments(
            self._client.list_issue_comments(repo_full, number), username
        ) + GithubMapper.count_user_comments(
            self._client.list_review_comments(repo_full, number), username
        )

        reviews = self._fetch_user_reviews(repo_full, number, username)

        pr_obj = GithubMapper.build_pull_request(
            detail, repo_full, number, additions, deletions, comments_by_user
        )
        return pr_obj, reviews

    def _ext_breakdown(
        self, repo_full: str, number: int
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Fetch a PR's changed files and hand them to the mapper's extension breakdown."""
        return GithubMapper.breakdown_from_files(
            self._client.list_pull_request_files(repo_full, number)
        )

    def _fetch_user_reviews(
        self, repo_full: str, number: int, username: str
    ) -> list[Review]:
        """Fetch a PR's reviews and keep the target user's, via the mapper."""
        return GithubMapper.user_reviews(
            self._client.list_pull_request_reviews(repo_full, number),
            repo_full,
            number,
            username,
        )

    def _index_pr_commits(
        self, repo_full: str, number: int, index: dict[tuple[str, str], int]
    ) -> None:
        """Walk a PR's commit SHAs and insert each `(repo, sha)` → number into `index`."""
        for sha in self._client.list_pull_request_commits(repo_full, number):
            index[(repo_full, sha)] = number
