"""Tests for UserStateRepository — file-backed persistence for `UserState`."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from getgit.application import UserState, UserStateRepository
from getgit.exporting import JSONFileHandler


def _repo(tmp_path: Path, username: str = "alice") -> UserStateRepository:
    """Build a repository wired with a real `JSONFileHandler` for round-trip tests."""
    return UserStateRepository(tmp_path, username, JSONFileHandler())


def test_load_returns_empty_state_when_no_file_exists(tmp_path: Path):
    """First-run case: no state.json yet → fresh empty UserState, no handler call needed."""
    out = _repo(tmp_path).load()

    assert out == UserState()


def test_save_creates_username_directory_and_state_file(tmp_path: Path):
    """The repository should create `<out>/<username>/state.json`, parents and all."""
    path = _repo(tmp_path).save(UserState(last_run_status="complete"))

    assert path == tmp_path / "alice" / "state.json"
    assert path.exists()


def test_round_trip_preserves_all_fields(tmp_path: Path):
    """Saving and re-loading should yield the same values, with datetimes intact."""
    ts = datetime(2026, 5, 13, 3, 21, 34, tzinfo=timezone.utc)
    original = UserState(
        pr_search_updated_since=ts,
        commits_per_repo={"o/r": ts, "o/other": ts},
        last_run_at=ts,
        last_run_status="complete",
    )
    repo = _repo(tmp_path)

    repo.save(original)
    loaded = repo.load()

    assert loaded == original


def test_save_writes_iso_strings_for_datetimes(tmp_path: Path):
    """The on-disk JSON should use ISO strings, not Python repr or epoch ints."""
    ts = datetime(2026, 5, 13, tzinfo=timezone.utc)
    _repo(tmp_path).save(UserState(pr_search_updated_since=ts, commits_per_repo={"o/r": ts}))

    raw = json.loads((tmp_path / "alice" / "state.json").read_text(encoding="utf-8"))

    assert raw["pr_search_updated_since"] == "2026-05-13T00:00:00+00:00"
    assert raw["commits_per_repo"]["o/r"] == "2026-05-13T00:00:00+00:00"


def test_save_delegates_to_the_injected_json_handler(tmp_path: Path):
    """save() should hand the state object directly to the handler's write()."""
    handler = Mock(spec=JSONFileHandler)
    handler.write.return_value = tmp_path / "alice" / "state.json"
    repo = UserStateRepository(tmp_path, "alice", handler)
    state = UserState(last_run_status="complete")

    repo.save(state)

    handler.write.assert_called_once_with(state, tmp_path / "alice" / "state.json")


def test_load_delegates_to_the_injected_json_handler(tmp_path: Path):
    """load() should call handler.read() and reconstruct the UserState from raw dict."""
    state_path = tmp_path / "alice" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{}", encoding="utf-8")  # so the existence check passes

    handler = Mock(spec=JSONFileHandler)
    handler.read.return_value = {
        "pr_search_updated_since": "2026-05-13T00:00:00+00:00",
        "commits_per_repo": {"o/r": "2026-05-12T00:00:00+00:00"},
        "last_run_at": "2026-05-13T00:00:00+00:00",
        "last_run_status": "complete",
    }

    out = UserStateRepository(tmp_path, "alice", handler).load()

    handler.read.assert_called_once_with(state_path)
    assert out.last_run_status == "complete"
    assert out.commits_per_repo == {"o/r": datetime(2026, 5, 12, tzinfo=timezone.utc)}
