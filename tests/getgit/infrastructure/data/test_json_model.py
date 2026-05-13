"""Tests for JSONModel — the dataclass mixin that powers `to_jsonable()`."""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from getgit.infrastructure.data import JSONModel


@dataclass
class _Sample(JSONModel):
    name: str
    when: datetime
    tags: list[str]
    extras: dict[str, int]


def test_to_jsonable_serializes_datetimes_as_iso():
    """Datetime fields render as ISO-8601 strings."""
    s = _Sample(name="x", when=datetime(2026, 5, 12, tzinfo=timezone.utc), tags=[], extras={})

    out = s.to_jsonable()

    assert out["when"] == "2026-05-12T00:00:00+00:00"


def test_to_jsonable_walks_lists_and_dicts():
    """Containers recurse so any nested datetimes/dataclasses get converted."""
    s = _Sample(name="x", when=datetime(2026, 1, 1), tags=["a", "b"], extras={"k": 1})

    out = s.to_jsonable()

    assert out["tags"] == ["a", "b"]
    assert out["extras"] == {"k": 1}


def test_to_jsonable_walks_nested_jsonmodel_instances():
    """A JSONModel containing another JSONModel should serialize the inner one too."""

    @dataclass
    class _Outer(JSONModel):
        inner: _Sample

    inner = _Sample(name="i", when=datetime(2026, 1, 1), tags=[], extras={})
    outer = _Outer(inner=inner)

    out = outer.to_jsonable()

    assert out == {"inner": {"name": "i", "when": "2026-01-01T00:00:00", "tags": [], "extras": {}}}


def test_to_jsonable_on_non_dataclass_raises():
    """Subclassing JSONModel without `@dataclass` is a programming error."""

    class _Bare(JSONModel):
        pass

    with pytest.raises(TypeError, match="not a @dataclass"):
        _Bare().to_jsonable()
