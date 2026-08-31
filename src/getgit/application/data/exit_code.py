"""Process exit codes returned by `application.run`."""

from enum import IntEnum


class ExitCode(IntEnum):
    """The exit codes `application.run` returns, one per run outcome.

    An `IntEnum` so a value is usable directly as a process exit status
    (and compares equal to the bare int) while the names document what
    each code means at the call site. There is deliberately no member
    for `1`: that's Python's default for an unhandled exception, which
    `run` lets propagate rather than returning.
    """

    SUCCESS = 0
    PARTIAL = 2
    REPOSITORY_ACCESS_ERROR = 3
