"""Tests for the ExitCode enum."""

from getgit.application import ExitCode


def test_values_match_the_documented_exit_codes():
    """The three run outcomes map to 0 / 2 / 3."""
    assert ExitCode.SUCCESS == 0
    assert ExitCode.PARTIAL == 2
    assert ExitCode.REPOSITORY_ACCESS_ERROR == 3


def test_is_usable_directly_as_an_int_exit_status():
    """As an IntEnum, a member is an int — so `SystemExit`/`sys.exit` accept it as-is."""
    assert int(ExitCode.PARTIAL) == 2
    assert isinstance(ExitCode.SUCCESS, int)
