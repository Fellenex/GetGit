"""Tests for GithubService — verifies it threads AppSettings into each provider."""

from pathlib import Path

from _support.github import (
    RecordingCommitProvider,
    RecordingPullRequestProvider,
    RecordingRepoProvider,
)

from getgit.application import AppSettings
from getgit.github import GithubService


def _settings(**overrides) -> AppSettings:
    """Build an `AppSettings` with reasonable defaults for service tests."""
    base = dict(
        username="alice",
        out_dir=Path("output"),
        max_commits=None,
        max_prs=None,
        fetch_extensions=True,
        access_token="t",
    )
    base.update(overrides)
    return AppSettings(**base)


def _make_service(**setting_overrides):
    repo, prs, commits = (
        RecordingRepoProvider(),
        RecordingPullRequestProvider(),
        RecordingCommitProvider(),
    )
    service = GithubService(
        repo_provider=repo,
        pull_request_provider=prs,
        commit_provider=commits,
        settings=_settings(**setting_overrides),
    )
    return service, repo, prs, commits


def test_fetch_repositories_passes_username_and_is_self():
    """Username comes from settings; is_self is the explicit caller arg."""
    service, repo, _, _ = _make_service(username="bob")

    service.fetch_repositories(is_self=True)

    assert repo.last_call == {"username": "bob", "is_self": True}


def test_fetch_pull_requests_threads_settings_through():
    """max_prs and fetch_extensions should be propagated from AppSettings."""
    service, _, prs, _ = _make_service(max_prs=10, fetch_extensions=False)

    service.fetch_pull_requests()

    assert prs.last_call == {
        "username": "alice",
        "limit": 10,
        "fetch_extensions": False,
    }


def test_fetch_commits_passes_repos_and_pr_index():
    """fetch_commits is the only method whose data comes from prior calls."""
    service, _, _, commits = _make_service(max_commits=5)
    repos = [{"full_name": "o/r"}]
    pr_index = {("o/r", "abc"): 42}

    service.fetch_commits(repos=repos, pr_index=pr_index)

    assert commits.last_call == {
        "repos": repos,
        "username": "alice",
        "limit": 5,
        "pr_index": pr_index,
    }
