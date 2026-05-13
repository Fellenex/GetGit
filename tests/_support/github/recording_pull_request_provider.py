"""Test double for `PullRequestProvider` — records call args."""

from getgit.github import PullRequestFetchResult


class RecordingPullRequestProvider:
    """Records the args of the last `fetch` call; returns an empty result."""

    def __init__(self):
        """Initialize with no recorded call yet."""
        self.last_call: dict | None = None

    def fetch(self, username, limit, fetch_extensions) -> PullRequestFetchResult:
        """Record the call and return an empty `PullRequestFetchResult`."""
        self.last_call = {
            "username": username,
            "limit": limit,
            "fetch_extensions": fetch_extensions,
        }
        return PullRequestFetchResult()
