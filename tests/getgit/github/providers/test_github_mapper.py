"""Tests for GithubMapper — the stateless wire→domain rules, exercised with no client."""

from datetime import datetime, timezone

from getgit.github import (
    Commit,
    GithubComment,
    GithubCommit,
    GithubMapper,
    GithubPullRequest,
    GithubPullRequestChangedFile,
    GithubReview,
)

_DT = datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)


def _detail(**overrides) -> GithubPullRequest:
    """Build a GithubPullRequest with sensible defaults for build_pull_request tests."""
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


# --- build_query --------------------------------------------------------------


def test_build_query_appends_repo_filter_when_target_repo_set():
    """`target_repo` adds `repo:OWNER/NAME` to the search query."""
    out = GithubMapper.build_query(
        "author:alice", since=None, target_repo="octocat/hello-world"
    )
    assert out == "type:pr author:alice is:closed repo:octocat/hello-world"


def test_build_query_appends_updated_filter_when_since_set():
    """`since` adds an `updated:>=` qualifier for resumed runs."""
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = GithubMapper.build_query("author:alice", since=since, target_repo=None)
    assert out == "type:pr author:alice is:closed updated:>=2026-01-01T00:00:00+00:00"


def test_build_query_omits_optional_filters_when_none():
    """With no since/target_repo the query has neither qualifier."""
    out = GithubMapper.build_query("author:alice", since=None, target_repo=None)
    assert out == "type:pr author:alice is:closed"


# --- extract_jira_codes -------------------------------------------------------


def test_extract_jira_codes_returns_sorted_flat_list():
    """All codes returned in one sorted, deduped list."""
    assert GithubMapper.extract_jira_codes("WD-1 YWFB-2 WD-3") == ["WD-1", "WD-3", "YWFB-2"]


def test_extract_jira_codes_dedupes_across_inputs():
    """A code appearing in multiple blobs appears once."""
    out = GithubMapper.extract_jira_codes("WD-1 and YWFB-2", "WD-1 again", "PTR-99")
    assert out == ["PTR-99", "WD-1", "YWFB-2"]


def test_extract_jira_codes_ignores_none_and_empty():
    """None and empty strings are tolerated."""
    assert GithubMapper.extract_jira_codes(None, "", "WD-5") == ["WD-5"]


def test_extract_jira_codes_requires_uppercase_prefix():
    """Lowercase prefixes (e.g. `wd-1`) must not match — JIRA codes are uppercase."""
    assert GithubMapper.extract_jira_codes("wd-1 and Pr-2") == []


def test_extract_jira_codes_no_match_returns_empty_list():
    """No matches anywhere produce an empty list (not None)."""
    assert GithubMapper.extract_jira_codes("nothing here", "still nothing") == []


# --- file extension -----------------------------------------------------------


def test_file_extension_simple():
    """Standard filenames yield their suffix with the dot."""
    assert GithubMapper._file_extension("foo.py") == ".py"
    assert GithubMapper._file_extension("path/to/foo.yml") == ".yml"


def test_file_extension_compound():
    """Only the last suffix is considered (so `.tar.gz` → `.gz`)."""
    assert GithubMapper._file_extension("archive.tar.gz") == ".gz"


def test_file_extension_falls_back_to_basename_for_extensionless_files():
    """Files like `Dockerfile` have no extension and return the bare filename."""
    assert GithubMapper._file_extension("Dockerfile") == "Dockerfile"
    assert GithubMapper._file_extension("path/Makefile") == "Makefile"


def test_file_extension_dotfiles_are_their_own_key():
    """Hidden files like `.gitignore` bucket under their bare name, not ''."""
    assert GithubMapper._file_extension(".gitignore") == ".gitignore"


# --- count_user_comments ------------------------------------------------------


def test_count_user_comments_counts_only_matching_login():
    """Only comments whose author_login equals the target user are counted."""
    comments = [
        GithubComment("alice"),
        GithubComment("bob"),
        GithubComment("alice"),
        GithubComment(None),
    ]
    assert GithubMapper.count_user_comments(comments, "alice") == 2


def test_count_user_comments_empty_stream_is_zero():
    """An empty comment stream counts to zero."""
    assert GithubMapper.count_user_comments([], "alice") == 0


