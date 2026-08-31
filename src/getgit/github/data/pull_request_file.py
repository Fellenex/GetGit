"""GitHub pull-request file response object."""

from dataclasses import dataclass


@dataclass
class PullRequestFile:
    """One changed file as returned by `/repos/{repo}/pulls/{number}/files`.

    A wire-shape response object. `GithubProvider` aggregates these into
    the per-extension additions/deletions breakdown; the extension
    bucketing and zero-entry omission are its business, not this
    object's.
    """

    filename: str
    additions: int
    deletions: int
