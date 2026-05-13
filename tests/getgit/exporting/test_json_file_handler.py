"""Tests for JSONFileHandler — write + read with `JSONModel` awareness."""

import json
from datetime import datetime, timezone
from pathlib import Path

from getgit.exporting import JSONFileHandler
from getgit.github import Commit


def _ts() -> datetime:
    return datetime(2026, 5, 12, tzinfo=timezone.utc)


def test_write_serializes_a_list_of_jsonmodel_rows(tmp_path: Path):
    """Each row is rendered through its own to_jsonable; output is a top-level list."""
    rows = [
        Commit(sha="a", repo="o/r", authored_at=_ts(), message="m1"),
        Commit(sha="b", repo="o/r", authored_at=_ts(), message="m2", pull_request_number=7),
    ]

    path = JSONFileHandler().write(rows, tmp_path / "out.json")

    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, list)
    assert parsed[0]["sha"] == "a"
    assert parsed[1]["pull_request_number"] == 7
    assert parsed[0]["authored_at"] == "2026-05-12T00:00:00+00:00"


def test_write_serializes_a_single_jsonmodel(tmp_path: Path):
    """A bare JSONModel writes as a JSON object — used by UserStateRepository."""
    commit = Commit(sha="x", repo="o/r", authored_at=_ts(), message="m")

    path = JSONFileHandler().write(commit, tmp_path / "out.json")

    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    assert parsed["sha"] == "x"


def test_write_passes_through_plain_dicts_and_lists(tmp_path: Path):
    """Non-JSONModel JSON-serializable values should round-trip unchanged."""
    payload = {"a": 1, "b": [2, 3]}

    path = JSONFileHandler().write(payload, tmp_path / "out.json")

    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_write_empty_list_writes_empty_array(tmp_path: Path):
    """Empty list should produce `[]` — still valid JSON, unlike CSV's empty file."""
    path = JSONFileHandler().write([], tmp_path / "out.json")

    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_write_returns_the_written_path(tmp_path: Path):
    """write() should return the same path it was given."""
    target = tmp_path / "out.json"
    assert JSONFileHandler().write([], target) == target


def test_read_returns_the_raw_parsed_value(tmp_path: Path):
    """read() returns whatever json.loads gives — no model reconstruction."""
    target = tmp_path / "in.json"
    target.write_text('{"username": "alice", "count": 3}', encoding="utf-8")

    assert JSONFileHandler().read(target) == {"username": "alice", "count": 3}


def test_write_then_read_round_trip(tmp_path: Path):
    """A value written by the handler should be readable by the handler unchanged (modulo to_jsonable conversion)."""
    handler = JSONFileHandler()
    commit = Commit(sha="x", repo="o/r", authored_at=_ts(), message="m")

    path = handler.write(commit, tmp_path / "round_trip.json")
    out = handler.read(path)

    assert out["sha"] == "x"
    assert out["authored_at"] == "2026-05-12T00:00:00+00:00"
