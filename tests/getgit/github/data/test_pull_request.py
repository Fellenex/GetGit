"""Tests for the PullRequest model."""

from datetime import datetime, timezone

from getgit.github import PullRequest


def test_to_jsonable_emits_dict_diff_stats_and_jira_codes():
    """additions/deletions should serialize as dicts; jira_codes as a list."""
    ts = datetime(2026, 5, 12, tzinfo=timezone.utc)
    pr = PullRequest(
        number=1,
        repo="o/r",
        title="t",
        merged=True,
        created_at=ts,
        closed_at=ts,
        additions={".py": 10, "Dockerfile": 3},
        deletions={".py": 2},
        comments=4,
        comments_by_author=1,
        jira_codes=["WD-1"],
    )

    out = pr.to_jsonable()

    assert out["additions"] == {".py": 10, "Dockerfile": 3}
    assert out["deletions"] == {".py": 2}
    assert out["jira_codes"] == ["WD-1"]
    assert out["comments_by_author"] == 1
    assert out["merged"] is True
