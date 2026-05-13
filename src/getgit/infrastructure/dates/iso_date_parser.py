"""Single-place ISO-8601 → datetime parsing, tolerating GitHub's `Z` suffix."""

from datetime import datetime


class IsoDateParser:
    """Parses ISO-8601 timestamp strings.

    GitHub returns timestamps as `2026-05-12T10:30:00Z`; Python's stdlib
    `datetime.fromisoformat` accepts `+00:00` but historically not `Z`
    on every supported version. We normalize the `Z` away so callers
    don't have to remember which sources use which suffix.

    Stateless — exposed as a static method, but kept on a class for
    discoverability (`IsoDateParser.parse(...)` reads better than a
    bare module-level function across the codebase).
    """

    @staticmethod
    def parse(value: str | None) -> datetime | None:
        """Return a `datetime` for an ISO-8601 string, or `None` for missing input."""
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
