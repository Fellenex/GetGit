"""JSON implementation of the `Writer` protocol."""

import json
from pathlib import Path

from ..models import JSONModel


class JsonWriter:
    """Writes a list of `JSONModel` rows as a JSON array.

    Each row is serialized via its own `to_jsonable()` so nested
    datetimes/dataclasses/dicts render correctly. Empty input writes a
    `[]` (still valid JSON) — diverges from `CsvWriter`, which writes
    an empty file because it can't infer columns without a row.
    """

    def write(self, items: list[JSONModel], filename: Path) -> Path:
        """Serialize `items` to `filename`. Returns the path written."""
        payload = [item.to_jsonable() for item in items]
        filename.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return filename
