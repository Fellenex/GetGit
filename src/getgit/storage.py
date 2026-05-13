"""Serialize reports to disk as JSON and CSV."""

import csv
import json
from dataclasses import fields
from pathlib import Path

from .models import AuthorshipReport, JSONModel


def write_report(report: AuthorshipReport, out_dir: Path) -> dict[str, Path]:
    """Write the full report to `out_dir` as JSON plus one CSV per row-shaped collection.

    Returns a dict of `{format_label: path}` for everything written.
    Existing files are overwritten.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    base = report.username
    paths: dict[str, Path] = {}

    json_path = out_dir / f"{base}.json"
    json_path.write_text(json.dumps(report.to_jsonable(), indent=2), encoding="utf-8")
    paths["json"] = json_path

    paths["commits_csv"] = _write_csv(report.commits, out_dir / f"{base}.commits.csv")
    paths["authored_pull_requests_csv"] = _write_csv(
        report.authored_pull_requests, out_dir / f"{base}.authored_pull_requests.csv"
    )
    paths["participated_pull_requests_csv"] = _write_csv(
        report.participated_pull_requests,
        out_dir / f"{base}.participated_pull_requests.csv",
    )
    paths["reviews_csv"] = _write_csv(report.reviews, out_dir / f"{base}.reviews.csv")
    return paths


def _flatten_for_csv(value: object) -> object:
    """Coerce a JSON-safe value into a CSV cell.

    Lists become `;`-joined strings. Dicts become `key:value` pairs
    `;`-joined and key-sorted for determinism — when a value is itself
    a list, its members are joined with `|` so the outer `;` remains
    unambiguous (e.g. `WD:WD-1|WD-2;YWFB:YWFB-9`). Other values pass
    through untouched.
    """
    if isinstance(value, list):
        return ";".join(map(str, value))
    if isinstance(value, dict):
        return ";".join(f"{k}:{_inner(value[k])}" for k in sorted(value))
    return value


def _inner(value: object) -> str:
    """Render a dict value: lists get `|`-joined, scalars stringify."""
    if isinstance(value, list):
        return "|".join(map(str, value))
    return str(value)


def _write_csv(rows: list[JSONModel], path: Path) -> Path:
    """Write a list of homogeneous JSONModel rows to `path`.

    Columns come from the dataclass field order. List- and dict-valued
    fields are flattened via `_flatten_for_csv`. Empty input writes an
    empty file because we can't infer the column set without a row.
    """
    if not rows:
        path.write_text("", encoding="utf-8", newline="")
        return path

    fieldnames = [f.name for f in fields(rows[0])]
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            data = row.to_jsonable()
            writer.writerow({k: _flatten_for_csv(v) for k, v in data.items()})
    return path
