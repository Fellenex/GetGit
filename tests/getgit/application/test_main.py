"""Tests for application.run — the UI-agnostic orchestration entry point."""

from pathlib import Path

import pytest

from getgit.application import AppSettings, run
from getgit.github import RepositoryAccessError


def _settings_without_token() -> AppSettings:
    """Build an `AppSettings` with no token — used to assert validation fires."""
    return AppSettings(
        username="alice",
        out_dir=Path("output"),
        max_commits=None,
        max_prs=None,
        fetch_extensions=True,
        access_token=None,
    )


def test_run_raises_when_access_token_missing():
    """Missing access token should fail fast before any HTTP work."""
    with pytest.raises(RuntimeError, match="access token"):
        run(_settings_without_token())


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


def test_run_reports_repository_access_error_with_exit_3(monkeypatch, tmp_path, capsys):
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

    settings = AppSettings(
        username="alice",
        out_dir=tmp_path,
        max_commits=None,
        max_prs=None,
        fetch_extensions=True,
        access_token="tok",
        target_repo="octocat/hello-world",
    )

    code = run(settings)

    assert code == 3
    err = capsys.readouterr().err
    assert "octocat/hello-world" in err
    assert not any(tmp_path.glob("alice/**/*.json"))
