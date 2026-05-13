"""Tests for the Writer protocol — both concrete writers must satisfy its shape."""

import inspect

from getgit.exporting import CsvWriter, JsonWriter, Writer


def test_csv_writer_has_write_method():
    """CsvWriter should expose a `write(items, filename)` method."""
    assert hasattr(CsvWriter, "write")
    sig = inspect.signature(CsvWriter.write)
    # self + items + filename
    assert list(sig.parameters) == ["self", "items", "filename"]


def test_json_writer_has_write_method():
    """JsonWriter should expose a `write(items, filename)` method."""
    assert hasattr(JsonWriter, "write")
    sig = inspect.signature(JsonWriter.write)
    assert list(sig.parameters) == ["self", "items", "filename"]


def test_writer_protocol_declares_write():
    """The Writer protocol must declare a `write` method (the contract)."""
    assert hasattr(Writer, "write")
