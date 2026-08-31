"""Tests for the CLI entry point — verifies it wires argparse + application.run together."""

from unittest.mock import patch

from getgit.cli import main


def test_main_calls_application_run_with_parsed_settings(monkeypatch):
    """main() should parse argv into the settings pair and hand both to application.run."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    captured = {}

    def fake_run(app_settings, scrape_settings):
        captured["app_settings"] = app_settings
        captured["scrape_settings"] = scrape_settings
        return 0

    with patch("getgit.cli.entrypoint.run", side_effect=fake_run) as mocked:
        rc = main(["alice", "--max-prs", "3"])

    assert rc == 0
    assert mocked.called
    assert captured["scrape_settings"].username == "alice"
    assert captured["scrape_settings"].max_prs == 3
    assert captured["app_settings"].access_token == "ghp_test"


def test_main_returns_runs_exit_code(monkeypatch):
    """Whatever run() returns is what main() returns."""
    monkeypatch.setenv("GITHUB_TOKEN", "t")

    with patch("getgit.cli.entrypoint.run", return_value=42):
        assert main(["alice"]) == 42
