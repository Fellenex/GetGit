"""Tests for the Review model."""

from datetime import datetime, timezone

from getgit.github import Review


def test_to_jsonable_round_trips_all_fields():
    """A Review should serialize with state, index, and an ISO submitted_at."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    review = Review(
        pr_repo="o/r",
        pr_number=42,
        index=2,
        state="CHANGES_REQUESTED",
        submitted_at=ts,
        body="needs work",
    )

    out = review.to_jsonable()

    assert out == {
        "pr_repo": "o/r",
        "pr_number": 42,
        "index": 2,
        "state": "CHANGES_REQUESTED",
        "submitted_at": "2026-05-12T00:00:00+00:00",
        "body": "needs work",
    }


def test_submitted_at_can_be_none():
    """A pending review with no submission timestamp should serialize as null."""
    review = Review(
        pr_repo="o/r",
        pr_number=1,
        index=1,
        state="COMMENTED",
        submitted_at=None,
        body="",
    )

    assert review.to_jsonable()["submitted_at"] is None
