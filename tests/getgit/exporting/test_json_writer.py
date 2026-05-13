"""Tests for JsonWriter."""

import json
from datetime import datetime, timezone
from pathlib import Path

from getgit.exporting import JsonWriter
from getgit.models import Commit


def _ts() -> datetime:
    return datetime(2026, 5, 12, tzinfo=timezone.utc)


def test_writes_a_json_array_of_jsonable_rows(tmp_path: Path):
    """Each row is rendered through its own to_jsonable; output is a top-level list."""
    rows = [
        Commit(sha="a", repo="o/r", authored_at=_ts(), message="m1"),
        Commit(sha="b", repo="o/r", authored_at=_ts(), message="m2", pull_request_number=7),
    ]

    path = JsonWriter().write(rows, tmp_path / "out.json")

    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, list)
    assert parsed[0]["sha"] == "a"
    assert parsed[1]["pull_request_number"] == 7
    assert parsed[0]["authored_at"] == "2026-05-12T00:00:00+00:00"


def test_empty_input_writes_empty_array(tmp_path: Path):
    """Empty list should produce `[]` — still valid JSON, unlike CSV's empty file."""
    path = JsonWriter().write([], tmp_path / "out.json")

    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_returns_the_written_path(tmp_path: Path):
    """write() should return the same path it was given."""
    target = tmp_path / "out.json"
    assert JsonWriter().write([], target) == target
