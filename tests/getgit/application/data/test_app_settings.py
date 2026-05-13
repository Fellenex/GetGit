"""Tests for the AppSettings dataclass."""

from pathlib import Path

from getgit.application import AppSettings


def test_holds_all_fields_passed_in():
    """Constructor accepts and exposes every field by name."""
    s = AppSettings(
        username="alice",
        out_dir=Path("out"),
        max_commits=10,
        max_prs=20,
        fetch_extensions=False,
        access_token="ghp_xyz",
    )

    assert s.username == "alice"
    assert s.out_dir == Path("out")
    assert s.max_commits == 10
    assert s.max_prs == 20
    assert s.fetch_extensions is False
    assert s.access_token == "ghp_xyz"


def test_two_instances_with_same_fields_are_equal():
    """`@dataclass` should give us value equality for free."""
    a = AppSettings("u", Path("o"), None, None, True, None)
    b = AppSettings("u", Path("o"), None, None, True, None)

    assert a == b
