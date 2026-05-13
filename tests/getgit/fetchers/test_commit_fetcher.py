"""Tests for CommitFetcher."""

import httpx

from getgit.fetchers import CommitFetcher
from getgit.models import Commit


class _FakeClient:
    """Minimal stand-in for GithubClient.

    `pages` maps a URL to the list of items that endpoint should yield.
    Pages are not split — `paginate` returns everything for the URL in
    one go, which is what fetch_commits would see for a small repo.
    """

    def __init__(self, pages: dict[str, list[dict]]):
        self._pages = pages

    def paginate(self, url: str, params: dict | None = None):
        return iter(self._pages.get(url, []))


def _commit(sha: str) -> dict:
    """Build a GitHub-shaped commit payload."""
    return {
        "sha": sha,
        "commit": {
            "author": {"date": "2026-05-12T10:00:00Z"},
            "message": f"msg {sha}",
        },
    }


def test_fetch_walks_each_repo_and_returns_commits():
    """A commit per repo is returned with sha/message/repo populated."""
    client = _FakeClient({
        "/repos/o/r1/commits": [_commit("a")],
        "/repos/o/r2/commits": [_commit("b"), _commit("c")],
    })
    repos = [{"full_name": "o/r1"}, {"full_name": "o/r2"}]

    out = CommitFetcher(client).fetch(repos, "alice")

    assert [c.sha for c in out] == ["a", "b", "c"]
    assert all(isinstance(c, Commit) for c in out)
    assert out[0].repo == "o/r1"
    assert out[1].repo == "o/r2"


def test_fetch_attaches_pull_request_number_from_index():
    """Commits in the pr_index get their PR number; others stay None."""
    client = _FakeClient({"/repos/o/r/commits": [_commit("a"), _commit("b")]})
    pr_index = {("o/r", "a"): 42}

    out = CommitFetcher(client).fetch(
        [{"full_name": "o/r"}], "alice", pr_index=pr_index
    )

    assert out[0].pull_request_number == 42
    assert out[1].pull_request_number is None


def test_fetch_respects_limit():
    """`limit` should stop iteration once N commits have been collected."""
    client = _FakeClient({
        "/repos/o/r/commits": [_commit(s) for s in "abcde"],
    })

    out = CommitFetcher(client).fetch([{"full_name": "o/r"}], "alice", limit=2)

    assert [c.sha for c in out] == ["a", "b"]


class _ErroringClient:
    """Client that raises a 409 (empty repo) on the first paginate call."""

    def __init__(self, code: int):
        self._code = code

    def paginate(self, url: str, params: dict | None = None):
        resp = httpx.Response(self._code, request=httpx.Request("GET", url))
        raise httpx.HTTPStatusError("nope", request=resp.request, response=resp)


def test_fetch_skips_repos_that_return_409_or_404():
    """Empty/inaccessible repos are silently skipped."""
    fetcher = CommitFetcher(_ErroringClient(409))

    assert fetcher.fetch([{"full_name": "o/empty"}], "alice") == []
