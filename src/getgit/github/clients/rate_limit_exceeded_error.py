"""Exception raised when GitHub returns a 403, signalling we should stop."""


class RateLimitExceededError(RuntimeError):
    """Raised by `GithubClient` when GitHub returns HTTP 403.

    Once raised, the originating client refuses every subsequent
    `get`/`paginate` call without hitting the network — even if a
    higher layer catches and ignores the first one. This protects
    against burning what little quota the user has left on retries.

    A 403 from GitHub usually means: primary rate limit (5,000/hr
    authenticated), secondary rate limit (abuse detection), or — less
    commonly — insufficient token scopes. We don't try to distinguish;
    the operator can re-run after addressing whichever it was.
    """
