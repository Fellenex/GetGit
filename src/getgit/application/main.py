"""UI-agnostic orchestration: run the scrape pipeline against an `AppSettings`.

The CLI calls `run(settings)` after parsing argv. Phase 2's FastAPI
endpoint will call the same `run(settings)` after building an
`AppSettings` from the request. Anything specific to one entry point
(argparse, environment loading, HTTP request decoding) lives outside
this module.
"""

import sys
from datetime import datetime, timezone

from ..authentication import GithubSettings
from ..exporting import ReportExporter
from ..github import (
    AuthorshipReport,
    CommitProvider,
    GithubClient,
    GithubService,
    PullRequestProvider,
    RepoProvider,
)
from .data import AppSettings


def run(settings: AppSettings) -> int:
    """Execute the full scrape and write the report to disk.

    Returns a process-style exit code (`0` on success). Raises
    `RuntimeError` if `settings.access_token` is missing — failing fast
    here beats discovering it mid-scrape via a 401 from GitHub.
    """
    if not settings.access_token:
        raise RuntimeError(
            "No GitHub access token in AppSettings. "
            "Set GITHUB_TOKEN (CLI) or supply an OAuth token (web)."
        )

    github_settings = GithubSettings(auth_token=settings.access_token)
    with GithubClient(github_settings) as client:
        viewer = client.viewer_login()
        is_self = viewer.lower() == settings.username.lower()

        print(
            f"Viewer: {viewer} | Target: {settings.username} | Self: {is_self}",
            file=sys.stderr,
        )

        github = GithubService(
            repo_provider=RepoProvider(client),
            pull_request_provider=PullRequestProvider(client),
            commit_provider=CommitProvider(client),
            settings=settings,
        )

        repos = github.fetch_repositories(is_self=is_self)
        print(f"Found {len(repos)} repos", file=sys.stderr)

        pr_result = github.fetch_pull_requests()
        print(
            f"Found {len(pr_result.authored)} authored PRs, "
            f"{len(pr_result.participated)} participated PRs, "
            f"{len(pr_result.reviews)} reviews "
            f"(indexed {len(pr_result.commit_pr_index)} commits)",
            file=sys.stderr,
        )

        commits = github.fetch_commits(repos=repos, pr_index=pr_result.commit_pr_index)
        print(f"Found {len(commits)} commits", file=sys.stderr)

    report = AuthorshipReport(
        username=settings.username,
        generated_at=datetime.now(timezone.utc),
        commits=commits,
        authored_pull_requests=pr_result.authored,
        participated_pull_requests=pr_result.participated,
        reviews=pr_result.reviews,
    )
    paths = ReportExporter().write_report(report, settings.out_dir)
    for label, p in paths.items():
        print(f"Wrote {label}: {p}")
    return 0
