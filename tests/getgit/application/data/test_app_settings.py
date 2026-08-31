"""Tests for the AppSettings dataclass."""

from pathlib import Path

from getgit.application import AppSettings


def test_holds_all_fields_passed_in():
    """Constructor accepts and exposes every field by name."""
    s = AppSettings(
        out_dir=Path("out"),
        access_token="ghp_xyz",
    )

    assert s.out_dir == Path("out")
    assert s.access_token == "ghp_xyz"


def test_access_token_defaults_to_none():
    """Only `out_dir` is required; the token defaults to None until validation in run()."""
    s = AppSettings(out_dir=Path("out"))

    assert s.access_token is None


def test_two_instances_with_same_fields_are_equal():
    """`@dataclass` should give us value equality for free."""
    a = AppSettings(Path("o"), None)
    b = AppSettings(Path("o"), None)

    assert a == b
