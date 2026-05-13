"""Serialize reports to disk."""

import json
from pathlib import Path

from .models import AuthorshipReport, to_jsonable


def write_report(report: AuthorshipReport, out_dir: Path) -> Path:
    """Write a report to `<out_dir>/<username>.json`, creating the dir if needed.

    Returns the path written. Existing files are overwritten.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.username}.json"
    path.write_text(json.dumps(to_jsonable(report), indent=2), encoding="utf-8")
    return path
