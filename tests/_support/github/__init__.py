"""Support classes for GitHub-domain tests.

Only generic, reusable helpers belong here. One-off behaviors (raising
specific errors, recording specific call args) should use
`unittest.mock.Mock` directly instead of growing a bespoke class.
"""

from .fake_github_client import FakeGithubClient

__all__ = ["FakeGithubClient"]
