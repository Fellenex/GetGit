"""Test double for `CommitProvider` — records call args."""


class RecordingCommitProvider:
    """Records the args of the last `fetch` call; returns an empty list."""

    def __init__(self):
        """Initialize with no recorded call yet."""
        self.last_call: dict | None = None

    def fetch(self, repos, username, limit, pr_index) -> list:
        """Record the call and return an empty commit list."""
        self.last_call = {
            "repos": repos,
            "username": username,
            "limit": limit,
            "pr_index": pr_index,
        }
        return []
