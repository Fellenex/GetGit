"""Tests for CsvWriter."""

from datetime import datetime, timezone
from pathlib import Path

from getgit.exporting import CsvWriter
from getgit.models import Commit, PullRequest, Review


def _ts() -> datetime:
    return datetime(2026, 5, 12, tzinfo=timezone.utc)


def test_writes_header_and_rows_in_field_order(tmp_path: Path):
    """Columns should match the dataclass field declaration order."""
    rows = [Commit(sha="abc", repo="o/r", authored_at=_ts(), message="m", pull_request_number=42)]

    path = CsvWriter().write(rows, tmp_path / "out.csv")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "sha,repo,authored_at,message,pull_request_number"
    assert lines[1] == "abc,o/r,2026-05-12T00:00:00+00:00,m,42"


def test_dict_of_scalars_renders_as_key_value_pairs(tmp_path: Path):
    """`{".py": 10, ".yml": 5}` should render as `.py:10;.yml:5` (key-sorted)."""
    rows = [
        PullRequest(
            number=1, repo="o/r", title="t", merged=True,
            created_at=_ts(), closed_at=_ts(),
            additions={".py": 10, ".yml": 5}, deletions={},
            comments=0, comments_by_author=0, jira_codes={},
        )
    ]

    path = CsvWriter().write(rows, tmp_path / "out.csv")

    line = path.read_text(encoding="utf-8").splitlines()[1]
    assert ".py:10;.yml:5" in line


def test_dict_of_lists_uses_pipe_for_inner_separator(tmp_path: Path):
    """`{"WD": ["WD-1", "WD-2"]}` should render as `WD:WD-1|WD-2`."""
    rows = [
        PullRequest(
            number=1, repo="o/r", title="t", merged=True,
            created_at=_ts(), closed_at=_ts(),
            additions={}, deletions={}, comments=0, comments_by_author=0,
            jira_codes={"WD": ["WD-1", "WD-2"], "YWFB": ["YWFB-9"]},
        )
    ]

    path = CsvWriter().write(rows, tmp_path / "out.csv")

    line = path.read_text(encoding="utf-8").splitlines()[1]
    assert "WD:WD-1|WD-2" in line
    assert "YWFB:YWFB-9" in line


def test_empty_input_writes_empty_file(tmp_path: Path):
    """Empty list → empty file (we can't infer columns without a row)."""
    path = CsvWriter().write([], tmp_path / "out.csv")

    assert path.read_text(encoding="utf-8") == ""


def test_returns_the_written_path(tmp_path: Path):
    """write() should return the same path it was given."""
    target = tmp_path / "out.csv"
    rows = [Review(pr_repo="o/r", pr_number=1, index=1, state="COMMENTED", submitted_at=_ts(), body="")]

    assert CsvWriter().write(rows, target) == target
