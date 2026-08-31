"""Tests for UserStateService — load/advance/save coordination over the repository."""

from datetime import datetime, timezone
from unittest.mock import Mock

from getgit.application import UserState, UserStateRepository, UserStateService
from getgit.github import Commit, GithubScrapeResult, PullRequest


def _service() -> tuple[UserStateService, Mock]:
    """Build a service backed by a Mock repository; return the service + the mock."""
    repo = Mock(spec=UserStateRepository)
    return UserStateService(repo), repo


def _pr(number: int, updated_at: datetime) -> PullRequest:
    """Build a PullRequest carrying just the `updated_at` these tests read."""
    return PullRequest(
        number=number,
        repo="o/r",
        title="t",
        merged=True,
        created_at=updated_at,
        closed_at=updated_at,
        updated_at=updated_at,
        additions={},
        deletions={},
        comments=0,
        comments_by_author=0,
        jira_codes=[],
    )


def _commit(repo: str, authored_at: datetime) -> Commit:
    """Build a Commit with the repo + authored_at the watermark merge reads."""
    return Commit(sha="abc", repo=repo, authored_at=authored_at, message="m")


def test_load_current_state_delegates_to_the_repository():
    """load_current_state returns exactly what the repository's load() yields."""
    service, repo = _service()
    stored = UserState(last_run_status="complete")
    repo.load.return_value = stored

    assert service.load_current_state() is stored
    repo.load.assert_called_once_with()


def test_save_new_state_advances_watermarks_on_a_complete_run():
    """A complete run advances both watermarks to the newest data collected."""
    service, repo = _service()
    old = datetime(2026, 5, 1, tzinfo=timezone.utc)
    new_pr = datetime(2026, 5, 20, tzinfo=timezone.utc)
    new_commit = datetime(2026, 5, 18, tzinfo=timezone.utc)
    started = datetime(2026, 5, 21, tzinfo=timezone.utc)
    previous = UserState(pr_search_updated_since=old, commits_per_repo={"o/r": old})
    pr_result = GithubScrapeResult(authored=[_pr(1, new_pr)])
    commits = [_commit("o/r", new_commit)]

    service.save_new_state(previous, pr_result, commits, started, partial=False)

    saved = repo.save.call_args.args[0]
    assert saved.pr_search_updated_since == new_pr
    assert saved.commits_per_repo == {"o/r": new_commit}
    assert saved.last_run_at == started
    assert saved.last_run_status == "complete"


def test_save_new_state_holds_watermarks_on_a_partial_run():
    """A partial run keeps the previous watermarks so the next run re-fetches the window."""
    service, repo = _service()
    old = datetime(2026, 5, 1, tzinfo=timezone.utc)
    started = datetime(2026, 5, 21, tzinfo=timezone.utc)
    previous = UserState(pr_search_updated_since=old, commits_per_repo={"o/r": old})
    # Fresh data exists, but a partial must ignore it for watermark purposes.
    pr_result = GithubScrapeResult(
        authored=[_pr(1, datetime(2026, 5, 20, tzinfo=timezone.utc))]
    )
    commits = [_commit("o/r", datetime(2026, 5, 18, tzinfo=timezone.utc))]

    service.save_new_state(previous, pr_result, commits, started, partial=True)

    saved = repo.save.call_args.args[0]
    assert saved.pr_search_updated_since == old
    assert saved.commits_per_repo == {"o/r": old}
    assert saved.last_run_at == started
    assert saved.last_run_status == "partial"


def test_save_new_state_returns_the_path_from_the_repository():
    """save_new_state hands back whatever path the repository's save() returns."""
    service, repo = _service()
    repo.save.return_value = "output/alice/state.json"

    result = service.save_new_state(
        UserState(), GithubScrapeResult(), [], datetime.now(timezone.utc), False
    )

    assert result == "output/alice/state.json"
