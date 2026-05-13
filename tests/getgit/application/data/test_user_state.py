"""Tests for the UserState dataclass."""

from datetime import datetime, timezone

from getgit.application import UserState


def test_defaults_represent_a_first_run():
    """Empty user state = no watermarks, never-run status."""
    s = UserState()

    assert s.pr_search_updated_since is None
    assert s.commits_per_repo == {}
    assert s.last_run_at is None
    assert s.last_run_status == "never"


def test_holds_supplied_watermarks():
    """All four fields can be set explicitly and round-trip via attribute access."""
    ts = datetime(2026, 5, 13, tzinfo=timezone.utc)
    s = UserState(
        pr_search_updated_since=ts,
        commits_per_repo={"o/r": ts},
        last_run_at=ts,
        last_run_status="complete",
    )

    assert s.pr_search_updated_since == ts
    assert s.commits_per_repo == {"o/r": ts}
    assert s.last_run_at == ts
    assert s.last_run_status == "complete"


def test_default_factory_is_independent_per_instance():
    """Mutable default for `commits_per_repo` must not be shared across instances."""
    a = UserState()
    b = UserState()

    a.commits_per_repo["o/r"] = datetime(2026, 5, 12, tzinfo=timezone.utc)

    assert b.commits_per_repo == {}


def test_to_jsonable_emits_iso_strings_via_jsonmodel():
    """UserState inherits to_jsonable from JSONModel — datetimes flatten to ISO."""
    ts = datetime(2026, 5, 13, 3, 21, 34, tzinfo=timezone.utc)
    s = UserState(
        pr_search_updated_since=ts,
        commits_per_repo={"o/r": ts},
        last_run_at=ts,
        last_run_status="complete",
    )

    out = s.to_jsonable()

    assert out["pr_search_updated_since"] == "2026-05-13T03:21:34+00:00"
    assert out["commits_per_repo"]["o/r"] == "2026-05-13T03:21:34+00:00"
    assert out["last_run_at"] == "2026-05-13T03:21:34+00:00"
    assert out["last_run_status"] == "complete"
