import httpx

from ..github_api import paginate


def viewer_login(client: httpx.Client) -> str:
    resp = client.get("/user")
    resp.raise_for_status()
    return resp.json()["login"]


def list_repos(client: httpx.Client, username: str, is_self: bool) -> list[dict]:
    if is_self:
        return list(paginate(client, "/user/repos", {"affiliation": "owner", "visibility": "all"}))
    return list(paginate(client, f"/users/{username}/repos"))
