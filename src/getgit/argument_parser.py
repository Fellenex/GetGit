"""CLI argument parsing — wraps argparse and produces an `AppSettings`."""

import argparse
from pathlib import Path

from .settings import AppSettings


class ArgumentParser:
    """Parses GetGit's CLI arguments into an `AppSettings`.

    Owns the argparse configuration so `cli.main` doesn't have to. The
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
        self._parser = parser

    def parse(self, argv: list[str] | None = None) -> AppSettings:
        """Parse `argv` (or `sys.argv` when `None`) and return an `AppSettings`."""
        ns = self._parser.parse_args(argv)
        return AppSettings(
            username=ns.username,
            out_dir=Path(ns.out),
            max_commits=ns.max_commits,
            max_prs=ns.max_prs,
            fetch_extensions=not ns.no_extension_breakdown,
        )
