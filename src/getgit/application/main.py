"""UI-agnostic orchestration: run the scrape pipeline against an `AppSettings`.

The CLI calls `run(settings)` after parsing argv. Phase 2's FastAPI
endpoint will call the same `run(settings)` after building an
`AppSettings` from the request. Anything specific to one entry point
(argparse, environment loading, HTTP request decoding) lives outside
this module.
"""

import sys
from datetime import datetime, timezone

from ..authentication import PersonalTokenAuth
from ..fetchers import CommitFetcher, PullRequestFetcher, RepoFetcher
from ..models import AuthorshipReport
from ..storage import write_report
from .app_settings import AppSettings


def run(settings: AppSettings) -> int:
    """Execute the full scrape and write the report to disk.

    Returns a process-style exit code (`0` on success). The orchestration
    is deliberately printf-based for now: phase 2 will swap stderr
    breadcrumbs for structured logging once there's a non-CLI consumer
    that benefits from it.
    """
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
