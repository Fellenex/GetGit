"""Per-scrape configuration produced by the CLI's argument parser."""

from dataclasses import dataclass


@dataclass
class ScrapeSettings:
    """Everything that identifies and shapes one specific scrape.

    Split out from `AppSettings` (which holds the cross-scrape config)
    so a long-lived process or scheduler can keep the stable settings
    once and vary only these per-invocation parameters per run. The CLI
    produces one alongside an `AppSettings`; phase 2's HTTP entry point
    will build one per request.
    """

    username: str
    max_commits: int | None
    max_prs: int | None
    fetch_extensions: bool
    target_repo: str | None = None
