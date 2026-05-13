"""GitHub providers — per-resource scrapers built on the client."""

from .commit_provider import CommitProvider
from .pull_request_provider import PullRequestProvider
from .repo_provider import RepoProvider

__all__ = ["CommitProvider", "PullRequestProvider", "RepoProvider"]
