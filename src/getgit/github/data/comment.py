"""GitHub comment response object (issue comments and PR review comments)."""

from dataclasses import dataclass


@dataclass
class Comment:
    """One comment from either PR comment stream.

    Covers both `/repos/{repo}/issues/{n}/comments` and
    `/repos/{repo}/pulls/{n}/comments` — the two streams share the only
    field we consume, the author's login. `GithubProvider` counts the
    comments whose `author_login` matches the target user.
    """

    author_login: str | None
