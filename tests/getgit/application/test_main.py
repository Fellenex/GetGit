"""Tests for application.run — the UI-agnostic orchestration entry point."""

from pathlib import Path

import pytest

from getgit.application import AppSettings, run


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
