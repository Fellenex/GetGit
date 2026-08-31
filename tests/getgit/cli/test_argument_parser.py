"""Tests for the CLI argument parser."""

from pathlib import Path

import pytest

from getgit.application import AppSettings, ScrapeSettings
from getgit.cli import ArgumentParser


def test_parses_minimal_args_into_settings_pair():
    """Only the username is required; everything else has defaults."""
    app_settings, scrape_settings = ArgumentParser().parse(["alice"])

    assert isinstance(app_settings, AppSettings)
    assert isinstance(scrape_settings, ScrapeSettings)
    assert scrape_settings.username == "alice"
    assert app_settings.out_dir == Path("output")
    assert scrape_settings.max_commits is None
    assert scrape_settings.max_prs is None
    assert scrape_settings.fetch_extensions is True


def test_no_extension_breakdown_inverts_into_fetch_extensions():
    """The CLI flag is `--no-extension-breakdown`; the setting is `fetch_extensions`."""
    _, scrape_settings = ArgumentParser().parse(["alice", "--no-extension-breakdown"])

    assert scrape_settings.fetch_extensions is False


def test_max_flags_propagate():
    """--max-commits and --max-prs should land on the ScrapeSettings as ints."""
    _, scrape_settings = ArgumentParser().parse(
        ["alice", "--max-commits", "5", "--max-prs", "7"]
    )

    assert scrape_settings.max_commits == 5
    assert scrape_settings.max_prs == 7


def test_out_dir_becomes_a_path():
    """--out should be coerced to a `Path`, not left as a raw string."""
    app_settings, _ = ArgumentParser().parse(["alice", "--out", "results"])

    assert app_settings.out_dir == Path("results")


def test_username_is_required():
    """Calling parse with no args should fail — username is positional and required."""
    with pytest.raises(SystemExit):
        ArgumentParser().parse([])


def test_access_token_read_from_env(monkeypatch):
    """`access_token` should be populated from the GITHUB_TOKEN env var."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_xyz")

    app_settings, _ = ArgumentParser().parse(["alice"])

    assert app_settings.access_token == "ghp_xyz"


def test_access_token_is_none_when_env_missing(monkeypatch):
    """Missing env var should produce `access_token=None`; validation happens later in run()."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    app_settings, _ = ArgumentParser().parse(["alice"])

    assert app_settings.access_token is None


def test_target_repo_defaults_to_none():
    """Without --repo, `target_repo` is None (full repo discovery)."""
    _, scrape_settings = ArgumentParser().parse(["alice"])

    assert scrape_settings.target_repo is None


def test_target_repo_populated_from_repo_flag():
    """`--repo OWNER/NAME` should land on `ScrapeSettings.target_repo`."""
    _, scrape_settings = ArgumentParser().parse(["alice", "--repo", "octocat/hello-world"])

    assert scrape_settings.target_repo == "octocat/hello-world"
