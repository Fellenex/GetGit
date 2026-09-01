"""UI-agnostic orchestration: run the scrape pipeline against the settings pair.

The CLI calls `run(app_settings, scrape_settings)` after parsing argv.
Phase 2's FastAPI endpoint will call the same `run(...)` after building
both settings objects from the request — the stable `AppSettings` (out
dir + token) and the per-request `ScrapeSettings`. Anything specific to
one entry point (argparse, environment loading, HTTP request decoding)
lives outside this module.
"""

import logging
from datetime import datetime, timezone

from ..exporting import JSONFileHandler, ReportService
from ..github import (
    Commit,
    GithubClient,
    GithubRepo,
    GithubService,
    GithubSettings,
    PullRequestFetchResult,
    RateLimitExceededError,
    RepositoryAccessError,
)
from .data import AppSettings, ExitCode, ScrapeSettings
from .user_state_repository import UserStateRepository
from .user_state_service import UserStateService

logger = logging.getLogger("getgit")
"""Progress/diagnostic channel for the scrape.

`run` emits its progress through this logger instead of writing to
`sys.stderr` directly, so the reusable core carries no presentation
policy: the CLI entry point attaches a stderr handler (preserving the
old behaviour), and a phase-2 HTTP caller attaches its own sink (or
none). See [ADR-061].
"""


def run(app_settings: AppSettings, scrape_settings: ScrapeSettings) -> ExitCode:
    """Execute the full scrape and write the report to disk.

    Returns an `ExitCode` (an `IntEnum`, so it doubles as the process
    exit status):
    - `ExitCode.SUCCESS` (`0`) on full success.
    - `ExitCode.PARTIAL` (`2`) on partial save — a 403 was hit
      mid-scrape and the report was written from whatever data was
      collected so far.
    - `ExitCode.REPOSITORY_ACCESS_ERROR` (`3`) when a `--repo`-scoped
      search returns 422 — the target repo doesn't exist or the token
      can't see it. Fails fast with a clean message (no report written,
      no traceback).

    Raises `RuntimeError` if `app_settings.access_token` is missing —
    failing fast here beats discovering it mid-scrape via a 401 from
    GitHub.

    A per-username `UserState` at `<out_dir>/<username>/state.json`
    tracks watermarks across runs. The next run's PR search and
    per-repo commit listings are constrained to data updated since
    those watermarks. On a complete run the watermarks advance to the
    newest data we just collected; on a partial (rate-limited) run
    they intentionally do *not* advance, so the next run re-fetches
    the same window.
    """
    if not app_settings.access_token:
        raise RuntimeError(
            "No GitHub access token in AppSettings. "
            "Set GITHUB_TOKEN (CLI) or supply an OAuth token (web)."
        )

    started_at = datetime.now(timezone.utc)
    state_service = UserStateService(
        UserStateRepository(
            app_settings.out_dir, scrape_settings.username, JSONFileHandler()
        )
    )
    state = state_service.load_current_state()
    logger.info("%s", state.describe_resume())

    repos: list[GithubRepo] = []
    pr_result = PullRequestFetchResult()
    commits: list[Commit] = []
    partial = False

    github_settings = GithubSettings(auth_token=app_settings.access_token)
    try:
        with GithubClient(github_settings) as client:
            viewer = client.viewer_login()
            is_self = viewer.lower() == scrape_settings.username.lower()

            logger.info(
                "Viewer: %s | Target: %s | Self: %s",
                viewer,
                scrape_settings.username,
                is_self,
            )

            github = GithubService.build(client, scrape_settings)

            if scrape_settings.target_repo:
                repos = [GithubRepo(full_name=scrape_settings.target_repo)]
                logger.info(
                    "Targeting single repo: %s (skipping repo discovery)",
                    scrape_settings.target_repo,
                )
            else:
                repos = github.fetch_repositories(is_self=is_self)
                logger.info("Found %d repos", len(repos))

            pr_result = github.fetch_pull_requests(
                since=state.pr_search_updated_since
            )
            logger.info(
                "Found %d authored PRs, %d participated PRs, %d reviews "
                "(indexed %d commits)",
                len(pr_result.authored),
                len(pr_result.participated),
                len(pr_result.reviews),
                len(pr_result.commit_pr_index),
            )

            commits = github.fetch_commits(
                repos=repos,
                pr_index=pr_result.commit_pr_index,
                since_per_repo=state.commits_per_repo,
            )
            logger.info("Found %d commits", len(commits))
    except RepositoryAccessError as e:
        logger.error("%s", e)
        return ExitCode.REPOSITORY_ACCESS_ERROR
    except RateLimitExceededError as e:
        partial = True
        logger.error("Hit rate limit: %s", e)
        repos, pr_result, commits = _absorb_partial(e.partial, repos, pr_result, commits)
        logger.error("Saving partial report from data collected so far.")

    paths = ReportService().write_report(
        scrape_settings.username,
        commits,
        pr_result,
        app_settings.out_dir,
        generated_at=datetime.now(timezone.utc),
    )
    for label, p in paths.items():
        logger.info("Wrote %s: %s", label, p)

    state_path = state_service.save_new_state(
        state, pr_result, commits, started_at, partial
    )
    logger.info("Updated user state: %s", state_path)

    return ExitCode.PARTIAL if partial else ExitCode.SUCCESS


def _absorb_partial(
    partial: object,
    repos: list[GithubRepo],
    pr_result: PullRequestFetchResult,
    commits: list[Commit],
) -> tuple[list[GithubRepo], PullRequestFetchResult, list[Commit]]:
    """Route the failing provider's partial payload back into the local result vars.

    The orchestration is sequential, so only one provider was running
    when the rate limit hit — we can identify which one by the partial
    payload's type (and, for the two `list` cases, by element type).
    Anything we already finished keeps its earlier value.
    """
    if isinstance(partial, PullRequestFetchResult):
        return repos, partial, commits
    if isinstance(partial, list) and partial:
        if isinstance(partial[0], Commit):
            return repos, pr_result, partial
        return partial, pr_result, commits
    return repos, pr_result, commits
