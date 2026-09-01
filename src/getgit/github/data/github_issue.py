"""GitHub issue wire-shape object (from the issue-search endpoint)."""

from dataclasses import dataclass


@dataclass
class GithubIssue:
    """One issue as returned by GitHub's `/search/issues` endpoint.

    A wire-shape object carrying the two fields we consume: the
    `owner/name` repo slug (normalized from the raw `repository_url` at
    the client boundary) and the issue/PR number. `GithubClient` performs
    that conversion so knowledge of the search envelope (`items`,
    `repository_url`) never leaves the client.
    """

    repo_full_name: str
    number: int
