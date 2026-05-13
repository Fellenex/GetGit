"""Tests for GithubService — verifies it threads AppSettings into each provider."""

from pathlib import Path

from getgit.application import AppSettings
from getgit.github import PullRequestFetchResult
from getgit.services import GithubService


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


class _RecordingRepoProvider:
    """Records the args of the last `list_repos` call."""

    def __init__(self):
        self.last_call: dict | None = None

    def list_repos(self, username: str, is_self: bool) -> list[dict]:
        self.last_call = {"username": username, "is_self": is_self}
        return [{"full_name": "o/r"}]


class _RecordingPullRequestProvider:
    def __init__(self):
        self.last_call: dict | None = None

    def fetch(self, username, limit, fetch_extensions):
        self.last_call = {
            "username": username,
            "limit": limit,
            "fetch_extensions": fetch_extensions,
        }
        return PullRequestFetchResult()


class _RecordingCommitProvider:
    def __init__(self):
        self.last_call: dict | None = None

    def fetch(self, repos, username, limit, pr_index):
        self.last_call = {
            "repos": repos,
            "username": username,
            "limit": limit,
            "pr_index": pr_index,
        }
        return []


def _make_service(**setting_overrides):
    repo, prs, commits = (
        _RecordingRepoProvider(),
        _RecordingPullRequestProvider(),
        _RecordingCommitProvider(),
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
