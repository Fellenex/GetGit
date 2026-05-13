"""Tests for the CLI entry point — verifies it wires argparse + application.run together."""

from unittest.mock import patch

from getgit.cli import main


def test_main_calls_application_run_with_parsed_settings(monkeypatch):
    """main() should parse argv into AppSettings and hand them to application.run."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    captured = {}

    def fake_run(settings):
        captured["settings"] = settings
        return 0

    with patch("getgit.cli.main.run", side_effect=fake_run) as mocked:
        rc = main(["alice", "--max-prs", "3"])

    assert rc == 0
    assert mocked.called
    settings = captured["settings"]
    assert settings.username == "alice"
    assert settings.max_prs == 3
    assert settings.access_token == "ghp_test"


def test_main_returns_runs_exit_code(monkeypatch):
    """Whatever run() returns is what main() returns."""
    monkeypatch.setenv("GITHUB_TOKEN", "t")

    with patch("getgit.cli.main.run", return_value=42):
        assert main(["alice"]) == 42
