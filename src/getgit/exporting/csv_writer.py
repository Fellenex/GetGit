"""CSV implementation of the `Writer` protocol."""

import csv
from dataclasses import fields
from pathlib import Path

from ..models import JSONModel


class CsvWriter:
    """Writes a list of homogeneous `JSONModel` rows as CSV.

    Columns come from `dataclasses.fields()` in declaration order. List-
    and dict-valued cells are flattened via `_flatten_for_csv` so the
    output round-trips through a single cell. Empty input writes an
    empty file because there's no row from which to infer columns.
    """

    def write(self, items: list[JSONModel], filename: Path) -> Path:
        """Serialize `items` to `filename`. Returns the path written."""
        if not items:
            filename.write_text("", encoding="utf-8", newline="")
            return filename

        fieldnames = [f.name for f in fields(items[0])]
        with filename.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            for row in items:
                data = row.to_jsonable()
                writer.writerow({k: self._flatten_for_csv(v) for k, v in data.items()})
        return filename

    @staticmethod
    def _flatten_for_csv(value: object) -> object:
        """Coerce a JSON-safe value into a CSV cell.

        Lists become `;`-joined strings. Dicts become `key:value` pairs
        `;`-joined and key-sorted for determinism — when a value is
        itself a list, its members are joined with `|` so the outer `;`
        remains unambiguous (e.g. `WD:WD-1|WD-2;YWFB:YWFB-9`). Other
        values pass through untouched.
        """
        if isinstance(value, list):
            return ";".join(map(str, value))
        if isinstance(value, dict):
            return ";".join(
                f"{k}:{CsvWriter._inner(value[k])}" for k in sorted(value)
            )
        return value

    @staticmethod
    def _inner(value: object) -> str:
        """Render a dict value: lists get `|`-joined, scalars stringify."""
        if isinstance(value, list):
            return "|".join(map(str, value))
        return str(value)
