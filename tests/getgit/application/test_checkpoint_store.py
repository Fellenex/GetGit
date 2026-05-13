"""Tests for CheckpointStore — file-backed persistence for `Checkpoint`."""

import json
from datetime import datetime, timezone
from pathlib import Path

from getgit.application import Checkpoint, CheckpointStore


def test_load_returns_empty_checkpoint_when_no_file_exists(tmp_path: Path):
    """First-run case: no state.json yet → fresh empty checkpoint."""
    store = CheckpointStore(tmp_path, "alice")

    out = store.load()

    assert out == Checkpoint()


def test_save_creates_username_directory_and_state_file(tmp_path: Path):
    """The store should create `<out>/<username>/state.json`, parents and all."""
    store = CheckpointStore(tmp_path, "alice")

    path = store.save(Checkpoint(last_run_status="complete"))

    assert path == tmp_path / "alice" / "state.json"
    assert path.exists()


def test_round_trip_preserves_all_fields(tmp_path: Path):
    """Saving and re-loading should yield the same values, with datetimes intact."""
    ts = datetime(2026, 5, 13, 3, 21, 34, tzinfo=timezone.utc)
    original = Checkpoint(
        pr_search_updated_since=ts,
        commits_per_repo={"o/r": ts, "o/other": ts},
        last_run_at=ts,
        last_run_status="complete",
    )
    store = CheckpointStore(tmp_path, "alice")

    store.save(original)
    loaded = store.load()

    assert loaded == original


def test_save_writes_iso_strings_for_datetimes(tmp_path: Path):
    """The on-disk JSON should use ISO strings, not Python repr or epoch ints."""
    ts = datetime(2026, 5, 13, tzinfo=timezone.utc)
    store = CheckpointStore(tmp_path, "alice")
    store.save(Checkpoint(pr_search_updated_since=ts, commits_per_repo={"o/r": ts}))

    raw = json.loads((tmp_path / "alice" / "state.json").read_text(encoding="utf-8"))

    assert raw["pr_search_updated_since"] == "2026-05-13T00:00:00+00:00"
    assert raw["commits_per_repo"]["o/r"] == "2026-05-13T00:00:00+00:00"
