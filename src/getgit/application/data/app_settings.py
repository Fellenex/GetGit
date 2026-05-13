"""Runtime configuration produced by the CLI's argument parser."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppSettings:
    """All inputs required to run a GetGit scrape.

    Constructed by `ArgumentParser.parse(...)` and passed into the
    orchestration in `cli.main`. Keeping these as a frozen-ish data
    object instead of a bag of locals makes it trivial to swap argparse
    for an HTTP form (phase 2) or a JSON request body (phase 3) — the
    fetcher pipeline only ever sees this struct.
    """

    username: str
    out_dir: Path
    max_commits: int | None
    max_prs: int | None
    fetch_extensions: bool
    access_token: str | None
    target_repo: str | None = None
