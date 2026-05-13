"""Orchestrates writing an `AuthorshipReport` to disk via the `Writer` protocol."""

from pathlib import Path

from ..github import AuthorshipReport
from .csv_writer import CsvWriter
from .json_writer import JsonWriter


class ReportExporter:
    """Writes an `AuthorshipReport` as one JSON and one CSV per top-level collection.

    Owns one `JsonWriter` and one `CsvWriter` and dispatches to them
    per collection. Keeping this as a class (vs. a free function) makes
    it trivial to swap the writer pair later — phase 2 might inject a
    `ParquetWriter`, etc.
    """

    def write_report(self, report: AuthorshipReport, out_dir: Path) -> dict[str, Path]:
        """Write each top-level collection in `report` as both JSON and CSV.

        Files land in a per-run subdirectory:
        `<out_dir>/<username>/<generated_at>/<collection>.{json,csv}`.
        The timestamp uses `%Y-%m-%d_T%H-%M-%S` (hyphens, no colons) so
        the path is valid on every filesystem we care about. The
        username + timestamp in the path captures the metadata that
        used to live at the top of the unified JSON.

        Returns a dict of `{label: path}` for everything written.
        Existing files in the same per-run directory are overwritten.
        """
        base_dir = out_dir / report.username / report.generated_at.strftime(
            "%Y-%m-%d_T%H-%M-%S"
        )
        base_dir.mkdir(parents=True, exist_ok=True)

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
            paths[f"{name}_json"] = json_writer.write(items, base_dir / f"{name}.json")
            paths[f"{name}_csv"] = csv_writer.write(items, base_dir / f"{name}.csv")
        return paths
