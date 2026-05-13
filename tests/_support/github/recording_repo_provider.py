"""Test double for `RepoProvider` — records call args."""


class RecordingRepoProvider:
    """Records the args of the last `list_repos` call; returns a single fake repo."""

    def __init__(self):
        """Initialize with no recorded call yet."""
        self.last_call: dict | None = None

    def list_repos(self, username: str, is_self: bool) -> list[dict]:
        """Record `(username, is_self)` and return one fake repo."""
        self.last_call = {"username": username, "is_self": is_self}
        return [{"full_name": "o/r"}]
