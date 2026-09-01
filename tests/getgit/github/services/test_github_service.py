"""Tests for GithubService — verifies it threads ScrapeSettings into GithubProvider."""

from unittest.mock import Mock, patch

from getgit.application import ScrapeSettings
from getgit.github import (
    GithubClient,
    GithubProvider,
    GithubRepo,
    GithubService,
    PullRequestFetchResult,
)


def _settings(**overrides) -> ScrapeSettings:
    """Build a `ScrapeSettings` with reasonable defaults for service tests."""
    base = dict(
        username="alice",
        max_commits=None,
        max_prs=None,
        fetch_extensions=True,
    )
    base.update(overrides)
    return ScrapeSettings(**base)


def _make_service(**setting_overrides):
    """Build a service backed by a Mock provider; return service + the mock."""
    provider = Mock(spec=GithubProvider)
    provider.list_repos.return_value = [GithubRepo("o/r")]
    provider.fetch_pull_requests.return_value = PullRequestFetchResult()
    provider.fetch_commits.return_value = []

    service = GithubService(provider=provider, settings=_settings(**setting_overrides))
    return service, provider


def test_build_wires_provider_to_the_client():
    """build() constructs a GithubProvider from the client and returns a ready service."""
    client = Mock(spec=GithubClient)
    module = "getgit.github.services.github_service"

    with patch(f"{module}.GithubProvider") as provider_cls:
        service = GithubService.build(client, _settings(username="bob"))

    provider_cls.assert_called_once_with(client)
    assert isinstance(service, GithubService)

    service.fetch_repositories(is_self=True)
    provider_cls.return_value.list_repos.assert_called_once_with("bob", is_self=True)


def test_fetch_repositories_passes_username_and_is_self():
    """Username comes from settings; is_self is the explicit caller arg."""
    service, provider = _make_service(username="bob")

    service.fetch_repositories(is_self=True)

    provider.list_repos.assert_called_once_with("bob", is_self=True)


def test_fetch_pull_requests_threads_settings_through():
    """max_prs and fetch_extensions should be propagated from ScrapeSettings."""
    service, provider = _make_service(max_prs=10, fetch_extensions=False)

    service.fetch_pull_requests()

    provider.fetch_pull_requests.assert_called_once_with(
        "alice", limit=10, fetch_extensions=False, since=None, target_repo=None
    )


def test_fetch_pull_requests_propagates_target_repo_from_settings():
    """settings.target_repo should be forwarded to the provider as target_repo."""
    service, provider = _make_service(target_repo="octocat/hello-world")

    service.fetch_pull_requests()

    assert provider.fetch_pull_requests.call_args.kwargs["target_repo"] == "octocat/hello-world"


def test_fetch_commits_passes_repos_and_pr_index():
    """fetch_commits is the only method whose data comes from prior calls."""
    service, provider = _make_service(max_commits=5)
    repos = [GithubRepo("o/r")]
    pr_index = {("o/r", "abc"): 42}

    service.fetch_commits(repos=repos, pr_index=pr_index)

    provider.fetch_commits.assert_called_once_with(
        repos, "alice", limit=5, pr_index=pr_index, since_per_repo=None
    )
