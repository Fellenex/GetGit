"""Repository (file-backed) for the per-username `UserState`."""

from datetime import datetime
from pathlib import Path

from ..exporting import JSONFileHandler
from .data import UserState


class UserStateRepository:
    """File-backed repository for one user's `UserState`.

    The file lives at `<out_dir>/<username>/state.json` — sibling to the
    per-run timestamped output subdirectories so `output/<username>/`
    holds both the watermark and the run history side-by-side. Delegates
    JSON I/O to a `JSONFileHandler` (constructor-injected) so the JSON-
    serialization seam stays in one place; this class is responsible
    only for path resolution and `UserState` ↔ raw-dict marshaling.
    """

    def __init__(self, out_dir: Path, username: str, json_handler: JSONFileHandler):
        """Resolve this user's state path and bind the JSON handler."""
        self._path = out_dir / username / "state.json"
        self._json_handler = json_handler

    def load(self) -> UserState:
        """Return the saved state, or an empty one if no file exists yet.

        Reads the raw JSON via the handler and reconstructs a
        `UserState` from it (handling `datetime` parsing because
        `JSONModel.to_jsonable()` is one-way).
        """
        if not self._path.exists():
            return UserState()
        raw = self._json_handler.read(self._path)
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
        """Persist the state via the handler. Returns the path written."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        return self._json_handler.write(state, self._path)

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        """Parse an ISO-8601 string back into a datetime, tolerating None."""
        if not value:
            return None
        return datetime.fromisoformat(value)
