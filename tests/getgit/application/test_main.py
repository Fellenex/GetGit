"""Tests for application.run — the UI-agnostic orchestration entry point."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from getgit.application import AppSettings, ExitCode, ScrapeSettings, run
from getgit.github import (
    Commit,
    PullRequestFetchResult,
    RateLimitExceededError,
    RepositoryAccessError,
)


def _scrape_settings(**overrides) -> ScrapeSettings:
    """Build a `ScrapeSettings` with reasonable defaults for run() tests."""
    base = dict(
        username="alice",
        max_commits=None,
        max_prs=None,
        fetch_extensions=True,
    )
    base.update(overrides)
    return ScrapeSettings(**base)


def test_run_raises_when_access_token_missing():
    """Missing access token should fail fast before any HTTP work."""
    app_settings = AppSettings(out_dir=Path("output"), access_token=None)
    with pytest.raises(RuntimeError, match="access token"):
        run(app_settings, _scrape_settings())


class _FakeClient:
    """Minimal `GithubClient` stand-in: a no-op context manager with a viewer."""

    def __init__(self, *args, **kwargs):
        """Ignore the `GithubSettings` the orchestrator passes in."""

    def __enter__(self) -> "_FakeClient":
        """Enter as itself — no real HTTP session to open."""
        return self

    def __exit__(self, *exc: object) -> bool:
        """Never suppress exceptions."""
        return False

    def viewer_login(self) -> str:
        """Return a fixed viewer login so `run` can compute `is_self`."""
        return "viewer"


def test_run_reports_repository_access_error_with_exit_3(monkeypatch, tmp_path, caplog):
    """A `RepositoryAccessError` should exit 3 with a clean message and no report."""

    class _FakeService:
        """`GithubService` stand-in whose scoped PR search rejects the repo."""

        def __init__(self, *args, **kwargs):
            """Ignore the wired-in providers and settings."""

        @classmethod
        def build(cls, client, settings):
            """Match `GithubService.build`, ignoring the client and settings."""
            return cls()

        def fetch_pull_requests(self, since=None):
            """Simulate the 422-scoped-search failure."""
            raise RepositoryAccessError("octocat/hello-world")

    monkeypatch.setattr("getgit.application.main.GithubClient", _FakeClient)
    monkeypatch.setattr("getgit.application.main.GithubService", _FakeService)

    app_settings = AppSettings(out_dir=tmp_path, access_token="tok")
    scrape_settings = _scrape_settings(target_repo="octocat/hello-world")

    code = run(app_settings, scrape_settings)

    assert code is ExitCode.REPOSITORY_ACCESS_ERROR
    assert "octocat/hello-world" in caplog.text
    assert not any(tmp_path.glob("alice/**/*.json"))


def test_run_rate_limit_in_pr_phase_saves_partial_and_skips_commits(monkeypatch, tmp_path):
    """A rate limit while fetching PRs exits 2, writes a partial report, and skips the commit walk."""
    partial_prs = PullRequestFetchResult()

    class _FakeService:
        """`GithubService` stand-in that rate-limits during the PR phase."""

        def __init__(self, *args, **kwargs):
            """Ignore the wired-in providers and settings."""

        @classmethod
        def build(cls, client, settings):
            """Match `GithubService.build`, ignoring the client and settings."""
            return cls()

        def fetch_repositories(self, *, is_self):
            """No repos needed for this path."""
            return []

        def fetch_pull_requests(self, since=None):
            """Rate-limit mid-PR-phase, attaching what was collected so far."""
            raise RateLimitExceededError("too many", partial=partial_prs)

        def fetch_commits(self, **kwargs):
            """The commit phase must never run once a partial is in hand."""
            raise AssertionError("commit phase must be skipped after a partial")

    monkeypatch.setattr("getgit.application.main.GithubClient", _FakeClient)
    monkeypatch.setattr("getgit.application.main.GithubService", _FakeService)

    code = run(AppSettings(out_dir=tmp_path, access_token="tok"), _scrape_settings())

    assert code is ExitCode.PARTIAL
    assert any(tmp_path.glob("alice/**/commits.json"))


def test_run_rate_limit_in_commit_phase_saves_collected_commits(monkeypatch, tmp_path):
    """A rate limit while walking commits exits 2 and writes the commits collected so far."""
    partial_commits = [
        Commit(
            sha="a",
            repo="o/r",
            authored_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            message="m",
        )
    ]

    class _FakeService:
        """`GithubService` stand-in that rate-limits during the commit phase."""

        def __init__(self, *args, **kwargs):
            """Ignore the wired-in providers and settings."""

        @classmethod
        def build(cls, client, settings):
            """Match `GithubService.build`, ignoring the client and settings."""
            return cls()

        def fetch_repositories(self, *, is_self):
            """One repo to walk."""
            return []

        def fetch_pull_requests(self, since=None):
            """PR phase succeeds with nothing to report."""
            return PullRequestFetchResult()

        def fetch_commits(self, **kwargs):
            """Rate-limit mid-commit-walk, attaching the commits collected so far."""
            raise RateLimitExceededError("too many", partial=partial_commits)

    monkeypatch.setattr("getgit.application.main.GithubClient", _FakeClient)
    monkeypatch.setattr("getgit.application.main.GithubService", _FakeService)

    code = run(AppSettings(out_dir=tmp_path, access_token="tok"), _scrape_settings())

    assert code is ExitCode.PARTIAL
    written = list(tmp_path.glob("alice/**/commits.json"))
    assert written
    assert '"a"' in written[0].read_text(encoding="utf-8")
