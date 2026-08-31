"""Tests for GithubClient — paginate logic and viewer_login.

Uses real `httpx.Response` instances (so `.json()`, `.links`, and
`.raise_for_status()` are the real implementations) and a `Mock` for
the underlying `httpx.Client` to script the response sequence.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import httpx

import pytest

from getgit.github import GithubSettings
from getgit.github import GithubClient, RateLimitExceededError


def _client_with(responses: list[httpx.Response]) -> GithubClient:
    """Build a GithubClient and swap in a Mock that returns `responses` in order."""
    client = GithubClient(GithubSettings(auth_token="t"))
    mock_http = Mock()
    mock_http.get.side_effect = responses
    client._http = mock_http
    return client


def _resp(
    payload,
    links_header: str | None = None,
    status: int = 200,
    headers: dict | None = None,
) -> httpx.Response:
    """Build a real `httpx.Response`. `links_header` populates the `Link` header httpx parses for us."""
    all_headers = dict(headers or {})
    if links_header:
        all_headers["Link"] = links_header
    # `request` must be set so raise_for_status() works; URL is irrelevant under the mock transport.
    return httpx.Response(
        status, json=payload, headers=all_headers, request=httpx.Request("GET", "/")
    )


def test_paginate_yields_a_single_page_array():
    """When there's no `next` link, we get every item from the one response."""
    c = _client_with([_resp([{"a": 1}, {"a": 2}])])

    assert list(c.paginate("/x")) == [{"a": 1}, {"a": 2}]


def test_paginate_follows_next_link_across_pages():
    """The Link header's `next` URL is followed until exhausted."""
    page1 = _resp([{"n": 1}], links_header='</x?page=2>; rel="next"')
    page2 = _resp([{"n": 2}, {"n": 3}])
    c = _client_with([page1, page2])

    assert list(c.paginate("/x")) == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_paginate_handles_search_envelope():
    """`/search/...` endpoints wrap results under `items` — we should unwrap."""
    c = _client_with([_resp({"total_count": 2, "items": [{"a": 1}, {"a": 2}]})])

    assert list(c.paginate("/search/issues", {"q": "type:pr"})) == [{"a": 1}, {"a": 2}]


def test_paginate_sets_per_page_default_on_first_call_only():
    """`per_page=100` is added to first request; following pages reuse the next URL as-is."""
    page1 = _resp([{"n": 1}], links_header='</x?page=2>; rel="next"')
    page2 = _resp([{"n": 2}])
    c = _client_with([page1, page2])

    list(c.paginate("/x"))

    assert c._http.get.call_args_list[0].args == ("/x",)
    assert c._http.get.call_args_list[0].kwargs == {"params": {"per_page": 100}}
    assert c._http.get.call_args_list[1].args == ("/x?page=2",)
    assert c._http.get.call_args_list[1].kwargs == {"params": None}


def test_viewer_login_returns_login_field():
    """viewer_login() should call /user and return the `login` field."""
    c = _client_with([_resp({"login": "alice", "id": 42})])

    assert c.viewer_login() == "alice"
    c._http.get.assert_called_with("/user", params=None)


def test_primary_rate_limit_403_locks_and_raises():
    """A 403 with `X-RateLimit-Remaining: 0` is a rate limit: raise and lock."""
    c = _client_with([_resp([], status=403, headers={"X-RateLimit-Remaining": "0"})])

    with pytest.raises(RateLimitExceededError):
        list(c.paginate("/x"))

    # Client is now locked — the next call is refused without touching the network.
    with pytest.raises(RateLimitExceededError):
        list(c.paginate("/y"))


def test_secondary_rate_limit_403_with_retry_after_locks_and_raises():
    """A 403 carrying `Retry-After` is a secondary (abuse) rate limit: raise and lock."""
    c = _client_with([_resp([], status=403, headers={"Retry-After": "60"})])

    with pytest.raises(RateLimitExceededError):
        list(c.paginate("/x"))


def test_access_403_surfaces_as_http_error_without_locking():
    """A 403 that is not a rate limit (quota remaining, no Retry-After) surfaces as
    HTTPStatusError and does NOT lock the client, so later calls still work."""
    access_denied = _resp([], status=403, headers={"X-RateLimit-Remaining": "4999"})
    later_ok = _resp([{"n": 1}])
    c = _client_with([access_denied, later_ok])

    with pytest.raises(httpx.HTTPStatusError):
        list(c.paginate("/repos/org/private/commits"))

    # Not locked: a subsequent call to another endpoint succeeds.
    assert list(c.paginate("/x")) == [{"n": 1}]


# --- Typed endpoint methods ---------------------------------------------------


def test_list_own_repos_uses_affiliation_and_maps_full_name():
    """Self scope hits /user/repos with the affiliation/visibility params and maps full_name."""
    c = _client_with([_resp([{"full_name": "me/r"}, {"full_name": "org/x"}])])

    out = c.list_own_repos()

    assert [r.full_name for r in out] == ["me/r", "org/x"]
    assert c._http.get.call_args_list[0].args == ("/user/repos",)
    assert c._http.get.call_args_list[0].kwargs["params"] == {
        "affiliation": "owner,collaborator,organization_member",
        "visibility": "all",
        "per_page": 100,
    }


def test_list_user_repos_hits_users_endpoint():
    """Stranger scope hits /users/{username}/repos."""
    c = _client_with([_resp([{"full_name": "alice/r"}])])

    out = c.list_user_repos("alice")

    assert [r.full_name for r in out] == ["alice/r"]
    assert c._http.get.call_args_list[0].args == ("/users/alice/repos",)


