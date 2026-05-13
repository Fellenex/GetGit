"""Tests for the CLI argument parser."""

from pathlib import Path

import pytest

from getgit.cli import ArgumentParser, AppSettings


def test_parses_minimal_args_into_app_settings():
    """Only the username is required; everything else has defaults."""
    settings = ArgumentParser().parse(["alice"])

    assert isinstance(settings, AppSettings)
    assert settings.username == "alice"
    assert settings.out_dir == Path("output")
    assert settings.max_commits is None
    assert settings.max_prs is None
    assert settings.fetch_extensions is True


def test_no_extension_breakdown_inverts_into_fetch_extensions():
    """The CLI flag is `--no-extension-breakdown`; the setting is `fetch_extensions`."""
    settings = ArgumentParser().parse(["alice", "--no-extension-breakdown"])

    assert settings.fetch_extensions is False


def test_max_flags_propagate():
    """--max-commits and --max-prs should land on the AppSettings as ints."""
    settings = ArgumentParser().parse(
        ["alice", "--max-commits", "5", "--max-prs", "7"]
    )

    assert settings.max_commits == 5
    assert settings.max_prs == 7


def test_out_dir_becomes_a_path():
    """--out should be coerced to a `Path`, not left as a raw string."""
    settings = ArgumentParser().parse(["alice", "--out", "results"])

    assert settings.out_dir == Path("results")


def test_username_is_required():
    """Calling parse with no args should fail — username is positional and required."""
    with pytest.raises(SystemExit):
        ArgumentParser().parse([])
