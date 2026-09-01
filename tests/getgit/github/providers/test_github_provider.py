"""Tests for GithubProvider — raw response objects → domain objects, and the error contract."""

from datetime import datetime, timezone
from unittest.mock import Mock

import httpx
import pytest

from getgit.github import (
    GithubClient,
    GithubComment,
    GithubCommit,
    GithubIssue,
    GithubProvider,
    GithubPullRequest,
    GithubPullRequestChangedFile,
    GithubRepo,
    GithubReview,
    PullRequestFetchResult,
    RateLimitExceededError,
    RepositoryAccessError,
)

_DT = datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    """Build a real `httpx.HTTPStatusError` carrying a response of `status`."""
    request = httpx.Request("GET", "/x")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"{status}", request=request, response=response)


def _detail(**overrides) -> GithubPullRequest:
    """Build a GithubPullRequest with sensible defaults for hydration tests."""
    base = dict(
        title="t",
        body=None,
        merged_at=None,
        created_at=_DT,
        closed_at=_DT,
        updated_at=_DT,
        additions=0,
        deletions=0,
        comments=0,
        review_comments=0,
    )
    base.update(overrides)
    return GithubPullRequest(**base)


def _payload(sha: str) -> GithubCommit:
    """Build a GithubCommit for commit-walk tests."""
    return GithubCommit(sha=sha, authored_at=_DT, message=f"msg {sha}")


# --- list_repos ---------------------------------------------------------------


def test_list_repos_self_uses_list_own_repos():
    """is_self=True delegates to the client's own-repos endpoint."""
    client = Mock(spec=GithubClient)
    client.list_own_repos.return_value = [GithubRepo("me/r"), GithubRepo("org/x")]

    out = GithubProvider(client).list_repos("me", is_self=True)

    assert out == [GithubRepo("me/r"), GithubRepo("org/x")]
    client.list_own_repos.assert_called_once_with()


def test_list_repos_stranger_uses_list_user_repos():
    """is_self=False delegates to the client's user-repos endpoint with the username."""
    client = Mock(spec=GithubClient)
    client.list_user_repos.return_value = [GithubRepo("alice/r")]

    GithubProvider(client).list_repos("alice", is_self=False)

    client.list_user_repos.assert_called_once_with("alice")


def test_list_repos_rate_limit_attaches_partial():
    """A rate limit surfaces with a (list-typed) partial attached."""
    client = Mock(spec=GithubClient)
    client.list_own_repos.side_effect = RateLimitExceededError("too many")

    with pytest.raises(RateLimitExceededError) as excinfo:
        GithubProvider(client).list_repos("me", is_self=True)

    assert excinfo.value.partial == []


# --- fetch_pull_requests (integration through hydration) ----------------------


def test_fetch_pull_requests_hydrates_authored_pr_end_to_end():
    """One authored PR: merged flag, comment sum, self-comment count, jira, reviews, index."""
    client = Mock(spec=GithubClient)
    client.search_issues.side_effect = (
        lambda q: [GithubIssue("o/r", 1)] if "author:alice" in q else []
    )
    client.get_pull_request.return_value = _detail(
        title="WD-1 add thing",
        body="relates to WD-2",
        merged_at=_DT,
        additions=10,
        deletions=2,
        comments=3,
        review_comments=4,
    )
    client.list_issue_comments.return_value = [GithubComment("alice"), GithubComment("bob")]
    client.list_review_comments.return_value = [GithubComment("alice")]
    client.list_pull_request_reviews.return_value = [
        GithubReview("alice", "APPROVED", _DT, "lgtm"),
        GithubReview("bob", "COMMENTED", _DT, "hmm"),
    ]
    client.list_pull_request_commits.return_value = ["sha1", "sha2"]

    out = GithubProvider(client).fetch_pull_requests("alice", fetch_extensions=False)

    assert len(out.authored) == 1
    pr = out.authored[0]
    assert pr.merged is True
    assert pr.comments == 7
    assert pr.comments_by_author == 2
    assert pr.additions == {"*": 10}
    assert pr.deletions == {"*": 2}
    assert pr.jira_codes == ["WD-1", "WD-2"]
    assert out.participated == []
    # Only the target user's review is kept, with a 1-based per-PR index.
    assert len(out.reviews) == 1
    assert out.reviews[0].index == 1
    assert out.reviews[0].state == "APPROVED"
    assert out.commit_pr_index == {("o/r", "sha1"): 1, ("o/r", "sha2"): 1}


