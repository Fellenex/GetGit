"""Tests for ReportService — orchestration on top of the writers."""

from datetime import datetime, timezone
from pathlib import Path

from getgit.exporting import ReportService
from getgit.github import (
    AuthorshipReport,
    Commit,
    PullRequest,
    PullRequestFetchResult,
    Review,
)


def _sample_report() -> AuthorshipReport:
    """Build a small report with one of each row type for round-trip tests."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    return AuthorshipReport(
        username="u",
        generated_at=ts,
        commits=[Commit(sha="abc", repo="o/r", authored_at=ts, message="m", pull_request_number=42)],
        authored_pull_requests=[
            PullRequest(
                number=42,
                repo="o/r",
                title="t",
                merged=True,
                created_at=ts,
                closed_at=ts,
                updated_at=ts,
                additions={".py": 10, ".yml": 5},
                deletions={".py": 2},
                comments=3,
                comments_by_author=0,
                jira_codes=["WD-1", "YWFB-12", "YWFB-9"],
            )
        ],
        participated_pull_requests=[
            PullRequest(
                number=99,
                repo="o/other",
                title="other",
                merged=True,
                created_at=ts,
                closed_at=ts,
                updated_at=ts,
                additions={".py": 1},
                deletions={},
                comments=4,
                comments_by_author=2,
                jira_codes=[],
            )
        ],
        reviews=[
            Review(
                pr_repo="o/other",
                pr_number=99,
                index=1,
                state="APPROVED",
                submitted_at=ts,
                body="lgtm",
            )
        ],
    )


def test_generate_report_flattens_fetch_result_into_collections():
    """generate_report splits a PullRequestFetchResult across the report's fields."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    authored = PullRequest(
        number=1, repo="o/r", title="a", merged=True,
        created_at=ts, closed_at=ts, updated_at=ts,
        additions={}, deletions={}, comments=0, comments_by_author=0, jira_codes=[],
    )
    participated = PullRequest(
        number=2, repo="o/r", title="p", merged=False,
        created_at=ts, closed_at=None, updated_at=ts,
        additions={}, deletions={}, comments=1, comments_by_author=0, jira_codes=[],
    )
    review = Review(
        pr_repo="o/r", pr_number=2, index=0, state="APPROVED", submitted_at=ts, body="",
    )
    commit = Commit(sha="abc", repo="o/r", authored_at=ts, message="m", pull_request_number=1)
    pr_result = PullRequestFetchResult(
        authored=[authored], participated=[participated], reviews=[review]
    )

    report = ReportService().generate_report(
        "alice", [commit], pr_result, generated_at=ts
    )

    assert report.username == "alice"
    assert report.generated_at == ts
    assert report.commits == [commit]
    assert report.authored_pull_requests == [authored]
    assert report.participated_pull_requests == [participated]
    assert report.reviews == [review]


def test_write_report_emits_a_json_and_csv_per_collection(tmp_path: Path):
    """Each top-level collection should produce both a JSON and a CSV file."""
    paths = ReportService().write_report(_sample_report(), tmp_path)

    assert set(paths) == {
        "commits_json",
        "commits_csv",
        "authored_pull_requests_json",
        "authored_pull_requests_csv",
        "participated_pull_requests_json",
        "participated_pull_requests_csv",
        "reviews_json",
        "reviews_csv",
    }
    for p in paths.values():
        assert p.exists()


def test_files_land_in_per_run_subdirectory(tmp_path: Path):
    """Output goes to `<out>/<username>/<generated_at>/<collection>.<format>`."""
    paths = ReportService().write_report(_sample_report(), tmp_path)

    expected_dir = tmp_path / "u" / "2026-05-12_T00-00-00"
    assert paths["commits_json"] == expected_dir / "commits.json"
    assert paths["reviews_csv"] == expected_dir / "reviews.csv"
    assert expected_dir.is_dir()


def test_collection_filenames_no_longer_carry_username_prefix(tmp_path: Path):
    """The username/timestamp metadata lives in the path, not the filename."""
    paths = ReportService().write_report(_sample_report(), tmp_path)

    assert paths["commits_json"].name == "commits.json"
    assert paths["reviews_csv"].name == "reviews.csv"
