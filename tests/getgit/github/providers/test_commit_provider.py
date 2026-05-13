"""Tests for CommitProvider."""

from unittest.mock import Mock

import httpx
import pytest

from _support.github import FakeGithubClient

from getgit.github import (
    Commit,
    CommitProvider,
    GithubClient,
    RateLimitExceededError,
)


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
    client = FakeGithubClient(pages={
        "/repos/o/r1/commits": [_commit("a")],
        "/repos/o/r2/commits": [_commit("b"), _commit("c")],
    })
    repos = [{"full_name": "o/r1"}, {"full_name": "o/r2"}]

    out = CommitProvider(client).fetch(repos, "alice")

    assert [c.sha for c in out] == ["a", "b", "c"]
    assert all(isinstance(c, Commit) for c in out)
    assert out[0].repo == "o/r1"
    assert out[1].repo == "o/r2"


def test_fetch_attaches_pull_request_number_from_index():
    """Commits in the pr_index get their PR number; others stay None."""
    client = FakeGithubClient(pages={"/repos/o/r/commits": [_commit("a"), _commit("b")]})
    pr_index = {("o/r", "a"): 42}

    out = CommitProvider(client).fetch(
        [{"full_name": "o/r"}], "alice", pr_index=pr_index
    )

    assert out[0].pull_request_number == 42
    assert out[1].pull_request_number is None


def test_fetch_respects_limit():
    """`limit` should stop iteration once N commits have been collected."""
    client = FakeGithubClient(pages={
        "/repos/o/r/commits": [_commit(s) for s in "abcde"],
    })

    out = CommitProvider(client).fetch([{"full_name": "o/r"}], "alice", limit=2)

    assert [c.sha for c in out] == ["a", "b"]


def test_fetch_skips_repos_that_return_409_or_404():
    """Empty/inaccessible repos are silently skipped."""
    request = httpx.Request("GET", "/repos/o/empty/commits")
    client = Mock(spec=GithubClient)
    client.paginate.side_effect = httpx.HTTPStatusError(
        "fake", request=request, response=httpx.Response(409, request=request)
    )

    assert CommitProvider(client).fetch([{"full_name": "o/empty"}], "alice") == []


def test_rate_limit_attaches_partial_commits_to_exception():
    """If we collect from one repo then 403 on the next, the partial commits ride on the exception."""
    def per_url(url, _params=None):
        if url == "/repos/o/r1/commits":
            return iter([_commit("a"), _commit("b")])
        raise RateLimitExceededError("too many")

    client = Mock(spec=GithubClient)
    client.paginate.side_effect = per_url

    repos = [{"full_name": "o/r1"}, {"full_name": "o/r2"}]

    with pytest.raises(RateLimitExceededError) as excinfo:
        CommitProvider(client).fetch(repos, "alice")

    assert isinstance(excinfo.value.partial, list)
    assert [c.sha for c in excinfo.value.partial] == ["a", "b"]
