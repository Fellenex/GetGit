"""Tests for the Commit model."""

from datetime import datetime, timezone

from getgit.models import Commit


def test_to_jsonable_serializes_datetime_as_iso():
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


def test_pull_request_number_round_trips():
    """A linked commit should carry its source PR number through serialization."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    commit = Commit(
        sha="def", repo="o/r", authored_at=ts, message="m", pull_request_number=99
    )

    assert commit.to_jsonable()["pull_request_number"] == 99
