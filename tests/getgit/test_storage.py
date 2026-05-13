"""Tests for the storage layer."""

from datetime import datetime, timezone
from pathlib import Path

from getgit.models import AuthorshipReport, Commit, PullRequest
from getgit.storage import write_report


def _sample_report() -> AuthorshipReport:
    """Build a small report with one commit and one PR for round-trip tests."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    return AuthorshipReport(
        username="u",
        generated_at=ts,
        commits=[Commit(sha="abc", repo="o/r", authored_at=ts, message="m", pull_request_number=42)],
        pull_requests=[
            PullRequest(
                number=42,
                repo="o/r",
                title="t",
                merged=True,
                created_at=ts,
                closed_at=ts,
                additions=10,
                deletions=2,
                comments=3,
                jira_codes=["WD-1", "YWFB-9"],
            )
        ],
    )


def test_write_report_emits_json_and_two_csvs(tmp_path: Path):
    """write_report should produce the JSON plus one CSV per row-shaped model."""
    paths = write_report(_sample_report(), tmp_path)

    assert set(paths) == {"json", "commits_csv", "pull_requests_csv"}
    for p in paths.values():
        assert p.exists()


def test_commits_csv_header_and_row(tmp_path: Path):
    """Commits CSV columns should match the dataclass field order."""
    paths = write_report(_sample_report(), tmp_path)
    lines = paths["commits_csv"].read_text(encoding="utf-8").splitlines()

    assert lines[0] == "sha,repo,authored_at,message,pull_request_number"
    assert lines[1] == "abc,o/r,2026-05-12T00:00:00+00:00,m,42"


def test_pr_csv_joins_jira_codes_with_semicolon(tmp_path: Path):
    """List-valued fields like jira_codes should be `;`-joined for CSV."""
    paths = write_report(_sample_report(), tmp_path)
    lines = paths["pull_requests_csv"].read_text(encoding="utf-8").splitlines()

    assert "WD-1;YWFB-9" in lines[1]


def test_empty_collection_writes_empty_csv(tmp_path: Path):
    """If a collection is empty we can't infer columns, so write an empty file."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    report = AuthorshipReport(username="u", generated_at=ts, commits=[], pull_requests=[])

    paths = write_report(report, tmp_path)

    assert paths["commits_csv"].read_text(encoding="utf-8") == ""
    assert paths["pull_requests_csv"].read_text(encoding="utf-8") == ""
