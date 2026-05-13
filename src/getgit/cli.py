"""Command-line entry point for GetGit."""

import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from .argument_parser import ArgumentParser
from .auth import PersonalTokenAuth
from .fetchers.commits import CommitFetcher
from .fetchers.prs import PullRequestFetcher
from .fetchers.repos import RepoFetcher
from .models import AuthorshipReport
from .settings import AppSettings
from .storage import write_report


def main(argv: list[str] | None = None) -> int:
    """Parse args, run all fetchers, and write the report.

    `argv` is exposed for testing; production callers leave it `None`.
    Returns a process exit code.
    """
    load_dotenv()
    settings = ArgumentParser().parse(argv)
    return _run(settings)


def _run(settings: AppSettings) -> int:
    """Execute the scrape using a fully-resolved `AppSettings`."""
    auth = PersonalTokenAuth()
    with auth.client() as client:
        viewer = client.viewer_login()
        is_self = viewer.lower() == settings.username.lower()

        print(
            f"Viewer: {viewer} | Target: {settings.username} | Self: {is_self}",
            file=sys.stderr,
        )

        repos = RepoFetcher(client).list_repos(settings.username, is_self=is_self)
        print(f"Found {len(repos)} repos", file=sys.stderr)

        pr_result = PullRequestFetcher(client).fetch(
            settings.username,
            limit=settings.max_prs,
            fetch_extensions=settings.fetch_extensions,
        )
        print(
            f"Found {len(pr_result.authored)} authored PRs, "
            f"{len(pr_result.participated)} participated PRs, "
            f"{len(pr_result.reviews)} reviews "
            f"(indexed {len(pr_result.commit_pr_index)} commits)",
            file=sys.stderr,
        )

        commits = CommitFetcher(client).fetch(
            repos,
            settings.username,
            limit=settings.max_commits,
            pr_index=pr_result.commit_pr_index,
        )
        print(f"Found {len(commits)} commits", file=sys.stderr)

    report = AuthorshipReport(
        username=settings.username,
        generated_at=datetime.now(timezone.utc),
        commits=commits,
        authored_pull_requests=pr_result.authored,
        participated_pull_requests=pr_result.participated,
        reviews=pr_result.reviews,
    )
    paths = write_report(report, settings.out_dir)
    for label, p in paths.items():
        print(f"Wrote {label}: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
