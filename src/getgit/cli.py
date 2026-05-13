"""Command-line entry point for GetGit."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .auth import PersonalTokenAuth
from .fetchers.commits import fetch_commits
from .fetchers.prs import fetch_pull_requests
from .fetchers.repos import list_repos, viewer_login
from .models import AuthorshipReport
from .storage import write_report


def main(argv: list[str] | None = None) -> int:
    """Parse args, run all fetchers, and write the JSON report.

    `argv` is exposed for testing; production callers (the console
    script, `python -m getgit`) leave it `None` so argparse reads
    `sys.argv`. Returns a process exit code.
    """
    load_dotenv()
    parser = argparse.ArgumentParser(prog="getgit", description="Scrape GitHub authorship data.")
    parser.add_argument("username", help="GitHub username to scrape.")
    parser.add_argument("--out", default="output", help="Output directory (default: ./output)")
    args = parser.parse_args(argv)

    auth = PersonalTokenAuth()
    with auth.client() as client:
        viewer = viewer_login(client)
        is_self = viewer.lower() == args.username.lower()

        print(f"Viewer: {viewer} | Target: {args.username} | Self: {is_self}", file=sys.stderr)

        repos = list_repos(client, args.username, is_self=is_self)
        print(f"Found {len(repos)} repos", file=sys.stderr)

        commits = fetch_commits(client, repos, args.username)
        print(f"Found {len(commits)} commits", file=sys.stderr)

        prs = fetch_pull_requests(client, args.username)
        print(f"Found {len(prs)} closed PRs", file=sys.stderr)

    report = AuthorshipReport(
        username=args.username,
        generated_at=datetime.now(timezone.utc),
        commits=commits,
        pull_requests=prs,
    )
    path = write_report(report, Path(args.out))
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
