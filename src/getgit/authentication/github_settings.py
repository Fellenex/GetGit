"""Configuration for the GitHub HTTP client."""

from dataclasses import dataclass


@dataclass
class GithubSettings:
    """All knobs `GithubClient` needs to talk to GitHub.

    Separating these from the client itself means callers compose
    `GithubClient(GithubSettings(token=...))` instead of the client
    pulling secrets from the environment — the same pattern that lets
    phase 2 swap a request-scoped OAuth token in without touching the
    client class.
    """

    auth_token: str
    base_url: str = "https://api.github.com"
    timeout: float = 30.0
