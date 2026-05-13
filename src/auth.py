import os
from typing import Protocol

import httpx


class Auth(Protocol):
    def client(self) -> httpx.Client: ...


class PersonalTokenAuth:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise RuntimeError(
                "GITHUB_TOKEN not set. Export your PAT or pass token= explicitly."
            )

    def client(self) -> httpx.Client:
        return httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "GetGit/0.1",
            },
            timeout=30.0,
        )
