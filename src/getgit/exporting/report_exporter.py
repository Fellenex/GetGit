"""Orchestrates writing an `AuthorshipReport` to disk via the `Writer` protocol."""

from pathlib import Path

from ..models import AuthorshipReport
from .csv_writer import CsvWriter
from .json_writer import JsonWriter


def write_report(report: AuthorshipReport, out_dir: Path) -> dict[str, Path]:
    """Write each top-level collection in `report` as both JSON and CSV.

    Output filenames are `<username>.<collection>.<format>`. Returns a
    dict of `{label: path}` for everything written. Existing files are
    overwritten.

    Top-level metadata (`username`, `generated_at`) is implicit in the
    filenames and the file mtimes — there is intentionally no unified
    `<username>.json` aggregating everything; consumers wanting that
    shape can join the per-collection files themselves.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    base = report.username
    csv_writer = CsvWriter()
    json_writer = JsonWriter()

    collections = {
        "commits": report.commits,
        "authored_pull_requests": report.authored_pull_requests,
        "participated_pull_requests": report.participated_pull_requests,
        "reviews": report.reviews,
    }

    paths: dict[str, Path] = {}
    for name, items in collections.items():
        paths[f"{name}_json"] = json_writer.write(
            items, out_dir / f"{base}.{name}.json"
        )
        paths[f"{name}_csv"] = csv_writer.write(
            items, out_dir / f"{base}.{name}.csv"
        )
    return paths