def test_search_issues_converts_repository_url_to_slug():
    """Search hits unwrap the envelope and reduce repository_url to owner/name."""
    payload = {
        "items": [
            {"repository_url": "https://api.github.com/repos/octocat/hello", "number": 7},
            {"repository_url": "https://api.github.com/repos/o/r", "number": 3},
        ]
    }
    c = _client_with([_resp(payload)])

    out = c.search_issues("type:pr author:alice is:closed")

    assert [(i.repo_full_name, i.number) for i in out] == [("octocat/hello", 7), ("o/r", 3)]
    assert c._http.get.call_args_list[0].kwargs["params"]["q"] == (
        "type:pr author:alice is:closed"
    )


def test_list_repo_commits_flattens_and_parses_date():
    """Repo commits flatten commit.author.date/commit.message and parse the date."""
    raw = {
        "sha": "abc",
        "commit": {"author": {"date": "2026-05-12T10:00:00Z"}, "message": "hi"},
    }
    c = _client_with([_resp([raw])])

    out = c.list_repo_commits("o/r", author="alice")

    assert out[0].sha == "abc"
    assert out[0].message == "hi"
    assert out[0].authored_at == datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)
    assert c._http.get.call_args_list[0].args == ("/repos/o/r/commits",)
    assert c._http.get.call_args_list[0].kwargs["params"] == {"author": "alice", "per_page": 100}


def test_list_repo_commits_adds_since_when_given():
    """A `since` datetime is sent as an ISO `since=` query param."""
    c = _client_with([_resp([])])

    c.list_repo_commits(
        "o/r", author="alice", since=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert c._http.get.call_args_list[0].kwargs["params"]["since"] == "2026-01-01T00:00:00+00:00"


def test_get_pull_request_maps_fields_and_parses_dates():
    """PR detail maps wire fields and parses timestamps; merged_at stays a datetime."""
    pr = {
        "title": "Add thing",
        "body": "WD-1 body",
        "merged_at": "2026-05-10T09:00:00Z",
        "created_at": "2026-05-01T00:00:00Z",
        "closed_at": "2026-05-10T09:00:00Z",
        "updated_at": "2026-05-10T09:05:00Z",
        "additions": 20,
        "deletions": 4,
        "comments": 2,
        "review_comments": 3,
    }
    c = _client_with([_resp(pr)])

    out = c.get_pull_request("o/r", 5)

    assert out.title == "Add thing"
    assert out.body == "WD-1 body"
    assert out.merged_at == datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc)
    assert out.created_at == datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    assert (out.additions, out.deletions) == (20, 4)
    assert (out.comments, out.review_comments) == (2, 3)
    c._http.get.assert_called_with("/repos/o/r/pulls/5", params=None)


def test_get_pull_request_defaults_missing_counts_and_nullable_dates():
    """Missing counts default to 0; an unmerged/open PR yields merged_at/closed_at None."""
    pr = {"title": "t", "created_at": "2026-05-01T00:00:00Z", "updated_at": "2026-05-02T00:00:00Z"}
    c = _client_with([_resp(pr)])

    out = c.get_pull_request("o/r", 9)

    assert out.merged_at is None
    assert out.closed_at is None
    assert out.body is None
    assert (out.additions, out.deletions, out.comments, out.review_comments) == (0, 0, 0, 0)


def test_list_pull_request_files_maps_filename_and_counts():
    """Files map filename/additions/deletions, defaulting missing counts to 0."""
    c = _client_with([_resp([{"filename": "a.py", "additions": 3}, {"filename": "b.py"}])])

    out = c.list_pull_request_files("o/r", 1)

    assert [(f.filename, f.additions, f.deletions) for f in out] == [
        ("a.py", 3, 0),
        ("b.py", 0, 0),
    ]
    assert c._http.get.call_args_list[0].args == ("/repos/o/r/pulls/1/files",)


def test_list_pull_request_reviews_is_user_null_safe_and_coalesces_body():
    """A review with a null `user` yields author_login None; a null body becomes ''."""
    reviews = [
        {"user": {"login": "alice"}, "state": "APPROVED", "submitted_at": "2026-05-03T00:00:00Z", "body": "lgtm"},
        {"user": None, "state": "COMMENTED", "submitted_at": None, "body": None},
    ]
    c = _client_with([_resp(reviews)])

    out = c.list_pull_request_reviews("o/r", 2)

    assert out[0].author_login == "alice"
    assert out[0].submitted_at == datetime(2026, 5, 3, 0, 0, tzinfo=timezone.utc)
    assert out[1].author_login is None
    assert out[1].body == ""


def test_list_pull_request_commits_returns_shas():
    """PR commits return just the SHAs, used to build the commit→PR index."""
    c = _client_with([_resp([{"sha": "a"}, {"sha": "b"}])])

    assert c.list_pull_request_commits("o/r", 4) == ["a", "b"]
    assert c._http.get.call_args_list[0].args == ("/repos/o/r/pulls/4/commits",)


def test_list_issue_comments_and_review_comments_hit_distinct_endpoints():
    """The two comment streams read from their respective endpoints and expose author_login."""
    issue_c = _client_with([_resp([{"user": {"login": "alice"}}, {"user": None}])])
    review_c = _client_with([_resp([{"user": {"login": "bob"}}])])

    issue_out = issue_c.list_issue_comments("o/r", 1)
    review_out = review_c.list_review_comments("o/r", 1)

    assert [c.author_login for c in issue_out] == ["alice", None]
    assert [c.author_login for c in review_out] == ["bob"]
    assert issue_c._http.get.call_args_list[0].args == ("/repos/o/r/issues/1/comments",)
    assert review_c._http.get.call_args_list[0].args == ("/repos/o/r/pulls/1/comments",)
