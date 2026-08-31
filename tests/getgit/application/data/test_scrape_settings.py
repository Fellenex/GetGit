"""Tests for the ScrapeSettings dataclass."""

from getgit.application import ScrapeSettings


def test_holds_all_fields_passed_in():
    """Constructor accepts and exposes every field by name."""
    s = ScrapeSettings(
        username="alice",
        max_commits=10,
        max_prs=20,
        fetch_extensions=False,
        target_repo="octocat/hello-world",
    )

    assert s.username == "alice"
    assert s.max_commits == 10
    assert s.max_prs == 20
    assert s.fetch_extensions is False
    assert s.target_repo == "octocat/hello-world"


def test_target_repo_defaults_to_none():
    """`target_repo` is optional — full repo discovery when omitted."""
    s = ScrapeSettings("alice", None, None, True)

    assert s.target_repo is None


def test_two_instances_with_same_fields_are_equal():
    """`@dataclass` should give us value equality for free."""
    a = ScrapeSettings("u", None, None, True)
    b = ScrapeSettings("u", None, None, True)

    assert a == b
