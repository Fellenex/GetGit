"""Reads and writes the per-username checkpoint at `output/<username>/state.json`."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .data import Checkpoint


class CheckpointStore:
    """File-backed store for one user's `Checkpoint`.

    The file lives at `<out_dir>/<username>/state.json` — sibling to the
    per-run timestamped output subdirectories so `output/<username>/`
    holds both the watermark and the run history side-by-side.
    """

    def __init__(self, out_dir: Path, username: str):
        """Resolve the on-disk location for this user's checkpoint."""
        self._path = out_dir / username / "state.json"

    def load(self) -> Checkpoint:
        """Return the saved checkpoint, or an empty one if none exists yet."""
        if not self._path.exists():
            return Checkpoint()
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return Checkpoint(
            pr_search_updated_since=self._parse_dt(raw.get("pr_search_updated_since")),
            commits_per_repo={
                repo: self._parse_dt(ts)
                for repo, ts in (raw.get("commits_per_repo") or {}).items()
                if ts
            },
            last_run_at=self._parse_dt(raw.get("last_run_at")),
            last_run_status=raw.get("last_run_status", "never"),
        )

    def save(self, checkpoint: Checkpoint) -> Path:
        """Serialize the checkpoint to disk and return the path written."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._jsonable(checkpoint)
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self._path

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        """Parse an ISO-8601 string back into a datetime, tolerating None."""
        if not value:
            return None
        return datetime.fromisoformat(value)

    @staticmethod
    def _jsonable(checkpoint: Checkpoint) -> dict:
        """Render the dataclass with datetimes flattened to ISO strings."""
        data = asdict(checkpoint)
        if checkpoint.pr_search_updated_since:
            data["pr_search_updated_since"] = checkpoint.pr_search_updated_since.isoformat()
        if checkpoint.last_run_at:
            data["last_run_at"] = checkpoint.last_run_at.isoformat()
        data["commits_per_repo"] = {
            repo: ts.isoformat() for repo, ts in checkpoint.commits_per_repo.items()
        }
        return data