def test_fetch_pull_requests_excludes_authored_from_participated():
    """A PR that is both authored and a participation hit stays only in authored."""
    client = Mock(spec=GithubClient)
    client.search_issues.side_effect = lambda q: [GithubIssue("o/r", 1)]
    client.get_pull_request.return_value = _detail()
    client.list_issue_comments.return_value = []
    client.list_review_comments.return_value = []
    client.list_pull_request_reviews.return_value = []
    client.list_pull_request_commits.return_value = []

    out = GithubProvider(client).fetch_pull_requests("alice", fetch_extensions=False)

    assert [pr.number for pr in out.authored] == [1]
    assert out.participated == []


def test_fetch_pull_requests_open_pr_is_not_merged():
    """A PR with no merged_at hydrates as merged=False."""
    client = Mock(spec=GithubClient)
    client.search_issues.side_effect = (
        lambda q: [GithubIssue("o/r", 2)] if "author:alice" in q else []
    )
    client.get_pull_request.return_value = _detail(merged_at=None)
    client.list_issue_comments.return_value = []
    client.list_review_comments.return_value = []
    client.list_pull_request_reviews.return_value = []
    client.list_pull_request_commits.return_value = []

    out = GithubProvider(client).fetch_pull_requests("alice", fetch_extensions=False)

    assert out.authored[0].merged is False


def test_fetch_pull_requests_rate_limit_attaches_partial_result():
    """A rate limit mid-fetch attaches a (possibly empty) PullRequestFetchResult."""
    client = Mock(spec=GithubClient)
    client.search_issues.side_effect = RateLimitExceededError("too many")

    with pytest.raises(RateLimitExceededError) as excinfo:
        GithubProvider(client).fetch_pull_requests("alice")

    assert isinstance(excinfo.value.partial, PullRequestFetchResult)
    assert excinfo.value.partial.authored == []
    assert excinfo.value.partial.participated == []


def test_scoped_search_422_becomes_repository_access_error():
    """A 422 from a `--repo`-scoped search surfaces as a clean domain error."""
    client = Mock(spec=GithubClient)
    client.search_issues.side_effect = _http_status_error(422)

    with pytest.raises(RepositoryAccessError) as excinfo:
        GithubProvider(client).fetch_pull_requests(
            "alice", target_repo="octocat/hello-world"
        )

    assert excinfo.value.repo == "octocat/hello-world"


def test_422_without_target_repo_is_not_swallowed():
    """Without a repo scope, a 422 isn't the authorization case — re-raise it raw."""
    client = Mock(spec=GithubClient)
    client.search_issues.side_effect = _http_status_error(422)

    with pytest.raises(httpx.HTTPStatusError):
        GithubProvider(client).fetch_pull_requests("alice")


def test_non_422_status_error_is_reraised_even_when_scoped():
    """Other HTTP errors (e.g. 500) propagate unchanged, not as access errors."""
    client = Mock(spec=GithubClient)
    client.search_issues.side_effect = _http_status_error(500)

    with pytest.raises(httpx.HTTPStatusError):
        GithubProvider(client).fetch_pull_requests(
            "alice", target_repo="octocat/hello-world"
        )


# --- fetch_commits ------------------------------------------------------------


