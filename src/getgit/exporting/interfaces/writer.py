"""The `Writer` protocol — abstract interface every exporter implements."""

from pathlib import Path
from typing import Protocol

from ...infrastructure.data import JSONModel


class Writer(Protocol):
    """Serializes a list of homogeneous `JSONModel` rows to a single file.

    Implementations decide the on-disk format (CSV, JSON, etc.). The
    orchestrator is responsible for picking the filename and the
    collection — the writer just renders.
    """

    def write(self, items: list[JSONModel], filename: Path) -> Path:
        """Serialize `items` to `filename`. Returns the path written."""
        ...
