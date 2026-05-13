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
    Commit,
    CommitProvider,
    GithubClient,
    GithubService,
    PullRequestFetchResult,
    PullRequestProvider,
    RateLimitExceededError,
    RepoProvider,
)
from .data import AppSettings, UserState
from .user_state_store import UserStateStore


def run(settings: AppSettings) -> int:
    """Execute the full scrape and write the report to disk.

    Returns a process exit code:
    - `0` on full success.
    - `2` on partial save — a 403 was hit mid-scrape and the report was
      written from whatever data was collected so far.

    Raises `RuntimeError` if `settings.access_token` is missing —
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
    if not settings.access_token:
        raise RuntimeError(
            "No GitHub access token in AppSettings. "
            "Set GITHUB_TOKEN (CLI) or supply an OAuth token (web)."
        )

    started_at = datetime.now(timezone.utc)
    state_store = UserStateStore(settings.out_dir, settings.username)
    state = state_store.load()
    print(_describe_resume(state), file=sys.stderr)

    repos: list[dict] = []
    pr_result = PullRequestFetchResult()
    commits: list[Commit] = []
    partial = False

    github_settings = GithubSettings(auth_token=settings.access_token)
    try:
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
    except RateLimitExceededError as e:
        partial = True
        print(f"Hit rate limit: {e}", file=sys.stderr)
        repos, pr_result, commits = _absorb_partial(e.partial, repos, pr_result, commits)
        print("Saving partial report from data collected so far.", file=sys.stderr)

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

    new_state = _next_state(state, pr_result, commits, started_at, partial)
    state_path = state_store.save(new_state)
    print(f"Updated user state: {state_path}", file=sys.stderr)

    return 2 if partial else 0


def _describe_resume(state: UserState) -> str:
    """Render a one-line summary of where this run picks up from."""
    if state.last_run_status == "never":
        return "UserState: first run for this user."
    base = f"UserState: last run {state.last_run_status} at {state.last_run_at}"
    if state.pr_search_updated_since:
        base += f"; PRs updated since {state.pr_search_updated_since}"
    if state.commits_per_repo:
        base += f"; {len(state.commits_per_repo)} repos with commit watermarks"
    return base + "."


def _next_state(
    previous: UserState,
    pr_result: PullRequestFetchResult,
    commits: list[Commit],
    started_at: datetime,
    partial: bool,
) -> UserState:
    """Compute the next `UserState` to persist.

    On a complete run we advance watermarks to the newest data we
    collected. On a partial run we keep the previous watermarks so
    the next run re-fetches the same window — trying to advance a
    partial creates gaps in coverage between the old watermark and
    the oldest item we managed to collect this time.
    """
    if partial:
        return UserState(
            pr_search_updated_since=previous.pr_search_updated_since,
            commits_per_repo=dict(previous.commits_per_repo),
            last_run_at=started_at,
            last_run_status="partial",
        )

    pr_watermark = _max_pr_updated_at(pr_result, previous.pr_search_updated_since)
    commits_watermark = _merge_commit_watermarks(previous.commits_per_repo, commits)
    return UserState(
        pr_search_updated_since=pr_watermark,
        commits_per_repo=commits_watermark,
        last_run_at=started_at,
        last_run_status="complete",
    )


def _max_pr_updated_at(
    pr_result: PullRequestFetchResult, fallback: datetime | None
) -> datetime | None:
    """Return the most recent `updated_at` across both PR sets, or `fallback` if empty."""
    timestamps = [
        pr.updated_at
        for pr in (*pr_result.authored, *pr_result.participated)
        if pr.updated_at
    ]
    return max(timestamps) if timestamps else fallback


def _merge_commit_watermarks(
    previous: dict[str, datetime], commits: list[Commit]
) -> dict[str, datetime]:
    """Merge previous per-repo commit watermarks with the newest `authored_at` per repo from this run."""
    merged = dict(previous)
    for commit in commits:
        existing = merged.get(commit.repo)
        if existing is None or commit.authored_at > existing:
            merged[commit.repo] = commit.authored_at
    return merged


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
