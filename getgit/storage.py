import json
from pathlib import Path

from .models import AuthorshipReport, to_jsonable


def write_report(report: AuthorshipReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.username}.json"
    path.write_text(json.dumps(to_jsonable(report), indent=2), encoding="utf-8")
    return path
