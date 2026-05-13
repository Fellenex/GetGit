"""Tests for the AuthorshipReport model."""

from datetime import datetime, timezone

from getgit.models import AuthorshipReport, Commit, PullRequest, Review


def test_serializes_nested_collections_recursively():
    """The top-level report should walk every nested model and primitive."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    report = AuthorshipReport(
        username="x",
        generated_at=ts,
        commits=[Commit(sha="a", repo="o/r", authored_at=ts, message="m")],
        authored_pull_requests=[
            PullRequest(
                number=1,
                repo="o/r",
                title="t",
                merged=True,
                created_at=ts,
                closed_at=ts,
                additions={".py": 10},
                deletions={".py": 2},
                comments=3,
                comments_by_author=1,
                jira_codes=["WD-1"],
            )
        ],
        participated_pull_requests=[],
        reviews=[
            Review(
                pr_repo="o/r",
                pr_number=2,
                index=1,
                state="APPROVED",
                submitted_at=ts,
                body="lgtm",
            )
        ],
    )

    out = report.to_jsonable()

    assert out["username"] == "x"
    assert out["generated_at"] == "2026-05-12T00:00:00+00:00"
    assert out["commits"][0]["sha"] == "a"
    assert out["authored_pull_requests"][0]["additions"] == {".py": 10}
    assert out["authored_pull_requests"][0]["jira_codes"] == ["WD-1"]
    assert out["participated_pull_requests"] == []
    assert out["reviews"][0]["state"] == "APPROVED"
