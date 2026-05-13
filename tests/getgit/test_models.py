"""Tests for the model layer."""

from datetime import datetime, timezone

from getgit.models import AuthorshipReport, Commit, PullRequest


def test_commit_to_jsonable_serializes_datetime_as_iso():
    """Datetime fields should round-trip as ISO-8601 strings."""
    ts = datetime(2026, 5, 12, 10, 30, tzinfo=timezone.utc)
    commit = Commit(sha="abc", repo="o/r", authored_at=ts, message="hi")

    out = commit.to_jsonable()

    assert out == {
        "sha": "abc",
        "repo": "o/r",
        "authored_at": "2026-05-12T10:30:00+00:00",
        "message": "hi",
        "pull_request_number": None,
    }


def test_authorship_report_serializes_nested_models():
    """Nested dataclasses inside lists should serialize recursively."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    report = AuthorshipReport(
        username="x",
        generated_at=ts,
        commits=[Commit(sha="a", repo="o/r", authored_at=ts, message="m")],
        pull_requests=[
            PullRequest(
                number=1,
                repo="o/r",
                title="t",
                merged=True,
                created_at=ts,
                closed_at=ts,
                additions=10,
                deletions=2,
                comments=3,
                jira_codes=["WD-1"],
            )
        ],
    )

    out = report.to_jsonable()

    assert out["username"] == "x"
    assert out["commits"][0]["sha"] == "a"
    assert out["pull_requests"][0]["jira_codes"] == ["WD-1"]
    assert out["pull_requests"][0]["created_at"] == "2026-05-12T00:00:00+00:00"
