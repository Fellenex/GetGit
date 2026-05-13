"""Repository discovery — the only place self vs stranger diverges."""

import httpx

from ..github_api import paginate


def viewer_login(client: httpx.Client) -> str:
    """Return the login of the user the PAT belongs to.

    Used to decide whether the target username is "self" (and therefore
    eligible for private-repo enumeration).
    """
    resp = client.get("/user")
    resp.raise_for_status()
    return resp.json()["login"]


def list_repos(client: httpx.Client, username: str, is_self: bool) -> list[dict]:
    """List repos owned by `username`.

    `is_self=True` uses `/user/repos` (returns public + private the PAT
    can see). `is_self=False` uses `/users/{username}/repos` (public
    only). The GitHub API enforces visibility server-side, so this single
    branch is the entire client-side scope check.
    """
    if is_self:
        return list(paginate(client, "/user/repos", {"affiliation": "owner", "visibility": "all"}))
    return list(paginate(client, f"/users/{username}/repos"))
