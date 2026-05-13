"""Reads and writes the per-username `UserState` at `output/<username>/state.json`."""

import json
from datetime import datetime
from pathlib import Path

from .data import UserState


class UserStateStore:
    """File-backed store for one user's `UserState`.

    The file lives at `<out_dir>/<username>/state.json` — sibling to the
    per-run timestamped output subdirectories so `output/<username>/`
    holds both the watermark and the run history side-by-side. Save
    delegates to `UserState.to_jsonable()` (inherited from `JSONModel`)
    so datetime → ISO conversion is centralized in the model layer.
    """

    def __init__(self, out_dir: Path, username: str):
        """Resolve the on-disk location for this user's state."""
        self._path = out_dir / username / "state.json"

    def load(self) -> UserState:
        """Return the saved state, or an empty one if no file exists yet."""
        if not self._path.exists():
            return UserState()
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return UserState(
            pr_search_updated_since=self._parse_dt(raw.get("pr_search_updated_since")),
            commits_per_repo={
                repo: self._parse_dt(ts)
                for repo, ts in (raw.get("commits_per_repo") or {}).items()
                if ts
            },
            last_run_at=self._parse_dt(raw.get("last_run_at")),
            last_run_status=raw.get("last_run_status", "never"),
        )

    def save(self, state: UserState) -> Path:
        """Serialize the state to disk via `JSONModel.to_jsonable()` and return the path."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(state.to_jsonable(), indent=2), encoding="utf-8")
        return self._path

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        """Parse an ISO-8601 string back into a datetime, tolerating None."""
        if not value:
            return None
        return datetime.fromisoformat(value)
