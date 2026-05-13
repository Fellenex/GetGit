"""Serialize reports to disk as JSON and CSV."""

import csv
import json
from dataclasses import fields
from pathlib import Path

from .models import AuthorshipReport, JSONModel


def write_report(report: AuthorshipReport, out_dir: Path) -> dict[str, Path]:
    """Write the full report to `out_dir` as JSON plus one CSV per row-shaped model.

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
    paths["pull_requests_csv"] = _write_csv(
        report.pull_requests, out_dir / f"{base}.pull_requests.csv"
    )
    return paths


def _write_csv(rows: list[JSONModel], path: Path) -> Path:
    """Write a list of homogeneous JSONModel rows to `path`.

    Columns come from the dataclass field order. List-valued fields are
    joined with `;` (JIRA codes never contain semicolons, so this is
    lossless and avoids CSV-quoting headaches). Empty input still writes
    a header row inferred from the row type — but if `rows` is empty we
    can't infer the type, so we write an empty file.
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
            for key, value in list(data.items()):
                if isinstance(value, list):
                    data[key] = ";".join(map(str, value))
            writer.writerow(data)
    return path
