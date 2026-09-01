"""GitHub pull-request changed-file wire-shape object."""

from dataclasses import dataclass


@dataclass
class GithubPullRequestChangedFile:
    """One changed file as returned by `/repos/{repo}/pulls/{number}/files`.

    A wire-shape object. `GithubMapper` aggregates these into the
    per-extension additions/deletions breakdown; the extension bucketing
    and zero-entry omission are its business, not this object's.
    """

    filename: str
    additions: int
    deletions: int