def test_fetch_commits_walks_each_repo_and_returns_commits():
    """A commit per repo is returned with sha/repo populated."""
    client = Mock(spec=GithubClient)
    client.list_repo_commits.side_effect = lambda full_name, author, since=None: {
        "o/r1": [_payload("a")],
        "o/r2": [_payload("b"), _payload("c")],
    }[full_name]
    repos = [GithubRepo("o/r1"), GithubRepo("o/r2")]

    out = GithubProvider(client).fetch_commits(repos, "alice")

    assert [c.sha for c in out] == ["a", "b", "c"]
    assert out[0].repo == "o/r1"
    assert out[1].repo == "o/r2"


def test_fetch_commits_attaches_pull_request_number_from_index():
    """Commits in the pr_index get their PR number; others stay None."""
    client = Mock(spec=GithubClient)
    client.list_repo_commits.return_value = [_payload("a"), _payload("b")]

    out = GithubProvider(client).fetch_commits(
        [GithubRepo("o/r")], "alice", pr_index={("o/r", "a"): 42}
    )

    assert out[0].pull_request_number == 42
    assert out[1].pull_request_number is None


def test_fetch_commits_respects_limit():
    """`limit` stops iteration once N commits have been collected."""
    client = Mock(spec=GithubClient)
    client.list_repo_commits.return_value = [_payload(s) for s in "abcde"]

    out = GithubProvider(client).fetch_commits([GithubRepo("o/r")], "alice", limit=2)

    assert [c.sha for c in out] == ["a", "b"]


def test_fetch_commits_passes_since_watermark_per_repo():
    """A per-repo watermark is forwarded to the client as the `since` arg."""
    client = Mock(spec=GithubClient)
    client.list_repo_commits.return_value = []
    watermark = datetime(2026, 1, 1, tzinfo=timezone.utc)

    GithubProvider(client).fetch_commits(
        [GithubRepo("o/r")], "alice", since_per_repo={"o/r": watermark}
    )

    client.list_repo_commits.assert_called_once_with(
        "o/r", author="alice", since=watermark
    )


def test_fetch_commits_skips_repos_that_return_409_or_404():
    """Empty/inaccessible repos are silently skipped."""
    client = Mock(spec=GithubClient)
    client.list_repo_commits.side_effect = _http_status_error(409)

    assert GithubProvider(client).fetch_commits([GithubRepo("o/empty")], "alice") == []


def test_fetch_commits_skips_repo_that_returns_403_and_continues():
    """A per-repo access 403 is skipped, not fatal: the walk continues to the next repo."""
    def per_repo(full_name, author, since=None):
        if full_name == "org/locked":
            raise _http_status_error(403)
        return [_payload("a")]

    client = Mock(spec=GithubClient)
    client.list_repo_commits.side_effect = per_repo

    out = GithubProvider(client).fetch_commits(
        [GithubRepo("org/locked"), GithubRepo("org/ok")], "alice"
    )

    assert [c.sha for c in out] == ["a"]
    assert out[0].repo == "org/ok"


def test_fetch_commits_rate_limit_attaches_partial():
    """If we collect from one repo then 403 on the next, the partial commits ride on the exception."""
    def per_repo(full_name, author, since=None):
        if full_name == "o/r1":
            return [_payload("a"), _payload("b")]
        raise RateLimitExceededError("too many")

    client = Mock(spec=GithubClient)
    client.list_repo_commits.side_effect = per_repo

    with pytest.raises(RateLimitExceededError) as excinfo:
        GithubProvider(client).fetch_commits(
            [GithubRepo("o/r1"), GithubRepo("o/r2")], "alice"
        )

    assert [c.sha for c in excinfo.value.partial] == ["a", "b"]


# --- extension breakdown ------------------------------------------------------


