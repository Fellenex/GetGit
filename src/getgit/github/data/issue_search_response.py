"""GitHub issue-search response object."""

from dataclasses import dataclass


@dataclass
class IssueSearchResponse:
    """One hit from GitHub's `/search/issues` endpoint.

    A wire-shape response object carrying the two fields we consume: the
    `owner/name` repo slug and the PR number. `GithubClient` performs the
    `repository_url` → `owner/name` conversion so that knowledge of the
    search envelope (`items`, `repository_url`) never leaves the client.
    """

    repo_full_name: str
    number: int
