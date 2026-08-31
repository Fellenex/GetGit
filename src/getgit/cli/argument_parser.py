"""CLI argument parsing — wraps argparse and produces the settings pair."""

import argparse
import os
from pathlib import Path

from ..application import AppSettings, ScrapeSettings


class ArgumentParser:
    """Parses GetGit's CLI arguments into an `(AppSettings, ScrapeSettings)` pair.

    Owns the argparse configuration so `cli.entrypoint` doesn't have to. The
    standard library's `argparse.ArgumentParser` is held as a private
    field rather than subclassed — composition keeps the public surface
    (`parse`) tiny and avoids inheriting argparse internals we don't
    need.
    """

    def __init__(self) -> None:
        """Build the underlying argparse parser with every flag GetGit accepts."""
        parser = argparse.ArgumentParser(
            prog="getgit", description="Scrape GitHub authorship data."
        )
        parser.add_argument("username", help="GitHub username to scrape.")
        parser.add_argument(
            "--out", default="output", help="Output directory (default: ./output)"
        )
        parser.add_argument(
            "--max-commits",
            type=int,
            default=None,
            help="Cap commits collected (test/dev knob to limit API calls).",
        )
        parser.add_argument(
            "--max-prs",
            type=int,
            default=None,
            help="Cap pull requests collected per set (test/dev knob).",
        )
        parser.add_argument(
            "--no-extension-breakdown",
            action="store_true",
            help="Skip /pulls/{n}/files; store totals only under the '*' key.",
        )
        parser.add_argument(
            "--repo",
            default=None,
            metavar="OWNER/NAME",
            help="Scrape only this repo (e.g. octocat/hello-world). Skips repo discovery.",
        )
        self._parser = parser

    def parse(
        self, argv: list[str] | None = None
    ) -> tuple[AppSettings, ScrapeSettings]:
        """Parse `argv` (or `sys.argv` when `None`) into the settings pair.

        Returns the stable `AppSettings` (out dir + token) and the
        per-scrape `ScrapeSettings` (username, caps, target repo). The
        GitHub access token comes from the `GITHUB_TOKEN` env var — the
        CLI is the only entry point that reads it from the environment.
        Phase 2's HTTP entry point will populate `access_token` from the
        OAuth flow instead.
        """
        ns = self._parser.parse_args(argv)
        app_settings = AppSettings(
            out_dir=Path(ns.out),
            access_token=os.environ.get("GITHUB_TOKEN"),
        )
        scrape_settings = ScrapeSettings(
            username=ns.username,
            max_commits=ns.max_commits,
            max_prs=ns.max_prs,
            fetch_extensions=not ns.no_extension_breakdown,
            target_repo=ns.repo,
        )
        return app_settings, scrape_settings
