"""Tests for the storage layer."""

from datetime import datetime, timezone
from pathlib import Path

from getgit.models import AuthorshipReport, Commit, PullRequest, Review
from getgit.storage import write_report


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
                additions={".py": 10, ".yml": 5},
                deletions={".py": 2},
                comments=3,
                comments_by_author=0,
                jira_codes=["WD-1", "YWFB-9"],
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


def test_write_report_emits_json_and_four_csvs(tmp_path: Path):
    """write_report should produce JSON plus a CSV per row-shaped collection."""
    paths = write_report(_sample_report(), tmp_path)

    assert set(paths) == {
        "json",
        "commits_csv",
        "authored_pull_requests_csv",
        "participated_pull_requests_csv",
        "reviews_csv",
    }
    for p in paths.values():
        assert p.exists()


def test_pr_csv_serializes_dict_fields_as_key_value_pairs(tmp_path: Path):
    """Dict fields like additions should render as `key:value;...` sorted by key."""
    paths = write_report(_sample_report(), tmp_path)
    line = paths["authored_pull_requests_csv"].read_text(encoding="utf-8").splitlines()[1]

    assert ".py:10;.yml:5" in line
    assert ".py:2" in line
    assert "WD-1;YWFB-9" in line


def test_reviews_csv_columns(tmp_path: Path):
    """Reviews CSV header should match the dataclass field order."""
    paths = write_report(_sample_report(), tmp_path)
    header = paths["reviews_csv"].read_text(encoding="utf-8").splitlines()[0]

    assert header == "pr_repo,pr_number,index,state,submitted_at,body"


def test_empty_dict_serializes_to_empty_cell(tmp_path: Path):
    """An empty dict (e.g. no deletions on a participated PR) should render as ''."""
    paths = write_report(_sample_report(), tmp_path)
    lines = paths["participated_pull_requests_csv"].read_text(encoding="utf-8").splitlines()
    # Header order: number,repo,title,merged,created_at,closed_at,additions,deletions,comments,comments_by_author,jira_codes
    cells = lines[1].split(",")
    deletions_idx = lines[0].split(",").index("deletions")
    assert cells[deletions_idx] == ""


def test_empty_collection_writes_empty_csv(tmp_path: Path):
    """If a collection is empty we can't infer columns, so write an empty file."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    report = AuthorshipReport(
        username="u",
        generated_at=ts,
        commits=[],
        authored_pull_requests=[],
        participated_pull_requests=[],
        reviews=[],
    )

    paths = write_report(report, tmp_path)

    assert paths["commits_csv"].read_text(encoding="utf-8") == ""
    assert paths["reviews_csv"].read_text(encoding="utf-8") == ""
