"""Tests for ReportService — assembles and writes the report via the writers."""

import json
from datetime import datetime, timezone
from pathlib import Path

from getgit.exporting import ReportService
from getgit.github import Commit, GithubScrapeResult, PullRequest, Review


def _sample_pieces() -> tuple[str, list[Commit], GithubScrapeResult, datetime]:
    """Build the (username, commits, pr_result, generated_at) args write_report takes."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    commits = [
        Commit(sha="abc", repo="o/r", authored_at=ts, message="m", pull_request_number=42)
    ]
    pr_result = GithubScrapeResult(
        authored=[
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
        participated=[
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
    return "u", commits, pr_result, ts


def _write(tmp_path: Path) -> dict[str, Path]:
    """Run write_report against the sample pieces and return its `{label: path}`."""
    username, commits, pr_result, ts = _sample_pieces()
    return ReportService().write_report(
        username, commits, pr_result, tmp_path, generated_at=ts
    )


def test_write_report_emits_a_json_and_csv_per_collection(tmp_path: Path):
    """Each top-level collection should produce both a JSON and a CSV file."""
    paths = _write(tmp_path)

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


def test_write_report_routes_fetch_result_into_the_right_collections(tmp_path: Path):
    """The fetch result is flattened: authored/participated/reviews land in separate files."""
    paths = _write(tmp_path)

    authored = json.loads(paths["authored_pull_requests_json"].read_text(encoding="utf-8"))
    participated = json.loads(
        paths["participated_pull_requests_json"].read_text(encoding="utf-8")
    )
    reviews = json.loads(paths["reviews_json"].read_text(encoding="utf-8"))

    assert [pr["number"] for pr in authored] == [42]
    assert [pr["number"] for pr in participated] == [99]
    assert [r["pr_number"] for r in reviews] == [99]


def test_files_land_in_per_run_subdirectory(tmp_path: Path):
    """Output goes to `<out>/<username>/<generated_at>/<collection>.<format>`."""
    paths = _write(tmp_path)

    expected_dir = tmp_path / "u" / "2026-05-12_T00-00-00"
    assert paths["commits_json"] == expected_dir / "commits.json"
    assert paths["reviews_csv"] == expected_dir / "reviews.csv"
    assert expected_dir.is_dir()


def test_collection_filenames_no_longer_carry_username_prefix(tmp_path: Path):
    """The username/timestamp metadata lives in the path, not the filename."""
    paths = _write(tmp_path)

    assert paths["commits_json"].name == "commits.json"
    assert paths["reviews_csv"].name == "reviews.csv"
