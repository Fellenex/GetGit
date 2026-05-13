"""Services domain — high-level facades that coordinate multiple fetchers."""

from .github_service import GithubService

__all__ = ["GithubService"]
