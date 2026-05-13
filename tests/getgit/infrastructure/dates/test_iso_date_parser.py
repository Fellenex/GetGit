"""Tests for IsoDateParser."""

from datetime import datetime, timezone

from getgit.infrastructure.dates import IsoDateParser


def test_parses_standard_iso_with_offset():
    """Standard ISO with `+00:00` should round-trip."""
    out = IsoDateParser.parse("2026-05-13T03:21:34+00:00")

    assert out == datetime(2026, 5, 13, 3, 21, 34, tzinfo=timezone.utc)


def test_parses_github_z_suffixed_form():
    """GitHub's `Z` suffix is normalized to `+00:00` before parsing."""
    out = IsoDateParser.parse("2026-05-13T03:21:34Z")

    assert out == datetime(2026, 5, 13, 3, 21, 34, tzinfo=timezone.utc)


def test_returns_none_for_none():
    """`None` input passes through — common when a JSON field is absent/null."""
    assert IsoDateParser.parse(None) is None


def test_returns_none_for_empty_string():
    """Empty strings are also treated as missing input."""
    assert IsoDateParser.parse("") is None


def test_parses_naive_iso_without_offset():
    """ISO strings without a timezone offset still parse — produce a naive datetime."""
    out = IsoDateParser.parse("2026-05-13T03:21:34")

    assert out == datetime(2026, 5, 13, 3, 21, 34)
    assert out.tzinfo is None
