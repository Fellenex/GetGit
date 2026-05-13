"""Support classes for GitHub-domain tests."""

from .erroring_github_client import ErroringGithubClient
from .fake_github_client import FakeGithubClient
from .fake_http import FakeHttp
from .fake_response import FakeResponse
from .recording_commit_provider import RecordingCommitProvider
from .recording_pull_request_provider import RecordingPullRequestProvider
from .recording_repo_provider import RecordingRepoProvider

__all__ = [
    "ErroringGithubClient",
    "FakeGithubClient",
    "FakeHttp",
    "FakeResponse",
    "RecordingCommitProvider",
    "RecordingPullRequestProvider",
    "RecordingRepoProvider",
]