# --- breakdown_from_files -----------------------------------------------------


def test_breakdown_from_files_omits_zero_entries():
    """A `.unity` file with deletions but no additions appears only in `deletions`."""
    files = [
        GithubPullRequestChangedFile("Assets/foo.unity", 0, 3),
        GithubPullRequestChangedFile("src/foo.py", 10, 0),
        GithubPullRequestChangedFile("src/bar.py", 5, 2),
    ]
    additions, deletions = GithubMapper.breakdown_from_files(files)
    assert additions == {".py": 15}
    assert deletions == {".unity": 3, ".py": 2}


def test_breakdown_from_files_no_changes_yields_empty_dicts():
    """Only zero-line file entries return two empty dicts (not `{ext: 0}`)."""
    files = [GithubPullRequestChangedFile("noop.txt", 0, 0)]
    additions, deletions = GithubMapper.breakdown_from_files(files)
    assert additions == {}
    assert deletions == {}


# --- user_reviews -------------------------------------------------------------


def test_user_reviews_keeps_only_target_user_with_1_based_index():
    """Non-user reviews are dropped; the user's are indexed 1..n in order."""
    reviews = [
        GithubReview(author_login="bob", state="COMMENTED", submitted_at=_DT, body="b"),
        GithubReview(author_login="alice", state="APPROVED", submitted_at=_DT, body="lgtm"),
        GithubReview(author_login="alice", state="CHANGES_REQUESTED", submitted_at=_DT, body="no"),
    ]
    out = GithubMapper.user_reviews(reviews, "o/r", 7, "alice")
    assert [(r.index, r.state) for r in out] == [(1, "APPROVED"), (2, "CHANGES_REQUESTED")]
    assert all(r.pr_repo == "o/r" and r.pr_number == 7 for r in out)


def test_user_reviews_none_for_user_yields_empty():
    """A PR with no reviews by the target user yields an empty list."""
    reviews = [
        GithubReview(author_login="bob", state="COMMENTED", submitted_at=_DT, body="b")
    ]
    assert GithubMapper.user_reviews(reviews, "o/r", 7, "alice") == []


# --- build_commit -------------------------------------------------------------


def test_build_commit_links_pr_number_from_index():
    """A commit present in the index gets its merging PR number attached."""
    payload = GithubCommit(sha="abc", authored_at=_DT, message="msg")
    out = GithubMapper.build_commit(payload, "o/r", {("o/r", "abc"): 42})
    assert out == Commit(
        sha="abc", repo="o/r", authored_at=_DT, message="msg", pull_request_number=42
    )


def test_build_commit_unindexed_commit_has_no_pr_number():
    """A commit absent from the index keeps `pull_request_number=None`."""
    payload = GithubCommit(sha="def", authored_at=_DT, message="msg")
    out = GithubMapper.build_commit(payload, "o/r", {})
    assert out.pull_request_number is None


# --- build_pull_request -------------------------------------------------------


def test_build_pull_request_derives_merged_comments_and_jira():
    """merged, the comment sum, and JIRA codes are derived from the wire detail."""
    detail = _detail(
        title="Fix WD-1",
        body="also WD-2 and WD-1",
        merged_at=_DT,
        comments=3,
        review_comments=2,
    )
    pr = GithubMapper.build_pull_request(
        detail, "o/r", 5, {".py": 10}, {}, comments_by_author=4
    )
    assert pr.repo == "o/r" and pr.number == 5
    assert pr.merged is True
    assert pr.comments == 5  # 3 issue + 2 review comments
    assert pr.comments_by_author == 4
    assert pr.additions == {".py": 10} and pr.deletions == {}
    assert pr.jira_codes == ["WD-1", "WD-2"]


def test_build_pull_request_open_pr_is_not_merged_and_no_jira():
    """No merged_at → not merged; a code-free title/body → empty jira_codes."""
    detail = _detail(title="nothing", body=None, merged_at=None)
    pr = GithubMapper.build_pull_request(detail, "o/r", 1, {}, {}, comments_by_author=0)
    assert pr.merged is False
    assert pr.jira_codes == []
