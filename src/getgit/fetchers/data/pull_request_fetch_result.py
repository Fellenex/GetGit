"""Result struct produced by `fetch_pull_requests`."""

from dataclasses import dataclass, field

from ...models import PullRequest, Review


@dataclass
class PullRequestFetchResult:
    """Bundle of everything one PR-side scrape produces.

    `authored` and `participated` partition the PRs the user touched.
    `reviews` is every review the user submitted on either set.
    `commit_pr_index` maps `(repo, commit_sha)` → PR number for any
    commit reachable from any of these PRs.
    """

    authored: list[PullRequest] = field(default_factory=list)
    participated: list[PullRequest] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    commit_pr_index: dict[tuple[str, str], int] = field(default_factory=dict)
