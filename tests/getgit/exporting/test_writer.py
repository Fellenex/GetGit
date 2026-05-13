"""Tests for the Writer protocol — only `CsvWriter` is expected to conform.

`JSONFileHandler` deliberately does *not* implement `Writer` — its
`write` accepts any JSON-serializable shape, not just `list[JSONModel]`.
"""

import inspect

from getgit.exporting import CsvWriter, Writer


def test_csv_writer_has_write_method():
    """CsvWriter should expose a `write(items, filename)` method."""
    assert hasattr(CsvWriter, "write")
    sig = inspect.signature(CsvWriter.write)
    # self + items + filename
    assert list(sig.parameters) == ["self", "items", "filename"]


def test_writer_protocol_declares_write():
    """The Writer protocol must declare a `write` method (the contract)."""
    assert hasattr(Writer, "write")
