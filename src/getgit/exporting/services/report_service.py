"""Orchestrates writing an `AuthorshipReport` to disk via the writers."""

from datetime import datetime
from pathlib import Path

from ...github import AuthorshipReport, Commit, GithubScrapeResult
from ..csv_writer import CsvWriter
from ..json_file_handler import JSONFileHandler


class ReportService:
    """Writes an `AuthorshipReport` as one JSON and one CSV per top-level collection.

    Owns one `JSONFileHandler` and one `CsvWriter` and dispatches to
    them per collection. Keeping this as a class (vs. a free function)
    makes it trivial to swap the writer pair later — phase 2 might
    inject a `ParquetWriter`, etc.
    """

    def write_report(
        self,
        username: str,
        commits: list[Commit],
        pr_result: GithubScrapeResult,
        out_dir: Path,
        *,
        generated_at: datetime,
    ) -> dict[str, Path]:
        """Assemble the report from the scrape pieces and write it to disk.

        The only `ReportService` method the orchestrator calls: it
        assembles an `AuthorshipReport` from `commits` + `pr_result`
        (stamped with the caller-supplied `generated_at`) and writes
        each top-level collection as both JSON and CSV.

        Files land in a per-run subdirectory:
        `<out_dir>/<username>/<generated_at>/<collection>.{json,csv}`.
        The timestamp uses `%Y-%m-%d_T%H-%M-%S` (hyphens, no colons) so
        the path is valid on every filesystem we care about. The
        username + timestamp in the path captures the metadata that
        used to live at the top of the unified JSON.

        Returns a dict of `{label: path}` for everything written.
        Existing files in the same per-run directory are overwritten.
        """
        report = self._generate_report(
            username, commits, pr_result, generated_at=generated_at
        )

        base_dir = out_dir / report.username / report.generated_at.strftime(
            "%Y-%m-%d_T%H-%M-%S"
        )
        base_dir.mkdir(parents=True, exist_ok=True)

        csv_writer = CsvWriter()
        json_handler = JSONFileHandler()

        collections = {
            "commits": report.commits,
            "authored_pull_requests": report.authored_pull_requests,
            "participated_pull_requests": report.participated_pull_requests,
            "reviews": report.reviews,
        }

        paths: dict[str, Path] = {}
        for name, items in collections.items():
            paths[f"{name}_json"] = json_handler.write(items, base_dir / f"{name}.json")
            paths[f"{name}_csv"] = csv_writer.write(items, base_dir / f"{name}.csv")
        return paths

    def _generate_report(
        self,
        username: str,
        commits: list[Commit],
        pr_result: GithubScrapeResult,
        *,
        generated_at: datetime,
    ) -> AuthorshipReport:
        """Assemble an `AuthorshipReport` from the collected scrape pieces.

        Flattens a `GithubScrapeResult` into the report's separate
        authored / participated / reviews collections. `generated_at`
        is supplied by the caller so the report's timestamp matches the
        run's own clock rather than the moment of assembly.
        """
        return AuthorshipReport(
            username=username,
            generated_at=generated_at,
            commits=commits,
            authored_pull_requests=pr_result.authored,
            participated_pull_requests=pr_result.participated,
            reviews=pr_result.reviews,
        )