def test_ext_breakdown_omits_zero_entries():
    """A `.unity` file with deletions but no additions appears only in `deletions`."""
    client = Mock(spec=GithubClient)
    client.list_pull_request_files.return_value = [
        GithubPullRequestChangedFile("Assets/foo.unity", 0, 3),
        GithubPullRequestChangedFile("src/foo.py", 10, 0),
        GithubPullRequestChangedFile("src/bar.py", 5, 2),
    ]

    additions, deletions = GithubProvider(client)._ext_breakdown("o/r", 1)

    assert additions == {".py": 15}
    assert deletions == {".unity": 3, ".py": 2}


def test_ext_breakdown_no_changes_yields_empty_dicts():
    """A PR with only zero-line file entries returns two empty dicts (not `{ext: 0}`)."""
    client = Mock(spec=GithubClient)
    client.list_pull_request_files.return_value = [GithubPullRequestChangedFile("noop.txt", 0, 0)]

    additions, deletions = GithubProvider(client)._ext_breakdown("o/r", 1)

    assert additions == {}
    assert deletions == {}


# --- pure helpers -------------------------------------------------------------


def test_file_extension_simple():
    """Standard filenames yield their suffix with the dot."""
    assert GithubProvider._file_extension("foo.py") == ".py"
    assert GithubProvider._file_extension("path/to/foo.yml") == ".yml"


def test_file_extension_compound():
    """Only the last suffix is considered (so `.tar.gz` → `.gz`)."""
    assert GithubProvider._file_extension("archive.tar.gz") == ".gz"


def test_file_extension_falls_back_to_basename_for_extensionless_files():
    """Files like `Dockerfile` have no extension and return the bare filename."""
    assert GithubProvider._file_extension("Dockerfile") == "Dockerfile"
    assert GithubProvider._file_extension("path/Makefile") == "Makefile"


def test_file_extension_dotfiles_are_their_own_key():
    """Hidden files like `.gitignore` bucket under their bare name, not ''."""
    assert GithubProvider._file_extension(".gitignore") == ".gitignore"


def test_extract_jira_codes_returns_sorted_flat_list():
    """All codes returned in one sorted, deduped list."""
    assert GithubProvider._extract_jira_codes("WD-1 YWFB-2 WD-3") == ["WD-1", "WD-3", "YWFB-2"]


def test_extract_jira_codes_dedupes_across_inputs():
    """A code appearing in multiple blobs appears once."""
    out = GithubProvider._extract_jira_codes("WD-1 and YWFB-2", "WD-1 again", "PTR-99")
    assert out == ["PTR-99", "WD-1", "YWFB-2"]


def test_extract_jira_codes_ignores_none_and_empty():
    """None and empty strings are tolerated."""
    assert GithubProvider._extract_jira_codes(None, "", "WD-5") == ["WD-5"]


def test_extract_jira_codes_requires_uppercase_prefix():
    """Lowercase prefixes (e.g. `wd-1`) must not match — JIRA codes are uppercase."""
    assert GithubProvider._extract_jira_codes("wd-1 and Pr-2") == []


def test_extract_jira_codes_no_match_returns_empty_list():
    """No matches anywhere produce an empty list (not None)."""
    assert GithubProvider._extract_jira_codes("nothing here", "still nothing") == []


def test_build_query_appends_repo_filter_when_target_repo_set():
    """`target_repo` adds `repo:OWNER/NAME` to the search query."""
    out = GithubProvider._build_query(
        "author:alice", since=None, target_repo="octocat/hello-world"
    )
    assert out == "type:pr author:alice is:closed repo:octocat/hello-world"


def test_build_query_appends_updated_filter_when_since_set():
    """`since` adds an `updated:>=` qualifier for resumed runs."""
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = GithubProvider._build_query("author:alice", since=since, target_repo=None)
    assert out == "type:pr author:alice is:closed updated:>=2026-01-01T00:00:00+00:00"


def test_build_query_omits_optional_filters_when_none():
    """With no since/target_repo the query has neither qualifier."""
    out = GithubProvider._build_query("author:alice", since=None, target_repo=None)
    assert out == "type:pr author:alice is:closed"
