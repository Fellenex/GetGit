"""Support classes for GitHub-domain tests.

Only generic, reusable helpers belong here. One-off behaviors (scripting
a client method's return value, raising a specific error, recording call
args) should use `unittest.mock.Mock(spec=GithubClient)` directly instead
of growing a bespoke class — the client's surface is now typed endpoint
methods returning response objects, which `Mock(spec=...)` models cleanly.
"""

__all__: list[str] = []
