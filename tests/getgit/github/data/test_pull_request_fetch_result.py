"""Tests for PullRequestFetchResult."""

from datetime import datetime, timezone

from getgit.github import PullRequest, PullRequestFetchResult


def _pr(number: int, updated_at: datetime | None) -> PullRequest:
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


def test_defaults_are_empty_collections():
    """Each field defaults to its own empty container."""
    out = PullRequestFetchResult()

    assert out.authored == []
    assert out.participated == []
    assert out.reviews == []
    assert out.commit_pr_index == {}


def test_default_factories_are_independent_per_instance():
    """Two instances must not share the same default list (mutable-default trap)."""
    a = PullRequestFetchResult()
    b = PullRequestFetchResult()

    a.authored.append("x")

    assert b.authored == []


def test_most_recent_updated_at_spans_authored_and_participated():
    """The newest timestamp wins whether it sits in authored or participated."""
    older = datetime(2026, 5, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 5, 20, tzinfo=timezone.utc)
    result = PullRequestFetchResult(
        authored=[_pr(1, older)], participated=[_pr(2, newer)]
    )

    assert result.most_recent_updated_at() == newer


def test_most_recent_updated_at_returns_fallback_when_no_timestamps():
    """With no PRs (or none carrying a timestamp) the supplied fallback is returned."""
    fallback = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert PullRequestFetchResult().most_recent_updated_at(fallback) == fallback
    assert (
        PullRequestFetchResult(authored=[_pr(1, None)]).most_recent_updated_at(fallback)
        == fallback
    )


def test_most_recent_updated_at_fallback_defaults_to_none():
    """Fallback is optional; an empty result reports no watermark at all."""
    assert PullRequestFetchResult().most_recent_updated_at() is None
