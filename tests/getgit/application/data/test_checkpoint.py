"""Tests for the Checkpoint dataclass."""

from datetime import datetime, timezone

from getgit.application import Checkpoint


def test_defaults_represent_a_first_run():
    """Empty checkpoint = no watermarks, never-run status."""
    c = Checkpoint()

    assert c.pr_search_updated_since is None
    assert c.commits_per_repo == {}
    assert c.last_run_at is None
    assert c.last_run_status == "never"


def test_holds_supplied_watermarks():
    """All four fields can be set explicitly and round-trip via attribute access."""
    ts = datetime(2026, 5, 13, tzinfo=timezone.utc)
    c = Checkpoint(
        pr_search_updated_since=ts,
        commits_per_repo={"o/r": ts},
        last_run_at=ts,
        last_run_status="complete",
    )

    assert c.pr_search_updated_since == ts
    assert c.commits_per_repo == {"o/r": ts}
    assert c.last_run_at == ts
    assert c.last_run_status == "complete"


def test_default_factory_is_independent_per_instance():
    """Mutable default for `commits_per_repo` must not be shared across instances."""
    a = Checkpoint()
    b = Checkpoint()

    a.commits_per_repo["o/r"] = datetime(2026, 5, 12, tzinfo=timezone.utc)

    assert b.commits_per_repo == {}
