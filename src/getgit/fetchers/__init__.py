"""Fetchers domain — per-resource scrapers that talk to the GitHub API."""

from .commit_fetcher import CommitFetcher
from .data import PullRequestFetchResult
from .pull_request_fetcher import PullRequestFetcher
from .repo_fetcher import RepoFetcher

__all__ = [
    "CommitFetcher",
    "PullRequestFetcher",
    "PullRequestFetchResult",
    "RepoFetcher",
]
