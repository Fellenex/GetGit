"""Cross-scrape runtime configuration produced by the CLI's argument parser."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppSettings:
    """The config that stays stable across many scrapes.

    Holds only the values a long-lived process or scheduler sets once
    and reuses for every run — the storage destination and the auth
    token. The per-scrape parameters (username, caps, target repo) live
    in `ScrapeSettings` instead. This is the stable layer the guidelines
    anticipate: "the auth-token source and the storage destination are
    the only layers expected to change between phases" — the CLI reads
    the token from `GITHUB_TOKEN`; phase 2's HTTP entry point will
    populate it from OAuth.
    """

    out_dir: Path
    access_token: str | None = None
