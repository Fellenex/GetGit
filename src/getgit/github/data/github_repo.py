"""GitHub repository wire-shape object."""

from dataclasses import dataclass


@dataclass
class GithubRepo:
    """One repository as returned by GitHub's repo-listing endpoints.

    A wire-shape object (distinct from any internal domain model) carrying
    only the field we consume downstream: `full_name`, the `owner/name`
    slug used to key commit listings and the commit→PR index.
    `GithubClient` builds these from `/user/repos` and
    `/users/{username}/repos`; nothing above the client sees the raw repo
    JSON.
    """

    full_name: str
