"""UI-agnostic orchestration: run the scrape pipeline against the settings pair.

The CLI calls `run(app_settings, scrape_settings)` after parsing argv.
Phase 2's FastAPI endpoint will call the same `run(...)` after building
both settings objects from the request — the stable `AppSettings` (out
dir + token) and the per-request `ScrapeSettings`. Anything specific to
one entry point (argparse, environment loading, HTTP request decoding)
lives outside this module.
"""

import sys
from datetime import datetime, timezone

from ..exporting import JSONFileHandler, ReportService
from ..github import (
    Commit,
    GithubClient,
    GithubService,
    GithubSettings,
    PullRequestFetchResult,
    RateLimitExceededError,
    RepositoryAccessError,
)
from .data import AppSettings, ExitCode, ScrapeSettings
from .user_state_repository import UserStateRepository
from .user_state_service import UserStateService


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
    print(state.describe_resume(), file=sys.stderr)

    repos: list[dict] = []
    pr_result = PullRequestFetchResult()
    commits: list[Commit] = []
    partial = False

    github_settings = GithubSettings(auth_token=app_settings.access_token)
    try:
        with GithubClient(github_settings) as client:
            viewer = client.viewer_login()
            is_self = viewer.lower() == scrape_settings.username.lower()

            print(
                f"Viewer: {viewer} | Target: {scrape_settings.username} | Self: {is_self}",
                file=sys.stderr,
            )

            github = GithubService.build(client, scrape_settings)

            if scrape_settings.target_repo:
                repos = [{"full_name": scrape_settings.target_repo}]
                print(
                    f"Targeting single repo: {scrape_settings.target_repo} (skipping repo discovery)",
                    file=sys.stderr,
                )
            else:
                repos = github.fetch_repositories(is_self=is_self)
                print(f"Found {len(repos)} repos", file=sys.stderr)

            pr_result = github.fetch_pull_requests(
                since=state.pr_search_updated_since
            )
            print(
                f"Found {len(pr_result.authored)} authored PRs, "
                f"{len(pr_result.participated)} participated PRs, "
                f"{len(pr_result.reviews)} reviews "
                f"(indexed {len(pr_result.commit_pr_index)} commits)",
                file=sys.stderr,
            )

            commits = github.fetch_commits(
                repos=repos,
                pr_index=pr_result.commit_pr_index,
                since_per_repo=state.commits_per_repo,
            )
            print(f"Found {len(commits)} commits", file=sys.stderr)
    except RepositoryAccessError as e:
        print(f"Error: {e}", file=sys.stderr)
        return ExitCode.REPOSITORY_ACCESS_ERROR
    except RateLimitExceededError as e:
        partial = True
        print(f"Hit rate limit: {e}", file=sys.stderr)
        repos, pr_result, commits = _absorb_partial(e.partial, repos, pr_result, commits)
        print("Saving partial report from data collected so far.", file=sys.stderr)

    paths = ReportService().write_report(
        scrape_settings.username,
        commits,
        pr_result,
        app_settings.out_dir,
        generated_at=datetime.now(timezone.utc),
    )
    for label, p in paths.items():
        print(f"Wrote {label}: {p}")

    state_path = state_service.save_new_state(
        state, pr_result, commits, started_at, partial
    )
    print(f"Updated user state: {state_path}", file=sys.stderr)

    return ExitCode.PARTIAL if partial else ExitCode.SUCCESS


def _absorb_partial(
    partial: object,
    repos: list[dict],
    pr_result: PullRequestFetchResult,
    commits: list[Commit],
) -> tuple[list[dict], PullRequestFetchResult, list[Commit]]:
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
