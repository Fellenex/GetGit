"""JSON file reader/writer with `JSONModel` awareness."""

import json
from pathlib import Path
from typing import Any

from ..infrastructure.data import JSONModel


class JSONFileHandler:
    """Reads and writes JSON files; flattens `JSONModel` payloads via `to_jsonable()`.

    Distinct from the `Writer` protocol because its `write` accepts any
    JSON-serializable shape (a single `JSONModel`, a list of them, or a
    plain dict/list/scalar) — not just the row-shaped `list[JSONModel]`
    a `Writer` operates on. `read` returns the raw parsed value;
    structuring it back into a model is the caller's job.
    """

    def write(self, data: Any, filename: Path) -> Path:
        """Serialize `data` to `filename` as JSON. Returns the path written.

        `JSONModel` instances (and lists thereof) are flattened via
        their `to_jsonable()` method. Plain dicts/lists/scalars pass
        through untouched.
        """
        filename.write_text(
            json.dumps(self._jsonable(data), indent=2), encoding="utf-8"
        )
        return filename

    def read(self, filename: Path) -> Any:
        """Read and parse `filename` as JSON. Returns the raw parsed value."""
        return json.loads(filename.read_text(encoding="utf-8"))

    @staticmethod
    def _jsonable(data: Any) -> Any:
        """Coerce `data` into a JSON-serializable form, unwrapping `JSONModel`s."""
        if isinstance(data, JSONModel):
            return data.to_jsonable()
        if isinstance(data, list):
            return [
                item.to_jsonable() if isinstance(item, JSONModel) else item
                for item in data
            ]
        return data
