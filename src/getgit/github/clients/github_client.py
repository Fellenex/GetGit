"""Authenticated GitHub REST client with pagination support."""

from datetime import datetime
from typing import Iterator

import httpx

from ...infrastructure.dates import IsoDateParser
from ..data import (
    CommentsResponse,
    CommitsResponse,
    IssueSearchResponse,
    PullRequestFilesResponse,
    PullRequestResponse,
    PullRequestReviewsResponse,
    ReposResponse,
)
from .github_settings import GithubSettings
from .rate_limit_exceeded_error import RateLimitExceededError


class GithubClient:
    """GitHub REST client with auth, pagination, and viewer-identity helpers.

    Built from a `GithubSettings` so the constructor encapsulates the
    auth-header wiring. Acts as a context manager — opens its
    underlying `httpx.Client` on `__enter__` and closes it on
    `__exit__`. Once a *rate-limit* 403 is observed (identified by its
    `Retry-After` / `X-RateLimit-Remaining` headers), the client locks
    itself: every subsequent call raises `RateLimitExceededError`
    without hitting the network. A non-rate-limit 403 (e.g. a per-repo
    access denial) is not a lock — it surfaces as a normal
    `httpx.HTTPStatusError` for the caller to handle.
    """

    def __init__(self, settings: GithubSettings):
        """Build the underlying `httpx.Client` from `settings`."""
        self._http = httpx.Client(
            base_url=settings.base_url,
            headers={
                "Authorization": f"Bearer {settings.auth_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "GetGit/0.1",
            },
            timeout=settings.timeout,
        )
        self._rate_limited = False

    def __enter__(self) -> "GithubClient":
        """Enter the underlying HTTP client's context."""
        self._http.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the underlying HTTP client."""
        self._http.__exit__(*exc)

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        """Perform a single GET. Raises `RateLimitExceededError` on 403."""
        self._guard_rate_limit()
        response = self._http.get(url, params=params)
        self._check_rate_limit(response)
        return response

    def paginate(self, url: str, params: dict | None = None) -> Iterator[dict]:
        """Yield every item across all pages of a GitHub REST endpoint.

        Follows the `Link: ...; rel="next"` header — works for both list
        endpoints (which return arrays) and search endpoints (which wrap
        results under `"items"`). Query params are sent on the first
        request only; the `next` URL already contains them. Aborts (and
        locks the client) on the first 403.
        """
        merged_params = dict(params or {})
        merged_params.setdefault("per_page", 100)
        next_url: str | None = url
        next_params: dict | None = merged_params
        while next_url:
            self._guard_rate_limit()
            resp = self._http.get(next_url, params=next_params)
            self._check_rate_limit(resp)
            resp.raise_for_status()
            data = resp.json()
            items = data["items"] if isinstance(data, dict) and "items" in data else data
            for item in items:
                yield item
            next_url = resp.links.get("next", {}).get("url")
            next_params = None

    def viewer_login(self) -> str:
        """Return the login of the user whose token is being used."""
        resp = self.get("/user")
        resp.raise_for_status()
        return resp.json()["login"]

    def list_own_repos(self) -> list[ReposResponse]:
        """List repos the token's user owns, collaborates on, or is an org member of.

        Hits `/user/repos` with
        `affiliation=owner,collaborator,organization_member&visibility=all`
        so org-owned and collaborator repos are discovered (not just
        owned ones) — the self-scrape scope.
        """
        return [
            ReposResponse(full_name=raw["full_name"])
            for raw in self.paginate(
                "/user/repos",
                {
                    "affiliation": "owner,collaborator,organization_member",
                    "visibility": "all",
                },
            )
        ]

    def list_user_repos(self, username: str) -> list[ReposResponse]:
        """List the public repos owned by `username` (the stranger-scrape scope)."""
        return [
            ReposResponse(full_name=raw["full_name"])
            for raw in self.paginate(f"/users/{username}/repos")
        ]

    def search_issues(self, query: str) -> list[IssueSearchResponse]:
        """Run a `/search/issues` query, returning each hit's repo slug + number.

        The search envelope (`items`) and the `repository_url` →
        `owner/name` conversion are handled here so no route or wire-shape
        knowledge escapes the client.
        """
        return [
            IssueSearchResponse(
                repo_full_name=self._key_from_repo_url(issue["repository_url"]),
                number=issue["number"],
            )
            for issue in self.paginate("/search/issues", {"q": query})
        ]

    def list_repo_commits(
        self, full_name: str, *, author: str, since: datetime | None = None
    ) -> list[CommitsResponse]:
        """List commits in `full_name` authored by `author`, optionally `since` a time.

        Uses `/repos/{full_name}/commits?author=...`, avoiding the
        `/search/commits` rate cap. `since` adds GitHub's `since=` filter
        so resumed runs skip already-collected commits.
        """
        params: dict[str, str] = {"author": author}
        if since is not None:
            params["since"] = since.isoformat()
        return [
            CommitsResponse(
                sha=raw["sha"],
                authored_at=IsoDateParser.parse(raw["commit"]["author"]["date"]),
                message=raw["commit"]["message"],
            )
            for raw in self.paginate(f"/repos/{full_name}/commits", params)
        ]

    def get_pull_request(self, repo: str, number: int) -> PullRequestResponse:
        """Fetch one PR's detail from `/repos/{repo}/pulls/{number}`."""
        resp = self.get(f"/repos/{repo}/pulls/{number}")
        resp.raise_for_status()
        pr = resp.json()
        return PullRequestResponse(
            title=pr["title"],
            body=pr.get("body"),
            merged_at=IsoDateParser.parse(pr.get("merged_at")),
            created_at=IsoDateParser.parse(pr["created_at"]),
            closed_at=IsoDateParser.parse(pr.get("closed_at")),
            updated_at=IsoDateParser.parse(pr["updated_at"]),
            additions=pr.get("additions", 0),
            deletions=pr.get("deletions", 0),
            comments=pr.get("comments", 0),
            review_comments=pr.get("review_comments", 0),
        )

    def list_pull_request_files(
        self, repo: str, number: int
    ) -> list[PullRequestFilesResponse]:
        """List a PR's changed files from `/repos/{repo}/pulls/{number}/files`."""
        return [
            PullRequestFilesResponse(
                filename=raw["filename"],
                additions=raw.get("additions", 0),
                deletions=raw.get("deletions", 0),
            )
            for raw in self.paginate(f"/repos/{repo}/pulls/{number}/files")
        ]

    def list_pull_request_reviews(
        self, repo: str, number: int
    ) -> list[PullRequestReviewsResponse]:
        """List a PR's reviews from `/repos/{repo}/pulls/{number}/reviews`."""
        return [
            PullRequestReviewsResponse(
                author_login=(raw.get("user") or {}).get("login"),
                state=raw.get("state", ""),
                submitted_at=IsoDateParser.parse(raw.get("submitted_at")),
                body=raw.get("body") or "",
            )
            for raw in self.paginate(f"/repos/{repo}/pulls/{number}/reviews")
        ]

    def list_pull_request_commits(self, repo: str, number: int) -> list[str]:
        """List the commit SHAs on a PR from `/repos/{repo}/pulls/{number}/commits`."""
        return [
            raw["sha"]
            for raw in self.paginate(f"/repos/{repo}/pulls/{number}/commits")
        ]

    def list_issue_comments(self, repo: str, number: int) -> list[CommentsResponse]:
        """List a PR's issue-comment stream from `/repos/{repo}/issues/{number}/comments`."""
        return self._list_comments(f"/repos/{repo}/issues/{number}/comments")

    def list_review_comments(self, repo: str, number: int) -> list[CommentsResponse]:
        """List a PR's review-comment stream from `/repos/{repo}/pulls/{number}/comments`."""
        return self._list_comments(f"/repos/{repo}/pulls/{number}/comments")

    def _list_comments(self, url: str) -> list[CommentsResponse]:
        """Paginate a comments endpoint into `CommentsResponse` response objects."""
        return [
            CommentsResponse(author_login=(raw.get("user") or {}).get("login"))
            for raw in self.paginate(url)
        ]

    @staticmethod
    def _key_from_repo_url(repo_url: str) -> str:
        """Convert `https://api.github.com/repos/owner/repo` → `owner/repo`."""
        return "/".join(repo_url.rsplit("/", 2)[-2:])

    def _guard_rate_limit(self) -> None:
        """Refuse to make a network call once a 403 has been seen."""
        if self._rate_limited:
            raise RateLimitExceededError(
                "Refusing further requests: a previous call returned 403."
            )

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """Lock the client and raise if `response` is a *rate-limit* 403.

        GitHub reuses 403 for several conditions. Only a genuine rate
        limit should lock the client and abort the whole scrape; a
        per-resource access 403 (e.g. an org repo behind SAML SSO the
        PAT isn't authorized for) must stay a local failure the caller
        can skip. We classify by reliable headers, never the response
        body (which varies across endpoint families):

        - a `Retry-After` header → secondary (abuse) rate limit.
        - `X-RateLimit-Remaining: 0` → primary rate limit.

        A 403 matching neither is left alone: the caller's
        `raise_for_status()` surfaces it as a normal
        `httpx.HTTPStatusError` for per-resource handling.
        """
        if response.status_code == 403 and self._is_rate_limit_403(response):
            self._rate_limited = True
            raise RateLimitExceededError(self._extract_message(response))

    @staticmethod
    def _is_rate_limit_403(response: httpx.Response) -> bool:
        """True when a 403 carries GitHub's rate-limit headers (primary or secondary)."""
        if response.headers.get("Retry-After") is not None:
            return True
        return response.headers.get("X-RateLimit-Remaining") == "0"

    @staticmethod
    def _extract_message(response: httpx.Response) -> str:
        """Build a human-readable message from a 403 response body."""
        try:
            body = response.json()
            msg = body.get("message", "").strip()
            if msg:
                return f"GitHub returned 403: {msg}"
        except (ValueError, AttributeError):
            pass
        return "GitHub returned 403"
